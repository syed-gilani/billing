import os
import traceback
import re
from datetime import datetime, timedelta
from StringIO import StringIO

from sqlalchemy.sql import desc
from sqlalchemy import not_
from sqlalchemy import func

from core.model import (UtilBill, Address, Session,
                           MYSQLDB_DATETIME_MIN, UtilityAccount, RateClass)
from reebill.reebill_file_handler import SummaryFileGenerator
from reebill.reebill_model import (ReeBill, Reading, ReeBillCustomer)
from exc import (IssuedBillError, NoSuchBillException, ConfirmAdjustment,
                 FormulaError, RegisterError, BillingError)
from core.utilbill_processor import ACCOUNT_NAME_REGEX
from util.pdf import PDFConcatenator


class ReebillProcessor(object):
    ''''Does a mix of the following things:
    - Operations on reebills: create, delete, compute, etc.
    etc.
    - CRUD on child objects of ReeBill that are closely associated
    with ReeBills, like ReeBillCharges and Readings.
    - CRUD on Payments.
    - CRUD on ReeBillCustomers.
    - Generating JSON data for the ReeBill UI.
    Each of these things should be separated into its own class (especially
    the UI-related methods), except maybe the first two can stay in the same
    class.
    '''
    def __init__(self, state_db, payment_dao, nexus_util, bill_mailer,
                 reebill_file_handler, ree_getter, journal_dao, logger=None):
        self.state_db = state_db
        self.payment_dao = payment_dao
        self.nexus_util = nexus_util
        self.bill_mailer = bill_mailer
        self.ree_getter = ree_getter
        self.reebill_file_handler = reebill_file_handler
        self.logger = logger
        self.journal_dao = journal_dao

    # TODO rename this to something that makes sense
    def get_hypothetical_matched_charges(self, reebill_id):
        """Gets all hypothetical charges from a reebill for a service and
        matches the actual charge to each hypotheitical charge
        TODO: This method has no test coverage!"""
        reebill = self.state_db.get_reebill_by_id(reebill_id)
        return [{
            'rsi_binding': reebill_charge.rsi_binding,
            'description': reebill_charge.description,
            'actual_quantity': reebill_charge.a_quantity,
            'quantity': reebill_charge.h_quantity,
            'unit': reebill_charge.unit,
            'rate': reebill_charge.rate,
            'actual_total': reebill_charge.a_total,
            'total': reebill_charge.h_total,
        } for reebill_charge in reebill.charges]

    def get_sequential_account_info(self, account, sequence):
        reebill = self.state_db.get_reebill(account, sequence)
        def address_to_dict(self):
            return {
                'addressee': self.addressee,
                'street': self.street,
                'city': self.city,
                'state': self.state,
                'postal_code': self.postal_code,
                }
        b_addr_dict = address_to_dict(reebill.billing_address)
        s_addr_dict = address_to_dict(reebill.service_address)
        return {
            'billing_address': b_addr_dict,
            'service_address': s_addr_dict,
            'discount_rate': reebill.discount_rate,
            'late_charge_rate': reebill.late_charge_rate,
        }

    def update_sequential_account_info(self, account, sequence,
            discount_rate=None, late_charge_rate=None, processed=None,
            ba_addressee=None, ba_street=None, ba_city=None, ba_state=None,
            ba_postal_code=None,
            sa_addressee=None, sa_street=None, sa_city=None, sa_state=None,
            sa_postal_code=None):
        """Update fields for the reebill given by account, sequence
        corresponding to the "sequential account information" form in the UI,
        """
        reebill = self.state_db.get_reebill(account, sequence)
        reebill.check_editable()

        if discount_rate is not None:
            reebill.discount_rate = discount_rate
        if late_charge_rate is not None:
            reebill.late_charge_rate = late_charge_rate
        if processed is not None:
            reebill.processed = processed
        if ba_addressee is not None:
            reebill.billing_address.addressee = ba_addressee
        if ba_state is not None:
            reebill.billing_address.state = ba_state
        if ba_street is not None:
            reebill.billing_address.street = ba_street
        if ba_city is not None:
            reebill.billing_address.city = ba_city
        if ba_postal_code is not None:
            reebill.billing_address.postal_code = ba_postal_code

        if sa_addressee is not None:
            reebill.service_address.addressee = sa_addressee
        if sa_state is not None:
            reebill.service_address.state = sa_state
        if sa_street is not None:
            reebill.service_address.street = sa_street
        if sa_city is not None:
            reebill.service_address.city = sa_city
        if sa_postal_code is not None:
            reebill.service_address.postal_code = sa_postal_code

        return reebill

    def compute_reebill(self, account, sequence, version='max'):
        """Most of this code, if not all, should be in ReeBill itself.
        """
        reebill = self.state_db.get_reebill(account, sequence, version)
        reebill.compute_charges()
        reebill.late_charge = self.get_late_charge(
            reebill, datetime.utcnow().date()) or 0

        # compute adjustment: this bill only gets an adjustment if it's the
        # earliest unissued version-0 bill, i.e. it meets 2 criteria:
        # (1) it's a version-0 bill, not a correction
        # (2) at least the 0th version of its predecessor has been issued (it
        #     may have an unissued correction; if so, that correction will
        #     contribute to the adjustment on this bill)
        predecessor = self.state_db.get_predecessor(reebill, version=0)
        reebill.set_adjustment(predecessor, self)

        # calculate payments:

        original_version = self.state_db.get_original_version(reebill)
        if reebill.sequence == 1:
            # include all payments since the beginning of time, in case there
            # happen to be any (which there shouldn't be--no one would pay
            # before receiving their first bill).
            # if any version of this bill has been issued, get payments up
            # until the issue date; otherwise get payments up until the
            # present.
            payments = self.payment_dao.get_total_payment_since(
                    account, MYSQLDB_DATETIME_MIN,
                    # will be None if original_version is not issued
                    end=original_version.issue_date)
            reebill.set_payments(payments, 0)
            return reebill

        assert reebill.sequence > 1
        if not predecessor.issued:
            # if predecessor is not issued, there's no way to tell what
            # payments will go in this bill instead of a previous bill, so
            # assume there are none (all payments since last issue date
            # go in the account's first unissued bill)
            reebill.set_payments([], predecessor.balance_due)
            return reebill

        assert reebill.sequence > 1 and predecessor.issued
        # all payments between issue date of predecessor and issue date of
        # the current bill (or today if not issued) apply to this bill
        payments = self.payment_dao.get_total_payment_since(account,
            predecessor.issue_date, end=original_version.issue_date)
        reebill.set_payments(payments, predecessor.balance_due)
        return reebill

    def roll_reebill(self, account, start_date=None):
        """ Create first or roll the next reebill for given account.
        After the bill is rolled, this function also binds renewable energy data
        and computes the bill by default. This behavior can be modified by
        adjusting the appropriate parameters.
        'start_date': must be given for the first reebill.
        """
        session = Session()

        reebill_customer = self.state_db.get_reebill_customer(account)
        last_reebill_row = session.query(ReeBill)\
                .filter(ReeBill.reebill_customer == reebill_customer)\
                .order_by(desc(ReeBill.sequence), desc(ReeBill.version)).first()

        new_utilbills = []
        if last_reebill_row is None:
            # No Reebills are associated with this account: Create the first one
            assert start_date is not None
            utilbill = session.query(UtilBill)\
                    .filter(UtilBill.utility_account ==
                            reebill_customer.utility_account)\
                    .filter(UtilBill.period_start >= start_date)\
                    .order_by(UtilBill.period_start).first()
            if utilbill is None:
                raise ValueError("No utility bill found starting on/after %s" %
                        start_date)
            new_utilbills.append(utilbill)
            new_sequence = 1
        else:
            # There are Reebills associated with this account: Create the next Reebill
            # First, find the successor to every utility bill belonging to the reebill
            # note that Hypothetical utility bills are excluded.
            for utilbill in last_reebill_row.utilbills:
                successor = session.query(UtilBill)\
                    .filter(UtilBill.utility_account == reebill_customer.utility_account)\
                    .filter(not_(UtilBill._utilbill_reebills.any()))\
                    .filter(RateClass.service == utilbill.get_service())\
                    .filter(UtilBill.utility == utilbill.utility)\
                    .filter(UtilBill.period_start >= utilbill.period_end)\
                    .order_by(UtilBill.period_end).first()
                if successor is None:
                    raise NoSuchBillException(("Couldn't find next "
                            "utility bill following %s") % utilbill)
                new_utilbills.append(successor)
            new_sequence = last_reebill_row.sequence + 1

        if not all(r.processed for r in new_utilbills):
            raise BillingError('Utility bill must be processed')

        # currently only one service is supported
        assert len(new_utilbills) == 1

        # create reebill row in state database
        new_reebill = ReeBill(reebill_customer, new_sequence, 0,
                              utilbills=new_utilbills,
                              billing_address=Address.from_other(
                                new_utilbills[0].billing_address),
                              service_address=Address.from_other(
                                new_utilbills[0].service_address))

        # assign Reading objects to the ReeBill based on registers from the
        # utility bill document
        if last_reebill_row is None:
            # this is the first reebill: choose only REG_TOTAL complain if it
            # doesn't exist
            try:
                reg_total_register = next(r for r in utilbill.registers if
                                          r.register_binding == 'REG_TOTAL')
            except StopIteration:
                raise RegisterError('The utility bill must have a register '
                                    'called "REG_TOTAL"')
            new_reebill.readings = [Reading.make_reading_from_register(
                reg_total_register)]
        else:
            # not the first reebill: copy readings from the previous one
            new_reebill.update_readings_from_reebill(last_reebill_row.readings)
            new_reebill.copy_reading_conventional_quantities_from_utility_bill()
        session.add(new_reebill)
        session.add_all(new_reebill.readings)

        self.ree_getter.update_renewable_readings(
                self.nexus_util.olap_id(account), new_reebill, use_olap=True)

        try:
            self.compute_reebill(account, new_sequence)
        except FormulaError as e:
            self.logger.error("Error when computing reebill %s: %s" % (
                    new_reebill, e))
        return new_reebill

    def new_version(self, account, sequence):
        """Creates a new version of the given reebill: duplicates the Reebill,
        re-computes the it, saves it, and increments the max_version number in
        MySQL. Returns the the new reebill.
        """
        if sequence <= 0:
            raise ValueError('Only sequence >= 0 can have multiple versions.')
        if not self.state_db.is_issued(account, sequence):
            raise ValueError("Can't create new version of an un-issued bill.")

        max_version = self.state_db.max_version(account, sequence)
        reebill = self.state_db.increment_version(account, sequence)

        assert len(reebill.utilbills) == 1

        self.ree_getter.\
            update_renewable_readings(self.nexus_util.olap_id(account), reebill)
        try:
            self.compute_reebill(account, sequence, version=max_version+1)
        except Exception as e:
            # NOTE: catching Exception is awful and horrible and terrible and
            # you should never do it, except when you can't think of any other
            # way to accomplish the same thing. ignoring the error here allows
            # a new version of the bill to be created even when it can't be
            # computed (e.g. the rate structure is broken and the user wants to
            # edit it, but can't until the new version already exists).
            self.logger.error(("In Process.new_version, couldn't compute new "
                    "version %s of reebill %s-%s: %s\n%s") % (
                    reebill.version, reebill.get_account(),
                    reebill.sequence, e, traceback.format_exc()))

        return reebill

    def get_unissued_corrections(self, account):
        """Returns [(sequence, max_version, balance adjustment)] of all
        un-issued versions of reebills > 0 for the given account."""
        result = []
        for seq, max_version in self.state_db.get_unissued_corrections(account):
            # adjustment is difference between latest version's
            # charges and the previous version's
            assert max_version > 0
            latest_version = self.state_db.get_reebill(account, seq,
                    version=max_version)
            prev_version = self.state_db.get_reebill(account, seq,
                    version=max_version - 1)
            adjustment = latest_version.total - prev_version.total
            result.append((seq, max_version, adjustment))
        return result

    def issue_corrections(self, account, target_sequence):
        '''Applies adjustments from all unissued corrections for 'account' to
        the reebill given by 'target_sequence', and marks the corrections as
        issued.'''
        # corrections can only be applied to an un-issued reebill whose version
        # is 0
        target_max_version = self.state_db.max_version(account, target_sequence)

        reebill = self.state_db.get_reebill(account, target_sequence,
                                            target_max_version)
        if reebill.issued or reebill.version > 0:
            raise ValueError(("Can't apply corrections to %s-%s, "
                    "because the latter is an issued reebill or another "
                    "correction.") % (account, target_sequence))

        all_unissued_corrections = self.get_unissued_corrections(account)

        if len(all_unissued_corrections) == 0:
            # no corrections to apply
            return

        if not reebill.processed:
            self.compute_reebill(account, target_sequence,
                version=target_max_version)

        # issue each correction
        for correction in all_unissued_corrections:
            correction_sequence, _, _ = correction
            correction_reebill = self.state_db.get_reebill(account,
                                                           correction_sequence)
            correction_reebill.issue(datetime.utcnow(), self)

    def get_total_adjustment(self, account):
        '''Returns total adjustment that should be applied to the next issued
        reebill for 'account' (i.e. the earliest unissued version-0 reebill).
        This adjustment is the sum of differences in totals between each
        unissued correction and the previous version it corrects.'''
        return sum(adjustment for (sequence, version, adjustment) in
                self.get_unissued_corrections(account))

    def get_late_charge(self, reebill, day):
        '''Returns the late charge for the given reebill on 'day', which is the
        present by default. ('day' will only affect the result for a bill that
        hasn't been issued yet: there is a late fee applied to the balance of
        the previous bill when only when that previous bill's due date has
        passed.) Late fees only apply to bills whose predecessor has been
        issued; 0 is returned if the predecessor has not been issued. (The
        first bill and the sequence 0 template bill always have a late charge
        of 0.)'''
        predecessor = self.state_db.get_predecessor(reebill)
        predecessor0 = self.state_db.get_predecessor(
            self.state_db.get_original_version(reebill), version=0)

        # the first bill, an unissued bill, or any bill before the due date
        # of its predecessor has no late charge
        if (reebill.sequence <= 1 or not predecessor.issued or
            day <= predecessor0.due_date):
            return 0

        # the balance on which a late charge is based is not necessarily the
        # current bill's balance_forward or the "outstanding balance": it's the
        # least balance_due of any issued version of the predecessor (as if it
        # had been charged on version 0's issue date, even if the version
        # chosen is not 0).
        min_balance_due = Session().query(func.min(ReeBill.balance_due))\
                .filter(ReeBill.reebill_customer == reebill.reebill_customer)\
                .filter(ReeBill.sequence == reebill.sequence - 1).scalar()
        total_payment = sum(p.credit for p in
                            self.payment_dao.get_total_payment_since(
                                reebill.get_account(), predecessor0.issue_date))
        source_balance = min_balance_due - total_payment
        #Late charges can only be positive
        return (reebill.late_charge_rate) * max(0, source_balance)

    def delete_reebill(self, account, sequence):
        '''Deletes the the given reebill and its utility bill associations.
        A reebill version has been issued can't be deleted. Returns the version
        of the reebill that was deleted.'''
        session = Session()
        reebill = self.state_db.get_reebill(account, sequence)
        reebill.check_editable()
        if reebill.version == 0 and reebill.sequence < \
                self.state_db.last_sequence(account):
            raise IssuedBillError("Only the last reebill can be deleted")
        version = reebill.version

        # NOTE session.delete() fails with an errror like "InvalidRequestError:
        # Instance '<ReeBill at 0x353cbd0>' is not persisted" if the object has
        # not been persisted (i.e. flushed from SQLAlchemy cache to database)
        # yet; the author says on Stack Overflow to use 'expunge' if the object
        # is in 'session.new' and 'delete' otherwise, but for some reason
        # 'reebill' does not get into 'session.new' when session.add() is
        # called. i have not solved this problem yet.
        session.delete(reebill)

        # Delete the PDF associated with a reebill if it was version 0
        # because we believe it is confusing to delete the pdf when
        # when a version still exists
        if version == 0:
            self.reebill_file_handler.delete_file(reebill, ignore_missing=True)
        return version

    def create_new_account(self, account, name, service_type, discount_rate,
            late_charge_rate, billing_address, service_address,
            template_account, utility_account_number):
        '''Creates a new account with utility bill template copied from the
        last utility bill of 'template_account' (which must have at least one
        utility bill).
        
        'billing_address' and 'service_address' are dictionaries containing the
        addresses for the utility bill. The address format should be the
        utility bill address format.

        Returns the new state.Customer.'''
        if self.state_db.account_exists(account):
            raise ValueError("Account %s already exists" % account)

        # validate parameters
        if not re.match(ACCOUNT_NAME_REGEX, account):
            raise ValueError('Invalid account number')
        if not 0 <= discount_rate <= 1:
            raise ValueError('Discount rate must be between 0 and 1 inclusive')
        if not 0 <= late_charge_rate <=1:
            raise ValueError(('Late charge rate must be between 0 and 1 '
                              'inclusive'))
        if service_type not in (None,) + ReeBillCustomer.SERVICE_TYPES:
            raise ValueError('Unknown service type "%s"' % service_type)

        session = Session()
        template_utility_account = session.query(UtilityAccount).filter_by(
                account=template_account).one()
        last_utility_bill = session.query(UtilBill)\
                .join(UtilityAccount).filter(UtilBill.utility_account==template_utility_account)\
                .order_by(desc(UtilBill.period_end)).first()
        if last_utility_bill is None:
            utility = template_utility_account.fb_utility
            supplier = template_utility_account.fb_supplier
            rate_class = template_utility_account.fb_rate_class
        else:
            utility = last_utility_bill.utility
            supplier = last_utility_bill.supplier
            rate_class = last_utility_bill.rate_class

        new_utility_account = UtilityAccount(
            name, account, utility, supplier, rate_class,
            Address(billing_address['addressee'],
                    billing_address['street'],
                    billing_address['city'],
                    billing_address['state'],
                    billing_address['postal_code']),
            Address(service_address['addressee'],
                    service_address['street'],
                    service_address['city'],
                    service_address['state'],
                    service_address['postal_code']),
                    account_number=utility_account_number)

        session.add(new_utility_account)

        if service_type is not None:
            new_reebill_customer = ReeBillCustomer(
                name=name, discount_rate=discount_rate,
                late_charge_rate=late_charge_rate, service=service_type,
                bill_email_recipient='example@example.com',
                utility_account=new_utility_account)
            session.add(new_reebill_customer)
            session.flush()
            return new_reebill_customer

    # deprecated--do not use!
    def issue(self, account, sequence, issue_date=None):
        if issue_date is None:
            issue_date = datetime.utcnow()
        reebill = self.state_db.get_reebill(account, sequence)
        reebill.issue(issue_date, self)

    def update_reebill_readings(self, account, sequence):
        '''Replace the readings of the reebill given by account, sequence
        with a new set of readings that matches the reebill's utility bill.
        '''
        reebill = self.state_db.get_reebill(account, sequence)
        reebill.check_editable()
        reebill.replace_readings_from_utility_bill_registers(reebill.utilbill)
        return reebill

    def bind_renewable_energy(self, account, sequence):
        reebill = self.state_db.get_reebill(account, sequence)
        reebill.check_editable()
        self.ree_getter.update_renewable_readings(
                self.nexus_util.olap_id(account), reebill, use_olap=True)

    def mail_reebill(self, account, sequence, recipient_list):
        reebill = self.state_db.get_reebill(account, sequence)

        # render the bills
        self.reebill_file_handler.render(reebill)

        # "the last element" (???)
        bill_file_name = "%.5d_%.4d.pdf" % (int(account), int(sequence))
        bill_date = "%s" % reebill.get_period()[0]
        merge_fields = {
            'street': reebill.service_address.street,
            'balance_due': round(reebill.balance_due, 2),
            'bill_dates': bill_date,
            'last_bill': bill_file_name,
        }
        bill_file_path = self.reebill_file_handler.get_file_path(reebill)
        self.bill_mailer.mail(
            recipient_list,
            merge_fields,
            open(bill_file_path, 'r'),
            bill_file_path)

    def _get_issuable_reebills(self):
        '''Return a Query of "issuable" reebills (lowest-sequence bill for
        each account that is unissued and is not a correction).
        '''
        session = Session()
        unissued_v0_reebills = session.query(
            ReeBill.sequence, ReeBill.reebill_customer_id).filter(
            ReeBill.issued == 0, ReeBill.version == 0)
        unissued_v0_reebills = unissued_v0_reebills.subquery()
        min_sequence = session.query(
            unissued_v0_reebills.c.reebill_customer_id.label(
                'reebill_customer_id'),
            func.min(unissued_v0_reebills.c.sequence).label('sequence')) \
            .group_by(unissued_v0_reebills.c.reebill_customer_id).subquery()
        return session.query(ReeBill).filter(
            ReeBill.reebill_customer_id == min_sequence.c.reebill_customer_id) \
            .filter(ReeBill.sequence == min_sequence.c.sequence)

    def get_issuable_reebills_dict(self):
        """ Returns a list of issuable reebill dictionaries
            of the earliest unissued version-0 reebill account. If
            proccessed == True, only processed Reebills are returned
            account can be used to get issuable bill for an account
        """
        return [r.column_dict() for r in self.get_issuable_reebills().all()]

    def issue_and_mail(self, apply_corrections, account, sequence,
                       recipients=None):
        """this function issues a single reebill and sends out a confirmation
        email.
        """
        # If there are unissued corrections and the user has not confirmed
        # to issue them, we will return a list of those corrections and the
        # sum of adjustments that have to be made so the client can create
        # a confirmation message
        unissued_corrections = self.get_unissued_corrections(account)
        if len(unissued_corrections) > 0 and not apply_corrections:
            # The user has confirmed to issue unissued corrections.
            sequences = [sequence for sequence, _, _ in unissued_corrections]
            total_adjustment = sum(adjustment
                        for _, _, adjustment in unissued_corrections)
            raise ConfirmAdjustment(sequences, total_adjustment)
        # Let's issue
        try:
            if len(unissued_corrections) > 0:
                assert apply_corrections is True
                self.issue_corrections(account, sequence)
            else:
                reebill = self.state_db.get_reebill(account, sequence)
                reebill.issue(datetime.utcnow(), self)
        except Exception as e:
            self.logger.error(('Error when issuing reebill %s-%s: %s' %(
                    account, sequence, e.__class__.__name__),) + e.args)
            raise
        # Let's mail!
        # Recepients can be a comma seperated list of email addresses
        if recipients is None:
            # this is not supposed to be allowed but somehow it happens
            # in a test
            recipient_list = ['']
        else:
            recipient_list = [rec.strip() for rec in recipients.split(',')]
        self.mail_reebill(account, sequence, recipient_list)

    def issue_processed_and_mail(self, apply_corrections):
        '''This function issues all processed reebills'''
        bills = self._get_issuable_reebills().filter_by(processed=True).all()
        for bill in bills:
            # If there are unissued corrections and the user has not confirmed
            # to issue them, we will return a list of those corrections and the
            # sum of adjustments that have to be made so the client can create
            # a confirmation message
            unissued_corrections = self.get_unissued_corrections(
                bill.reebill_customer.utility_account.account)
            if len(unissued_corrections) > 0 and not apply_corrections:
                # The user has confirmed to issue unissued corrections.
                sequences = [sequence for sequence, _, _
                            in unissued_corrections]
                total_adjustment = sum(adjustment
                            for _, _, adjustment in unissued_corrections)
                raise ConfirmAdjustment(sequences, total_adjustment)
            # Let's issue
            if len(unissued_corrections) > 0:
                assert apply_corrections is True
                try:
                    self.issue_corrections(bill.get_account(), bill.sequence)
                except Exception as e:
                    self.logger.error(('Error when issuing reebill %s-%s: %s' %(
                        bill.get_account(), bill.sequence,
                        e.__class__.__name__),) + e.args)
                    raise
            try:
                bill.issue(datetime.utcnow(), self)
            except Exception, e:
                self.logger.error(('Error when issuing reebill %s-%s: %s' %(
                        bill.get_account(), bill.sequence,
                        e.__class__.__name__),) + e.args)
                raise
            # Let's mail!
            # Recepients can be a comma seperated list of email addresses
            if bill.email_recipient is None:
                # this is not supposed to be allowed but somehow it happens
                # in a test
                recipient_list = ['']
            else:
                recipient_list = [rec.strip() for rec in
                                  bill.email_recipient.split(',')]
            self.mail_reebill(bill.get_account(), bill.sequence,
                              recipient_list)
        bills_dict = [bill.column_dict() for bill in bills]
        return bills_dict

    # TODO this method has no test coverage. maybe combine it into
    # update_sequential_account_info and add to the test for that
    def update_bill_email_recipient(self, account, sequence, recepients):
        """ Finds a particular reebill by account and sequence,
            finds the connected customer and updates the customer's default
            email recipient(s)
        """
        reebill = self.state_db.get_reebill(account, sequence)
        reebill.reebill_customer.bill_email_recipient = recepients

    def render_reebill(self, account, sequence):
        reebill = self.state_db.get_reebill(account, sequence)
        self.reebill_file_handler.render(reebill)

    def issue_summary(self, group):
        bills = group.get_bills_to_issue()
        if not bills:
            raise BillingError('No Processed bills were found for customers '
                               'with group %s' % group.name)

        for b in bills:
            self.issue_corrections(b.get_account(), b.sequence)
            b.issue(datetime.utcnow(), self)

        # create and email combined PDF file
        summary_file = StringIO()
        sfg = SummaryFileGenerator(self.reebill_file_handler, PDFConcatenator())
        sfg.generate_summary_file(bills, summary_file)
        summary_file.seek(0)
        merge_fields = {
            'street': group.name,
            'balance_due': sum(b.balance_due for b in bills),
            'bill_dates': max(b.get_period_end() for b in bills),
            'last_bill': '',
        }
        self.bill_mailer.mail(group.bill_email_recipient, merge_fields,
                              summary_file, 'summary.pdf')
        return bills

    def toggle_reebill_processed(self, account, sequence,
                apply_corrections):
        '''Make the reebill given by account, sequence, processed if
        it is not processed or un-processed if it is processed. If there are
        un-issued corrections for the given account, 'apply_corrections' must
        be True or ConfirmAdjustment will be raised.
        '''
        session = Session()
        reebill = self.state_db.get_reebill(account, sequence)

        if reebill.issued:
            raise IssuedBillError("Can't modify an issued bill")

        issuable_reebill = session.query(ReeBill).join(ReeBillCustomer) \
                .join(UtilityAccount)\
                .filter(UtilityAccount.account==account)\
                .filter(ReeBill.version==0, ReeBill.issued==False)\
                .order_by(ReeBill.sequence).first()

        if reebill.processed:
            reebill.processed = False
        else:
            if reebill == issuable_reebill:
                unissued_corrections = self.get_unissued_corrections(account)

                # if there are corrections that are not already processed and
                # user has not confirmed applying
                # them, send back data for a confirmation message
                unprocessed_corrections = False
                for sequence, version, _ in unissued_corrections:
                    correction = self.state_db.get_reebill(account, sequence,
                                                           version)
                    if not correction.processed:
                        unprocessed_corrections = True
                        break
                if len(unissued_corrections) > 0 and unprocessed_corrections \
                        and not apply_corrections:
                    sequences = [sequence for sequence, _, _
                            in unissued_corrections]
                    total_adjustment = sum(adjustment
                            for _, _, adjustment in unissued_corrections)
                    raise ConfirmAdjustment(sequences, total_adjustment)

                # otherwise, mark corrected bills as processed
                if unprocessed_corrections:
                    for sequence, version, _ in unissued_corrections:
                        unissued_reebill = self.state_db.get_reebill(account,
                                                                     sequence)
                        if not unissued_reebill.processed:
                            self.compute_reebill(account, sequence)
                            unissued_reebill.processed = True

            self.compute_reebill(account, reebill.sequence)
            reebill.processed = True

