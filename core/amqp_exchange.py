import json
import re
from boto.s3.connection import S3Connection
from datetime import datetime
from voluptuous import Schema, Match, Any, Invalid

from billing import config
from billing.nexusapi.nexus_util import NexusUtil
from billing.reebill.utilbill_processor import UtilbillProcessor
from billing.core.utilbill_loader import UtilBillLoader
from billing.core.pricing import FuzzyPricingModel
from billing.core.bill_file_handler import BillFileHandler
from billing.core.model import Session, Address, UtilityAccount
from billing.core.altitude import AltitudeUtility, get_utility_from_guid, \
    AltitudeGUID, update_altitude_account_guids
from billing.exc import AltitudeDuplicateError
from mq import MessageHandler, MessageHandlerManager, REJECT_MESSAGE
from mq.schemas.validators import MessageVersion, EmptyString, Date


# Voluptuos schema for validating/parsing utility bill message contents.
# specification is at
# https://docs.google.com/a/nextility.com/document/d
# /1u_YBupWZlpVr_vIyJfTeC2IaGU2mYZl9NoRwjF0MQ6c/edit

def TotalValidator():
    # Validator for the odd format of the "total" field in utility bill
    # messages: dollars and cents as a string preceded by "$", or empty.
    #
    def validate(value):
        substr = re.match('^\$\d*\.?\d{1,2}|$', value).group(0)
        if substr is None:
            raise Invalid('Invalid "total" string: "%s"' % value, value, state)
        return None if substr == '' else float(substr[1:])
    return validate

def DueDateValidator():
    # Validator for "due_date" field in utility bill
    # messages. ISO-8601 datetime string or empty string converted to Date or
    # None
    def validate(value):
        if value == '':
            return None
        try:
            dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            raise Invalid('Could not parse "due_date" string: %s' % value)
        return dt.date()
    return validate


UtilbillMessageSchema = Schema({
    'utility_account_number': basestring,
    'sha256_hexdigest': Match(BillFileHandler.HASH_DIGEST_REGEX),
    'due_date': DueDateValidator(),
    'total': TotalValidator(),
    'service_address': basestring,
    'utility_provider_guid': Match(AltitudeGUID.REGEX),
    'account_guids': [basestring],
    'message_version': MessageVersion(1)
}, required=True)


class BillingHandler(MessageHandler):

    def __init__(self, *args, **kwargs):
        super(BillingHandler, self).__init__(*args, **kwargs)
        s3_connection = S3Connection(
                config.get('aws_s3', 'aws_access_key_id'),
                config.get('aws_s3', 'aws_secret_access_key'),
                is_secure=config.get('aws_s3', 'is_secure'),
                port=config.get('aws_s3', 'port'),
                host=config.get('aws_s3', 'host'),
                calling_format=config.get('aws_s3', 'calling_format'))
        utilbill_loader = UtilBillLoader(Session())
        self.pricing_model = FuzzyPricingModel(
            utilbill_loader,  logger=self.logger
        )
        # TODO: ugly. maybe put entire url_format in config file.
        url_format = '%s://%s:%s/%%(bucket_name)s/%%(key_name)s' % (
                'https' if config.get('aws_s3', 'is_secure') is True else
                'http', config.get('aws_s3', 'host'),
                config.get('aws_s3', 'port'))
        self.bill_file_handler = BillFileHandler(
            s3_connection, config.get('aws_s3', 'bucket'), utilbill_loader,
            url_format)
        self.nexus_util = NexusUtil(
            config.get('reebill', 'nexus_web_host')
        )
        self.utilbill_processor = UtilbillProcessor(
            self.pricing_model, self.bill_file_handler, self.nexus_util,
            logger=self.logger)

# TODO: this code is not used yet (and not tested). it was originally decided
#  that it was necessary to synchronize utilities between altitude and
# billing databases, but this was later un-decided, so nothing is being done
# about it for now. see BILL-3784.
class ConsumeUtilityGuidHandler(BillingHandler):

    def handle(self, message):
        name, guid = message['name'], message['utility_provider_guid']

        # TODO: this may not be necessary because unique constraint in the
        # database can take care of preventing duplicates
        s = Session()
        if s.query(AltitudeUtility).filter_by(guid=guid).count() != 0:
            raise AltitudeDuplicateError(
                'Altitude utility "%s" already exists with name "%s"' % (
                    guid, name))

        new_utility = utilbill_processor.create_utility(name)
        s.add(AltitudeUtility(new_utility, guid))
        s.commit()


class ConsumeUtilbillFileHandler(BillingHandler):
    # on_error = REJECT_MESSAGE
    message_schema = UtilbillMessageSchema

    def handle(self, message):
        s = Session()
        utility = get_utility_from_guid(message['utility_provider_guid'])
        utility_account = s.query(UtilityAccount).filter_by(
            account_number=message['utility_account_number']).one()
        sha256_hexdigest = message['sha256_hexdigest']
        total = message['total']
        due_date = message['due_date']
        service_address_street = message['service_address']
        account_guids = message['account_guids']

        self.utilbill_processor.create_utility_bill_with_existing_file(
            utility_account, utility, sha256_hexdigest,
            target_total=total,
            service_address=Address(street=service_address_street),
            due_date=due_date)
        update_altitude_account_guids(utility_account, account_guids)
        s.commit()


if __name__ == "__main__":
    from billing import init_config, init_model, init_logging
    from os.path import join, realpath, dirname
    # TODO: is it necessary to specify file path?
    p = join(dirname(dirname(realpath(__file__))), 'settings.cfg')
    init_logging(filepath=p)
    init_config(filepath=p)
    init_model()

    from billing import config
    exchange_name = config.get('amqp', 'exchange')
    utilbill_routing_key = config.get('amqp', 'utilbill_routing_key')
    mgr = MessageHandlerManager()
    mgr.attach_message_handler(
        exchange_name, utilbill_routing_key, ConsumeUtilbillFileHandler
    )
    mgr.run()