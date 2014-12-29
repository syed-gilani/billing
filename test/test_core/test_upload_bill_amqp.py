'''Integration tests for receiving data associated with an existing utility
bill file over AMQP. The RabbitMQ server is not started by this test so it
must be running separately before the test starts.

# TODO: a lot of the behavior that is tested in here could be tested at a
unit-test level. Also, as much as possible of the real code that is used to
process AMQP messages should be covered here, which means using
run_amqp_consuers.py if possible.
'''
from StringIO import StringIO
from datetime import date
import json

from billing.core.amqp_exchange import consume_utilbill_file, \
    create_dependencies
from billing.core.model import Session, UtilityAccount
from billing.core.altitude import AltitudeUtility, AltitudeGUID, AltitudeAccount
from billing.core.utilbill_loader import UtilBillLoader
from billing.test.setup_teardown import TestCaseWithSetup
from billing.exc import DuplicateFileError
from billing.test.testing_utils import clean_up_rabbitmq

class TestUploadBillAMQP(TestCaseWithSetup):

    def setUp(self):
        super(TestUploadBillAMQP, self).setUp()

        self.connection, self.channel, self.exchange_name, self.queue_name, \
            self.utilbill_processor = create_dependencies()
        print self.exchange_name, self.queue_name
        self.utilbill_loader = UtilBillLoader(Session())

        clean_up_rabbitmq(self.connection, self.queue_name)

    def tearDown(self):
        # channel must be closed before trying to purge the queue, otherwise
        # any un-acked messages remain in an "unacked" rather than "ready"
        # state and will not get removed when queue_purge is called. (these
        # can always be removed in setUp because all "unacked" messages
        # become "ready", and thus purgeable, when the client process exits.)
        # a separate channel should be used to purge the queue so the channel
        # associated with the "unacked" messages can be closed.
        self.channel.close()
        clean_up_rabbitmq(self.connection, self.queue_name)
        self.connection.close()
        super(self.__class__, self).tearDown()

    def test_upload_bill_amqp(self):
        # put the file in place
        the_file = StringIO('test data')
        file_hash = self.utilbill_processor.bill_file_handler.upload_file(
            the_file)

        # no UtilBills exist yet with this hash
        self.assertEqual(0, self.utilbill_loader.count_utilbills_with_hash(
            file_hash))

        # altitude GUID entities must exist
        s = Session()
        utility_account = s.query(UtilityAccount).filter_by(
            account='99999').one()
        utility = utility_account.fb_utility
        guid_a, guid_b = 'A' * AltitudeGUID.LENGTH, 'B' * AltitudeGUID.LENGTH
        s.add_all([AltitudeUtility(utility, guid_a),
                   AltitudeUtility(utility, guid_b),
                   ])

        # two messages with the same sha256_hexigest: the first one will
        # cause a UtilBill to be created, but the second will cause a
        # DuplicateFileError to be raised. the second message also checks the
        # "empty" values that are allowed for some fields in the message.
        message1 = json.dumps(dict(
            utility_account_number='1',
            utility_provider_guid=guid_a,
            sha256_hexdigest=file_hash,
            due_date='2014-09-30T18:00:00',
            total='$231.12',
            service_address='123 Hollywood Drive',
            account_guids=['C' * AltitudeGUID.LENGTH,
                           'D' * AltitudeGUID.LENGTH]))
        self.channel.basic_publish(exchange=self.exchange_name,
                                   routing_key=self.queue_name, body=message1)
        message2 = json.dumps(dict(
            utility_account_number='2',
            utility_provider_guid=guid_b,
            sha256_hexdigest=file_hash,
            due_date='',
            total='',
            service_address='',
            account_guids=[]))
        self.channel.basic_publish(exchange=self.exchange_name,
                                   routing_key=self.queue_name, body=message2)

        # receive message: this not only causes the callback function to be
        # registered, but also calls it for any messages that are already
        # present when it is registered. any messages that are inserted after
        # "basic_consume" is called will not be processed until after the
        # test is finished, so we can't check for them.
        with self.assertRaises(DuplicateFileError):
            consume_utilbill_file(self.channel, self.queue_name,
                                  self.utilbill_processor)

        # make sure the data have been received. we can only check for the
        # final state after all messages have been processed, not the
        # intermediate states after receiving each individual message. that's
        # not ideal, but not a huge problem because we also have unit testing.
        self.assertEqual(1, self.utilbill_loader.count_utilbills_with_hash(
            file_hash))

        # check metadata that were provided with the bill:
        u = self.utilbill_loader.get_last_real_utilbill(utility_account.account)
        self.assertEqual(date(2014, 9, 30), u.due_date)
        self.assertEqual(231.12, u.target_total)
        self.assertEqual('123 Hollywood Drive', u.service_address.street)
        self.assertEqual('', u.service_address.city)
        self.assertEqual('', u.service_address.state)
        self.assertEqual('', u.service_address.postal_code)

        altitude_accounts = s.query(AltitudeAccount).all()
        self.assertEqual(2, len(altitude_accounts))
        for aa in altitude_accounts:
            self.assertEqual(utility_account, aa.utility_account)