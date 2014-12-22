from sqlalchemy import desc
from core.model import UtilBill, UtilityAccount
from exc import NoSuchBillException

class UtilBillLoader(object):
    '''Data access object for utility bills, used to hide database details
    from other classes so they can be more easily tested.
    '''
    def __init__(self, session):
        ''''session': SQLAlchemy session object to be used for database
        queries.
        '''
        self._session = session

    def get_utilbill_by_id(self, utilbill_id):
        '''Return utilbill with the given id.'''
        return self._session.query(UtilBill).filter_by(id=utilbill_id).one()

    def load_real_utilbills(self, **kwargs):
        '''Returns a cursor of UtilBill objects matching the criteria given
        by **kwargs. Only "real" utility bills (i.e. UtilBill objects with
        state Estimated or lower) are included.
        '''
        cursor = self._session.query(UtilBill).filter(
            UtilBill.state <= UtilBill.Estimated)
        for key, value in kwargs.iteritems():
            cursor = cursor.filter(getattr(UtilBill, key) == value)
        return cursor

    def get_last_real_utilbill(self, account, end=None, service=None,
                               utility=None, rate_class=None, processed=None):
        '''Returns the latest-ending UtilBill, optionally limited to those
        whose end date is before/on 'end', and optionally with
        the given service, utility, rate class, and 'processed' status.
        '''
        utility_account = self._session.query(UtilityAccount).filter_by(account=account) \
            .one()
        cursor = self._session.query(UtilBill) \
            .filter(UtilBill.utility_account == utility_account)
        if end is not None:
            cursor = cursor.filter(UtilBill.period_end <= end)
        if service is not None:
            cursor = cursor.filter(UtilBill.service == service)
        if utility is not None:
            cursor = cursor.filter(UtilBill.utility == utility)
        if rate_class is not None:
            cursor = cursor.filter(UtilBill.rate_class == rate_class)
        if processed is not None:
            assert isinstance(processed, bool)
            cursor = cursor.filter(UtilBill.processed == processed)
        result = cursor.order_by(desc(UtilBill.period_end)).first()
        if result is None:
            raise NoSuchBillException
        return result

    def count_utilbills_with_hash(self, hash):
        '''Return the number of utility bills having the given SHA-256 hash.
        '''
        return self._session.query(UtilBill).filter_by(
            sha256_hexdigest=hash).count()

    def get_utilbills_for_account_id(self, utility_account_id):
        '''Return an iterator containing utility bills whose UtilityAccount
        is identified by utility_account_id.
        '''
        return self._session.query(UtilBill).join(
            UtilityAccount).filter(UtilityAccount.id==utility_account_id)

