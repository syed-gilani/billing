import sys
import os
import unittest
import operator
from StringIO import StringIO
import ConfigParser
import logging
import pymongo
from bson import ObjectId
import sqlalchemy
import mongoengine
from skyliner.splinter import Splinter
from skyliner.skymap.monguru import Monguru
from datetime import date, datetime, timedelta
from billing.util import dateutils
from billing.processing import mongo
from billing.processing.session_contextmanager import DBSession
from billing.util.dateutils import estimate_month, month_offset
from billing.processing import rate_structure2
from billing.processing.process import Process, IssuedBillError
from billing.processing.state import StateDB, ReeBill, Customer, UtilBill
from billing.processing.billupload import BillUpload
from billing.util.dictutils import deep_map
import MySQLdb
from billing.util.mongo_utils import python_convert
from billing.test import example_data
from skyliner.mock_skyliner import MockSplinter, MockMonguru
from billing.util.nexus_util import MockNexusUtil
from billing.processing.mongo import NoSuchBillException
from billing.processing.exceptions import BillStateError
from billing.processing import fetch_bill_data as fbd

class TestCaseWithSetup(unittest.TestCase):
    '''Contains setUp/tearDown code for all test cases that need to use ReeBill
    databases.'''

    def setUp(self):
        '''Sets up "test" databases in Mongo and MySQL, and crates DAOs:
        ReebillDAO, RateStructureDAO, StateDB, Splinter, Process,
        NexusUtil.'''
        # show long diffs for failed dict equality assertions
        self.maxDiff = None

        # clear SQLAlchemy mappers so StateDB can be instantiated again
        #sqlalchemy.orm.clear_mappers()

        # everything needed to create a Process object
        config_file = StringIO('''[runtime]
integrate_skyline_backend = true
[billimages]
bill_image_directory = /tmp/test/billimages
show_reebill_images = true
[billdb]
billpath = /tmp/test/db-test/skyline/bills/
database = test
utilitybillpath = /tmp/test/db-test/skyline/utilitybills/
utility_bill_trash_directory = /tmp/test/db-test/skyline/utilitybills-deleted
collection = reebills
host = localhost
port = 27017
''')
        self.config = ConfigParser.RawConfigParser()
        self.config.readfp(config_file)
        self.billupload = BillUpload(self.config, logging.getLogger('test'))
        self.splinter = MockSplinter(deterministic=True)
        
        # temporary hack to get a bill that's always the same
        # this bill came straight out of mongo (except for .date() applied to
        # datetimes)
        ISODate = lambda s: datetime.strptime(s, dateutils.ISO_8601_DATETIME)
        true, false = True, False

        # customer database ("test" database has already been created with
        # empty customer table)
        statedb_config = {
            'host': 'localhost',
            'database': 'test',
            'user': 'dev',
            'password': 'dev'
        }

        # clear out tables in mysql test database (not relying on StateDB)
        mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test')
        c = mysql_connection.cursor()
        c.execute("delete from payment")
        c.execute("delete from reebill")
        c.execute("delete from utilbill")
        c.execute("delete from customer")
        # (note that status_days_since is a view and you neither can nor need
        # to delete from it)
        mysql_connection.commit()

        # insert three customers
        self.state_db = StateDB(**statedb_config)
        session = self.state_db.session()
        # name, account, discount rate, late charge rate
        customer = Customer('Test Customer', '99999', .12, .34,
                '000000000000000000000001')
        session.add(customer)
        customer = Customer('Test Customer2', '99998', .32, .31,
                '000000000000000000000002')
        session.add(customer)
        customer = Customer('Test Customer3', '99997', .21, .22,
                '000000000000000000000003')
        session.add(customer)
        session.commit()

        # set up logger, but ingore all log output
        logger = logging.getLogger('test')
        logger.addHandler(logging.NullHandler())


        mongoengine.connect('test', host='localhost', port=27017,
                alias='utilbills')
        mongoengine.connect('test', host='localhost', port=27017,
                alias='ratestructure')

        # insert template utilbill document for the customers in Mongo
        db = pymongo.Connection('localhost')['test']
        utilbill = example_data.get_utilbill_dict('99999',
                start=date(1900,01,01), end=date(1900,02,01),
                utility='washgas', service='gas')
        utilbill['_id'] = ObjectId('000000000000000000000001')
        db.utilbills.save(utilbill)
        utilbill = example_data.get_utilbill_dict('99998',
                start=date(1900,01,01), end=date(1900,02,01),
                utility='washgas', service='gas')
        utilbill['_id'] = ObjectId('000000000000000000000002')
        db.utilbills.save(utilbill)
        utilbill = example_data.get_utilbill_dict('99997',
                start=date(1900,01,01), end=date(1900,02,01),
                utility='washgas', service='gas')
        utilbill['_id'] = ObjectId('000000000000000000000003')
        db.utilbills.save(utilbill)

        self.reebill_dao = mongo.ReebillDAO(self.state_db,
                pymongo.Connection('localhost', 27017)['test'])

        self.rate_structure_dao = rate_structure2.RateStructureDAO(
                logger=logger)

        self.nexus_util = MockNexusUtil([
            {
                'billing': '99999',
                'olap': 'example-1',
                'casualname': 'Example',
                'primus': '1785 Massachusetts Ave.',
            },
            {
                'billing': '99998',
                'olap': 'example-2',
                'casualname': 'Example2',
                'primus': '1600 Pennsylvania Ave.',
            },
            {
                'billing': '99997',
                'olap': 'example-3',
                'casualname': 'Example3',
                'primus': '101 Independence Ave',
            },
        ])
        self.process = Process(self.state_db, self.reebill_dao,
                self.rate_structure_dao, self.billupload, self.nexus_util,
                self.splinter, logger=logger)

    def tearDown(self):
        '''Clears out databases.'''
        # clear out mongo test database
        mongo_connection = pymongo.Connection('localhost', 27017)
        mongo_connection.drop_database('test')

        # clear out tables in mysql test database (not relying on StateDB)
        mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test')
        c = mysql_connection.cursor()
        c.execute("delete from payment")
        c.execute("delete from reebill")
        c.execute("delete from utilbill")
        c.execute("delete from customer")
        mysql_connection.commit()

if __name__ == '__main__':
    unittest.main()
