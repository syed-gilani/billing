'''SQLAlchemy model classes for ReeBill-related database tables.
'''
from datetime import datetime, date
from itertools import chain
import traceback

from sqlalchemy import Column, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.types import Integer, String, Float, Date, DateTime, Boolean,\
        Enum
from sqlalchemy.ext.associationproxy import association_proxy

from exc import IssuedBillError, RegisterError, ProcessedBillError
from core.model import Base, Address, Register, Session, Evaluation, \
    UtilBill, Charge
from util.units import ureg, convert_to_therms


__all__ = [
    'Payment',
    'Reading',
    'ReeBill',
    'ReeBillCharge',
    'ReeBillCustomer',
]

class ReeBill(Base):
    __tablename__ = 'reebill'

    id = Column(Integer, primary_key=True)
    reebill_customer_id = Column(Integer,ForeignKey('reebill_customer.id'),
                                 nullable=False)
    sequence = Column(Integer, nullable=False)
    issued = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    issue_date = Column(DateTime)

    # new fields from Mongo
    ree_charge = Column(Float, nullable=False)
    balance_due = Column(Float, nullable=False)
    balance_forward = Column(Float, nullable=False)
    discount_rate = Column(Float, nullable=False)
    due_date = Column(Date)
    late_charge_rate = Column(Float, nullable=False)
    late_charge = Column(Float, nullable=False)
    total_adjustment = Column(Float, nullable=False)
    manual_adjustment = Column(Float, nullable=False)
    payment_received = Column(Float, nullable=False)
    prior_balance = Column(Float, nullable=False)
    ree_value = Column(Float, nullable=False)
    ree_savings = Column(Float, nullable=False)
    email_recipient = Column(String(1000), nullable=True)
    processed = Column(Boolean, default=False)

    billing_address_id = Column(Integer, ForeignKey('address.id'),
        nullable=False)
    service_address_id = Column(Integer, ForeignKey('address.id'),
        nullable=False)

    reebill_customer = relationship("ReeBillCustomer",
                                    backref=backref('reebills', order_by=id))

    billing_address = relationship('Address', uselist=False,
        cascade='all',
        primaryjoin='ReeBill.billing_address_id==Address.id')
    service_address = relationship('Address', uselist=False, cascade='all',
        primaryjoin='ReeBill.service_address_id==Address.id')

    _utilbill_reebills = relationship('UtilbillReebill', backref='reebill',
        # NOTE: the "utilbill_reebill" table also has ON DELETE CASCADE in
        # the db
        cascade='delete')

    # NOTE on why there is no corresponding 'UtilBill.reebills' attribute: each
    # 'AssociationProxy' has a 'creator', which is a callable that creates a
    # new instance of the intermediate class whenever an instance of the
    # "target" class is appended to the list (in this case, a new instance of
    # 'UtilbillReebill' to hold each UtilBill). the default 'creator' is just
    # the intermediate class itself, which works when that class' constructor
    # has only one argument and that argument is the target class instance. in
    # this case the 'creator' is 'UtilbillReebill' and its __init__ takes one
    # UtilBill as its argument. if there were a bidirectional relationship
    # where 'UtilBill' also had a 'reebills' attribute,
    # UtilbillReebill.__init__ would have to take both a UtilBill and a ReeBill
    # as arguments, so a 'creator' would have to be explicitly specified. for
    # ReeBill it would be something like
    #     creator=lambda u: UtilbillReebill(u, self)
    # and for UtilBill,
    #     creator=lambda r: UtilbillReebill(self, r)
    # but this will not actually work because 'self' is not available in class
    # scope; there is no instance of UtilBill or ReeBill at the time this
    # code is executed. it also does not work to move the code into __init__
    # and assign the 'utilbills' attribute to a particular ReeBill instance
    # or vice versa. there may be a way to make SQLAlchemy do this (maybe by
    # switching to "classical" class-definition style?) but i decided it was
    # sufficient to have only a one-directional relationship from ReeBill to
    # UtilBill.
    utilbills = association_proxy('_utilbill_reebills', 'utilbill')

    @property
    def utilbill(self):
        assert len(self.utilbills) == 1
        return self.utilbills[0]

    # see the following documentation for delete cascade behavior
    charges = relationship('ReeBillCharge', backref='reebill',
                           cascade='all, delete-orphan')
    readings = relationship('Reading', backref='reebill',
                            cascade='all, delete-orphan')

    def __init__(self, reebill_customer, sequence, version=0,
                 discount_rate=None, late_charge_rate=None,
                 billing_address=None, service_address=None, utilbills=[]):
        self.reebill_customer = reebill_customer
        self.sequence = sequence
        self.version = version
        self.issued = 0
        if discount_rate:
            self.discount_rate = discount_rate
        else:
            self.discount_rate = self.reebill_customer.discountrate
        if late_charge_rate:
            self.late_charge_rate = late_charge_rate
        else:
            self.late_charge_rate = self.reebill_customer.latechargerate

        self.ree_charge = 0
        self.balance_due = 0
        self.balance_forward = 0
        self.due_date = None
        self.late_charge = 0
        self.total_adjustment = 0
        self.manual_adjustment = 0
        self.payment_received = 0
        self.prior_balance = 0
        self.ree_value = 0
        self.ree_savings = 0
        self.email_recipient = None

        # NOTE: billing/service_address arguments can't be given default value
        # 'Address()' because that causes the same Address instance to be
        # assigned every time.
        self.billing_address = billing_address or Address()
        self.service_address = service_address or Address()

        # supposedly, SQLAlchemy sends queries to the database whenever an
        # association_proxy attribute is accessed, meaning that if
        # 'utilbills' is set before the other attributes above, SQLAlchemy
        # will try to insert the new row too soon, and fail because many
        # fields are still null but the columns are defined as not-null. this
        # can be fixed by setting 'utilbills' last, but there may be a better
        # solution. see related bug:
        # https://www.pivotaltracker.com/story/show/65502556
        self.utilbills = utilbills

    def __repr__(self):
        return '<ReeBill %s-%s-%s, %s, %s utilbills>' % (
            self.get_account(), self.sequence, self.version, 'issued' if
            self.issued else 'unissued', len(self.utilbills))

    def get_account(self):
        return self.reebill_customer.get_account()


    def check_editable(self):
        '''Raise a ProcessedBillError or IssuedBillError to prevent editing a
        bill that should not be editable.
        '''
        if self.issued:
            raise IssuedBillError("Can't modify an issued reebill")
        if self.processed:
            raise ProcessedBillError("Can't modify a processed reebill")

    def get_period(self):
        '''Returns period of the first (only) utility bill for this reebill
        as tuple of dates.
        '''
        return self.utilbills[0].period_start, self.utilbills[0].period_end


    def copy_reading_conventional_quantities_from_utility_bill(self):
        """Sets the conventional_quantity of each reading to match the
        corresponding utility bill register quantity."""
        s = Session.object_session(self)
        for reading, register in s.query(Reading, Register).join(Register,
                Reading.register_binding == Register.register_binding). \
                filter(Reading.reebill_id == self.id). \
                filter(Register.utilbill_id == self.utilbill.id).all():
            reading.conventional_quantity = register.quantity

    def replace_readings_from_utility_bill_registers(self, utility_bill):
        """Deletes and replaces the readings using the corresponding utility
        bill registers."""
        s = Session.object_session(self)

        while len(self.readings) > 0:
            # using the cascade setting "all, delete-orphan" deletes
            # the reading from the session when it gets dissasociated from
            # its parent. otherwise it would be necessary to call
            # s.expunge(elf.readings[0]).
            del self.readings[0]
        for register in utility_bill.registers:
            self.readings.append(Reading.make_reading_from_register(register))

    def update_readings_from_reebill(self, reebill_readings):
        '''Updates the set of Readings associated with this ReeBill to match
        the list of registers in the given reebill_readings. Readings that do
        not have a register binding that matches a register in the utility bill
        are ignored.
        '''
        session = Session.object_session(self)
        for r in self.readings:
            session.delete(r)

        # this works even when len(self.utilbills) == 0, which is currently
        # happening in a test but should never actually happen in real life
        # TODO replace with
        # [r.register_binding for r in self.utilbill.registers]
        utilbill_register_bindings = list(chain.from_iterable(
                (r.register_binding for r in u.registers)
                for u in self.utilbills))

        self.readings = [Reading(r.register_binding, r.measure, 0,
                0, r.aggregate_function, r.unit) for r in reebill_readings
                if r.register_binding in utilbill_register_bindings]
        session.flush()

    def get_reading_by_register_binding(self, binding):
        '''Returns the first Reading object found belonging to this ReeBill
        whose 'register_binding' matches 'binding'.
        '''
        try:
            result = next(r for r in self.readings if r.register_binding == binding)
        except StopIteration:
            raise RegisterError('Unknown register binding "%s"' % binding)
        return result

    def set_renewable_energy_reading(self, register_binding, new_quantity):
        reading = self.get_reading_by_register_binding(register_binding)
        unit_string = reading.unit.lower()

        if unit_string == 'kwd':
            # for demand in PV bills, 'new_quantity' will be in kilowatts
            # (kwd); no conversion is needed.
            reading.renewable_quantity = new_quantity
        else:
            # in all other cases, 'new_quantity' will be in BTU: convert to unit
            # of the reading
            new_quantity_with_unit = new_quantity * ureg.btu
            unit = ureg.parse_expression(unit_string)
            converted_quantity = new_quantity_with_unit.to(unit)
            reading.renewable_quantity = converted_quantity.magnitude

    def get_total_renewable_energy(self, ccf_conversion_factor=None):
        return sum(convert_to_therms(
            r.renewable_quantity, r.unit,
            ccf_conversion_factor=ccf_conversion_factor) for r in self.readings)

    def get_total_conventional_energy(self, ccf_conversion_factor=None):
        return sum(convert_to_therms(
            r.conventional_quantity, r.unit,
            ccf_conversion_factor=ccf_conversion_factor) for r in self.readings)

    def _replace_charges_with_evaluations(self, evaluations):
        """Replace the ReeBill charges with data from each `Evaluation`.
        :param evaluations: a dictionary of binding: `Evaluation`
        """
        session = Session.object_session(self)
        for charge in self.charges:
            session.delete(charge)
        self.charges = []
        charge_dct = {c.rsi_binding: c for c in self.utilbill.charges}
        for binding, evaluation in evaluations.iteritems():
            charge = charge_dct[binding]
            if charge.has_charge:
                unit = '' if charge.unit is None else charge.unit
                session.add(ReeBillCharge(self, binding, charge.description,
                        charge.group, charge.quantity, evaluation.quantity,
                        charge.unit, charge.rate, charge.total,
                        evaluation.total))

    def compute_charges(self):
        """Computes and updates utility bill charges, then computes and
        updates reebill charges."""
        self.utilbill.compute_charges()
        session = Session.object_session(self)
        for charge in self.charges:
            session.delete(charge)

        # compute the utility bill charges in a context where the quantity
        # of each Register that has a corresponding Reading is replaced by
        # the hypothetical_quantity of the Reading. a Register that has no
        # corresponding Reading may still be necessary for calculating the
        # charges, so the actual quantity of that register is used.
        context = {r.register_binding: Evaluation(r.quantity)
                   for r in self.utilbill.registers}
        context.update({r.register_binding: Evaluation(r.hypothetical_quantity)
                        for r in self.readings})

        evaluated_charges = {}
        for charge in self.utilbill.ordered_charges():
            evaluation = charge.evaluate(context, update=False)
            if evaluation.exception is not None:
                raise evaluation.exception
            context[charge.rsi_binding] = evaluation
            evaluated_charges[charge.rsi_binding] = evaluation
        self._replace_charges_with_evaluations(evaluated_charges)

    @property
    def total(self):
        '''The sum of all charges on this bill that do not come from other
        bills, i.e. charges that are being charged to the customer's account on
        this bill's issue date. (This includes the late charge, which depends
        on another bill for its value but belongs to the bill on which it
        appears.) This total is what should be used to calculate the adjustment
        produced by the difference between two versions of a bill.'''
        return self.ree_charge + self.late_charge

    def get_total_actual_charges(self):
        '''Returns sum of "actual" versions of all charges.
        '''
        return sum(charge.a_total for charge in self.charges)

    def get_total_hypothetical_charges(self):
        '''Returns sum of "hypothetical" versions of all charges.
        '''
        return sum(charge.h_total for charge in self.charges)

    def get_charge_by_rsi_binding(self, binding):
        '''Returns the first ReeBillCharge object found belonging to this
        ReeBill whose 'rsi_binding' matches 'binding'.
        '''
        return next(c for c in self.charges if c.rsi_binding == binding)

    def column_dict(self):
        period_start , period_end = self.get_period()
        the_dict = super(ReeBill, self).column_dict()
        the_dict.update({
            'account': self.get_account(),
            'mailto': self.reebill_customer.bill_email_recipient,
            'hypothetical_total': self.get_total_hypothetical_charges(),
            'actual_total': self.get_total_actual_charges(),
            'billing_address': self.billing_address.to_dict(),
            'service_address': self.service_address.to_dict(),
            'period_start': period_start,
            'period_end': period_end,
            'utilbill_total': sum(u.get_total_charges() for u in self.utilbills),
            # TODO: is this used at all? does it need to be populated?
            'services': [],
            'readings': [r.column_dict() for r in self.readings]
        })

        if self.version > 0:
            if self.issued:
                the_dict['corrections'] = str(self.version)
            else:
                the_dict['corrections'] = '#%s not issued' % self.version
        else:
            the_dict['corrections'] = '-' if self.issued else '(never ' \
                                                                 'issued)'
        # wrong energy unit can make this method fail causing the reebill
        # grid to not load; see
        # https://www.pivotaltracker.com/story/show/59594888
        try:
            the_dict['ree_quantity'] = self.get_total_renewable_energy()
        except (ValueError, StopIteration) as e:
            log.error(
                "Error when getting renewable energy "
                "quantity for reebill %s:\n%s" % (
                self.id, traceback.format_exc()))
            the_dict['ree_quantity'] = 'ERROR: %s' % e.message

        return the_dict


class UtilbillReebill(Base):
    '''Class corresponding to the "utilbill_reebill" table which represents the
    many-to-many relationship between "utilbill" and "reebill".'''
    __tablename__ = 'utilbill_reebill'

    reebill_id = Column(Integer, ForeignKey('reebill.id'), primary_key=True)
    utilbill_id = Column(Integer, ForeignKey('utilbill.id'), primary_key=True)

    # there is no delete cascade in this 'relationship' because a UtilBill
    # should not be deleted when a UtilbillReebill is deleted.
    utilbill = relationship('UtilBill', backref='_utilbill_reebills')

    def __init__(self, utilbill, document_id=None):
        # UtilbillReebill has only 'utilbill' in its __init__ because the
        # relationship goes Reebill -> UtilbillReebill -> UtilBill. NOTE if the
        # 'utilbill' argument is actually a ReeBill, ReeBill's relationship to
        # UtilbillReebill will cause a stack overflow in SQLAlchemy code
        # (without this check).
        assert isinstance(utilbill, UtilBill)

        self.utilbill = utilbill
        self.document_id = document_id

    def __repr__(self):
        return (('UtilbillReebill(utilbill_id=%s, reebill_id=%s, '
                 'document_id=...%s, uprs_document_id=...%s, ') % (
                    self.utilbill_id, self.reebill_id, self.document_id[-4:],
                    self.uprs_document_id[-4:]))

class ReeBillCustomer(Base):
    __tablename__ = 'reebill_customer'

    SERVICE_TYPES = ('thermal', 'pv')
    # this is here because there doesn't seem to be a way to get a list of
    # possible values from a SQLAlchemy.types.Enum


    id = Column(Integer, primary_key=True)
    name = Column(String(45))
    discountrate = Column(Float(asdecimal=False), nullable=False)
    latechargerate = Column(Float(asdecimal=False), nullable=False)
    bill_email_recipient = Column(String(1000), nullable=False)
    service = Column(Enum(*SERVICE_TYPES), nullable=False)
    utility_account_id = Column(Integer, ForeignKey('utility_account.id'))

    utility_account = relationship('UtilityAccount', uselist=False,
        primaryjoin='ReeBillCustomer.utility_account_id==UtilityAccount.id')


    def get_discount_rate(self):
        return self.discountrate

    def get_account(self):
        return self.utility_account.account

    def set_discountrate(self, value):
        self.discountrate = value

    def get_late_charge_rate(self):
        return self.latechargerate

    def set_late_charge_rate(self, value):
        self.latechargerate = value

    def __init__(self, name='', discount_rate=0.0, late_charge_rate=0.0,
                service='thermal', bill_email_recipient='',
                utility_account=None):
        """Construct a new :class:`.Customer`.
        :param name: The name of the utility_account.
        :param account:
        :param discount_rate:
        :param late_charge_rate:
        :param bill_email_recipient: The utility_account receiving email
        address for skyline-generated bills
        :fb_utility: The :class:`.Utility` to be assigned to the the first
        `UtilityBill` associated with this utility_account.
        :fb_supplier: The :class: 'Supplier' to be assigned to the first
        'UtilityBill' associated with this utility_account
        :fb_rate_class": "first bill rate class" (see fb_utility_name)
        :fb_billing_address: (as previous)
        :fb_service address: (as previous)
        """
        self.name = name
        self.discountrate = discount_rate
        self.latechargerate = late_charge_rate
        self.bill_email_recipient = bill_email_recipient
        self.service = service
        self.utility_account = utility_account

    def __repr__(self):
        return '<ReeBillCustomer(name=%s, discountrate=%s)>' \
               % (self.name, self.discountrate)

class ReeBillCharge(Base):
    '''Table representing "hypothetical" versions of charges in reebills (so
    named because these may not have the same schema as utility bill charges).
    Note that, in the past, a set of "hypothetical charges" was associated
    with each utility bill subdocument of a reebill Mongo document, of which
    there was always 1 in practice. Now these charges are associated directly
    with a reebill, so there would be no way to distinguish between charges
    from different utility bills, if there mere multiple utility bills.
    '''
    __tablename__ = 'reebill_charge'

    id = Column(Integer, primary_key=True)
    reebill_id = Column(Integer, ForeignKey('reebill.id', ondelete='CASCADE'))
    rsi_binding = Column(String(1000), nullable=False)
    description = Column(String(1000), nullable=False)
    # NOTE alternate name is required because you can't have a column called
    # "group" in MySQL
    group = Column(String(1000), name='group_name', nullable=False)
    a_quantity = Column(Float, nullable=False)
    h_quantity = Column(Float, nullable=False)
    unit = Column(Enum(*Charge.CHARGE_UNITS), nullable=False)
    rate = Column(Float, nullable=False)
    a_total = Column(Float, nullable=False)
    h_total = Column(Float, nullable=False)

    def __init__(self, reebill, rsi_binding, description, group, a_quantity,
                 h_quantity, unit, rate, a_total, h_total):
        assert unit is not None
        self.reebill = reebill
        self.rsi_binding = rsi_binding
        self.description = description
        self.group = group
        self.a_quantity, self.h_quantity = a_quantity, h_quantity
        self.unit = unit
        self.rate = rate
        self.a_total = None if a_total is None else round(a_total, 2)
        self.h_total = None if h_total is None else round(h_total, 2)

class Reading(Base):
    '''Stores utility register readings and renewable energy offsetting the
    value of each register.
    '''
    __tablename__ = 'reading'

    id = Column(Integer, primary_key=True)
    reebill_id = Column(Integer, ForeignKey('reebill.id'))

    # identifies which utility bill register this corresponds to
    register_binding = Column(String(1000), nullable=False)

    # name of measure in OLAP database to use for getting renewable energy
    # quantity
    measure = Column(String(1000), nullable=False)

    # actual reading from utility bill
    conventional_quantity = Column(Float, nullable=False)

    # renewable energy offsetting the above
    renewable_quantity = Column(Float, nullable=False)

    aggregate_function = Column(String(15), nullable=False)

    unit = Column(Enum(*Register.PHYSICAL_UNITS), nullable=False)

    @staticmethod
    def make_reading_from_register(register):
        '''Return a new 'Reading' instance based on the given utility bill
        register  with default values for its measure name and aggregation
        function.
        :param register: Register on which this reading is based.
        '''
        return Reading(register.register_binding, "Energy Sold",
                              register.quantity, 0, "SUM",
                              register.unit)

    def __init__(self, register_binding, measure, conventional_quantity,
                 renewable_quantity, aggregate_function, unit):
        assert isinstance(register_binding, basestring)
        assert isinstance(measure, basestring)
        assert isinstance(conventional_quantity, (float, int))
        assert isinstance(renewable_quantity, (float, int))
        assert isinstance(unit, basestring)
        self.register_binding = register_binding
        self.measure = measure
        self.conventional_quantity = conventional_quantity
        self.renewable_quantity = renewable_quantity
        self.aggregate_function = aggregate_function
        self.unit = unit

    def __hash__(self):
        return hash(self.register_binding + self.measure +
                str(self.conventional_quantity) + str(self.renewable_quantity)
                + self.aggregate_function + self.unit)

    def __eq__(self, other):
        return all([
            self.register_binding == other.register_binding,
            self.measure == other.measure,
            self.conventional_quantity == other.conventional_quantity,
            self.renewable_quantity == other.renewable_quantity,
            self.aggregate_function == other.aggregate_function,
            self.unit == other.unit
        ])

    @property
    def hypothetical_quantity(self):
        return self.conventional_quantity + self.renewable_quantity

    def get_aggregation_function(self):
        '''Return the function for aggregating renewable energy values
        (float, float -> float), based on the 'aggregate_function' database
        column.
        '''
        if self.aggregate_function == 'SUM':
            return sum
        if self.aggregate_function == 'MAX':
            return max
        else:
            raise ValueError('Unknown aggregation function "%s"' %
                             self.aggregate_function)

class Payment(Base):
    __tablename__ = 'payment'

    id = Column(Integer, primary_key=True)
    reebill_customer_id = Column(Integer, ForeignKey('reebill_customer.id'), nullable=False)
    reebill_id = Column(Integer, ForeignKey('reebill.id'))
    date_received = Column(DateTime, nullable=False)
    date_applied = Column(DateTime, nullable=False)
    description = Column(String(45))
    credit = Column(Float)

    reebill_customer = relationship("ReeBillCustomer", backref=backref('payments',
        order_by=id))

    reebill = relationship("ReeBill", backref=backref('payments',
        order_by=id))

    '''date_received is the datetime when the payment was recorded.
    date_applied is the date that the payment is "for", from the customer's
    perspective. Normally these are on the same day, but an error in an old
    payment can be corrected by entering a new payment with the same
    date_applied as the old one, whose credit is the true amount minus the
    previously-entered amount.'''

    def __init__(self, reebill_customer, date_received, date_applied, description,
                 credit):
        assert isinstance(date_received, datetime)
        assert isinstance(date_applied, date)
        self.reebill_customer = reebill_customer
        self.date_received = date_received
        self.date_applied = date_applied
        self.description = description
        self.credit = credit

    def is_editable(self):
        """ Returns True or False depending on whether the payment should be
        editable. Payments should be editable as long as it is not applied to
        a reebill
        """
        today = datetime.utcnow()
        if self.reebill_id is None:
            return True
        return False

    def __repr__(self):
        return '<Payment(%s, received=%s, applied=%s, %s, %s)>' \
               % (self.reebill_customer.get_account(), self.date_received, \
                  self.date_applied, self.description, self.credit)

    def column_dict(self):
        the_dict = super(Payment, self).column_dict()
        the_dict.update(editable=self.is_editable())
        return the_dict



