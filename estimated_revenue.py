import sys
from datetime import date, datetime
from collections import defaultdict
from skyliner.splinter import Splinter
from skyliner.skymap.monguru import Monguru
from billing.processing.process import Process
from billing.dateutils import estimate_month, month_offset, months_of_past_year, date_generator
from billing.nexus_util import NexusUtil
from billing.processing.rate_structure import RateStructureDAO
from billing.processing import state
from billing.processing.state import StateDB
from billing.mongo import ReebillDAO
from billing.dictutils import deep_map
from decimal import Decimal

import pprint
pp = pprint.PrettyPrinter(indent=4).pprint
sys.stdout = sys.stderr

class EstimatedRevenue(object):

    def __init__(self, state_db, reebill_dao, ratestructure_dao, splinter):
        self.state_db = state_db
        self.reebill_dao = reebill_dao
        self.splinter = splinter
        self.monguru = splinter.get_monguru()
        self.ratestructure_dao = ratestructure_dao
        self.process = Process(None, self.state_db, self.reebill_dao, None,
                self.splinter, self.monguru)

        # pre-load all the olap ids of accounts for speed (each one requires an
        # HTTP request)
        nexus_util = NexusUtil()
        session = self.state_db.session()
        self.olap_ids = dict([
            (account, nexus_util.olap_id(account)) for account in
            self.state_db.listAccounts(session)
        ])
        session.commit()

    def report(self, session):
        '''Returns a dictionary containing data about real and renewable energy
        charges in reebills for all accounts in the past year. Keys are (year,
        month) tuples. Each value is a dictionary whose key is an account (or
        'total') and whose value is a dictionary containing real or estimated
        renewable energy charge in all reebills whose approximate calendar
        month was or probably will be that month, and a boolean representing
        whether that value was estimated.

        If there was an error, an Exception is put in the dictionary with the
        key "error", and "value" and "estimated" keys are omitted.
        The monthly total only includes accounts for which there wasn't an
        error.

        Dictionary structure is like this:
        {
            10001 : {
                (2012,1): {
                    "value": $,
                    "estimated": False
                },
                (2012,2): {
                    "value": $,
                    "estimated": True
                },
                (2012,3): {
                    "error": "Error Message"
                },
                ...
            }
            ...
        }
        '''
        print 'Generating estimated revenue report'

        # dictionary account -> ((year, month) -> { monthtly data })
        # by default, value is 0 and it's not estimated
        data = defaultdict(lambda: defaultdict(lambda: {'value':0., 'estimated': False}))

        accounts = self.state_db.listAccounts(session)
        # accounts = ['10024'] # TODO enable all accounts when this is faster
        now = datetime.utcnow()
        for account in accounts:
            last_seq = self.state_db.last_sequence(session, account)
            for year, month in months_of_past_year(now.year, now.month):
                try:
                    # get sequences of bills this month
                    sequences = self.process.sequences_for_approximate_month(
                            session, account, year, month)

                    # for each sequence, add that bill's real or estimated
                    # renewable energy charge to the total for this month
                    for seq in sequences:
                        if seq <= last_seq:
                            data[account][year, month]['value'] += float(
                                    self.reebill_dao.load_reebill(account,
                                    seq).ree_charges)
                        else:
                            data[account][year, month]['value'] += self.\
                                    _estimate_ree_charge(session, account,
                                    year, month)
                            # a single estimated bill makes the whole month
                            # estimated
                            data[account][year, month]['estimated'] = True
                except Exception as e:
                    data[account][year, month] = {'error': e}
                    print '%s %s-%s ERROR: %s' % (account, year, month, e)

        # compute total
        for year, month in months_of_past_year(now.year, now.month):
            # add up revenue for all accounts in this month
            data['total'][year, month]['value'] = sum(data[acc][year, month].get('value', 0)
                    for acc in accounts if not isinstance(data[acc]
                    [year, month], Exception))

            # total value is estimated iff any estimated bills contributed to
            # it (errors are treated as non-estimated zeroes). this will almost
            # certainly be true because utility bills for the present month
            # have not even been received.
            data['total'][year, month]['estimated'] = any(data[acc][year,
                month].get('estimated',False) == True for acc in accounts)

        return data


    def _estimate_ree_charge(self, session, account, year, month):
        '''Returns an estimate of renewable energy charges for a bill that
        would be issed for the given account in the given month. The month must
        exceed the approximate month of the account's last real bill.'''
        # make sure (year, month) is not the approximate month of a real bill
        last_sequence = self.state_db.last_issued_sequence(session, account)
        last_reebill = self.reebill_dao.load_reebill(account, last_sequence)
        last_approx_month = estimate_month(last_reebill.period_begin,
                last_reebill.period_end)
        if (year, month) <= last_approx_month:
            raise ValueError(('%s does not exceed last approximate billing '
                'month for account %s, which is %s') % ((year, month), account,
                last_approximate_month))
        
        # the period over which to get energy sold is the entire calendar month
        # up to the present, unless this is the month following that of the
        # last real bill, in which case the period starts at the end of the
        # last bill's period (which may precede or follow the first day of this
        # month).
        if (year, month) == month_offset(*(last_approx_month + (1,))):
            start = last_reebill.period_end
        else:
            start = date(year, month, 1)
        month_end_year, month_end_month = month_offset(year, month, 1)
        end = min(date.today(), date(month_end_year, month_end_month, 1))
        
        # get energy sold during that period
        olap_id = self.olap_ids[account]
        energy_sold_btu = 0
        for day in date_generator(start, end):
            try:
                daily_sold_btu = self.monguru.get_data_for_day(olap_id,
                        day).energy_sold
                if daily_sold_btu == None:
                    # measure does not exist in the olap doc
                    daily_sold_btu = 0
            except ValueError:
                # olap doc is missing
                daily_sold_btu = 0
            energy_sold_btu += daily_sold_btu
        energy_sold_therms = energy_sold_btu / 100000.

        # now we figure out how much that energy costs. if the utility bill(s)
        # for this reebill are present, we could get them with
        # state.guess_utilbills_and_end_date(), and then use their rate
        # structure(s) to calculate the cost. but currently there are never any
        # utility bills until a reebill has been created. so there will never
        # be rate structure to use unless there is actually a reebill.

        # if last_reebill has zero renewable energy, replace it with the newest
        # bill that has non-zero renewable energy, if there is one
        while last_reebill.total_renewable_energy(
                ccf_conversion_factor=Decimal("1.0")) == 0:
            if last_reebill.sequence == 0:
                raise Exception(('No reebills with non-zero renewable '
                        'energy.') % account)
            last_reebill = self.reebill_dao.load_reebill(account,
                    last_reebill.sequence - 1)

        # to approximate the price per therm of renewable energy in the last
        # bill, we can just divide its renewable energy charge (the price at
        # which its energy was sold to the customer, including the discount) by
        # the quantity of renewable energy
        try:
            # TODO: 28825375 - ccf conversion factor is as of yet unavailable so 1 is assumed.
            ree_charges = float(last_reebill.ree_charges)
            total_renewable_energy = float(last_reebill.total_renewable_energy(
                    ccf_conversion_factor=Decimal("1.0")))
            unit_price = ree_charges / total_renewable_energy
            energy_price = unit_price * energy_sold_therms
            print '%s/%s %s to %s: $%.2f/therm (from #%s) * %.3f therms = $%.2f' % (
                    account, olap_id, start, end, unit_price,
                    last_reebill.sequence, energy_sold_therms, energy_price)
        except Exception as e:
            raise
        
        return energy_price


if __name__ == '__main__':
    state_db = StateDB(
        host='localhost',
        database='skyline_dev',
        user='dev',
        password='dev'
    )
    reebill_dao = ReebillDAO({
        'host': 'localhost',
        'port': 27017,
        'database': 'skyline',
        'collection': 'reebills',
    })
    ratestructure_dao = RateStructureDAO({
        'host': 'localhost',
        'port': 27017,
        'database': 'skyline',
        'collection': 'ratestructure',
    })
    splinter = Splinter('http://duino-drop.appspot.com/', 'tyrell', 'dev')
    session = state_db.session()
    er = EstimatedRevenue(state_db, reebill_dao, ratestructure_dao,
            splinter)

    data = er.report(session)

    ## print a table
    #all_months = sorted(set(reduce(lambda x,y: x+y, [data[account].keys() for
        #account in data], [])))
    #now = date.today()
    #data_months = months_of_past_year(now.year, now.month)
    #print '      '+('%10s '*12) % tuple(map(str, data_months))
    #for account in sorted(data.keys()):
        #print account + '%10.1f '*12 % tuple([data[account].get((year, month),
                #0) for (year, month) in data_months])
    #print 'total' + '%10.1f '*12 % tuple([sum(float(data[account].get((year, month),
            #0)) for account in data) for (year, month) in data_months])

    data = deep_map(lambda x: dict(x) if type(x) == defaultdict else x, data)
    data = deep_map(lambda x: dict(x) if type(x) == defaultdict else x, data)
    pp(data)

    session.commit()
