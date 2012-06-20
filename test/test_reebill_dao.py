#!/usr/bin/python
import unittest
import pymongo
import sqlalchemy
from datetime import date, datetime, timedelta
from billing import dateutils, mongo
from billing.processing.state import StateDB
from billing.processing.db_objects import ReeBill, Customer, UtilBill
import MySQLdb
from billing.test import example_data
from billing.mongo import NoSuchReeBillException

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint

class ReebillDAOTest(unittest.TestCase):

    def setUp(self):
        # this method runs before every test.
        # clear SQLAlchemy mappers so StateDB can be instantiated again
        sqlalchemy.orm.clear_mappers()

        # customer database ("test" database has already been created with
        # empty customer table)
        self.state_db = StateDB(**{
            'user':'dev',
            'password':'dev',
            'host':'localhost',
            'database':'test'
        })

        self.reebill_dao = mongo.ReebillDAO(self.state_db, **{
            'billpath': '/db-dev/skyline/bills/',
            'database': 'test',
            'utilitybillpath': '/db-dev/skyline/utilitybills/',
            'collection': 'test_reebills',
            'host': 'localhost',
            'port': 27017
        })
        
        ## clear out tables in mysql test database (not relying on StateDB)
        mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test')
        c = mysql_connection.cursor()
        c.execute("delete from payment")
        c.execute("delete from utilbill")
        c.execute("delete from rebill")
        c.execute("delete from customer")
        # (note that status_days_since, status_unbilled are views and you
        # neither can nor need to delete from them)
        mysql_connection.commit()

        # insert one customer
        session = self.state_db.session()
        # name, account, discount rate, late charge rate
        customer = Customer('Test Customer', '99999', .12, .34)
        session.add(customer)
        session.commit()

    def tearDown(self):
        # clear out mongo test database
        mongo_connection = pymongo.Connection('localhost', 27017)
        mongo_connection.drop_database('test')

        # clear out tables in mysql test database (not relying on StateDB)
        mysql_connection = MySQLdb.connect('localhost', 'dev', 'dev', 'test')
        c = mysql_connection.cursor()
        c.execute("delete from payment")
        c.execute("delete from utilbill")
        c.execute("delete from rebill")
        c.execute("delete from customer")
        mysql_connection.commit()

    def test_load_reebill(self):
        # put some reebills in, including non-0 versions
        b0 = example_data.get_reebill('99999', 0, version=0)
        b1 = example_data.get_reebill('99999', 1, version=0)
        b1_1 = example_data.get_reebill('99999', 1, version=1)
        b1_2 = example_data.get_reebill('99999', 1, version=2)
        b2 = example_data.get_reebill('99999', 2, version=0)
        b3 = example_data.get_reebill('99999', 3, version=0)
        b3_1 = example_data.get_reebill('99999', 3, version=1)

        b1.issue_date = date(2012,1,1)
        b1_1.issue_date = date(2012,2,15)
        b1_2.issue_date = date(2012,3,15)
        b2.issue_date = date(2012,2,1)
        b3.issue_date = date(2012,3,1)
        b3_1.issue_date = date(2012,4,15)

        self.reebill_dao.save_reebill(b0)
        self.reebill_dao.save_reebill(b1)
        self.reebill_dao.save_reebill(b1_1)
        self.reebill_dao.save_reebill(b1_2)
        self.reebill_dao.save_reebill(b2)
        self.reebill_dao.save_reebill(b3)
        self.reebill_dao.save_reebill(b3_1)

        # with no extra args to load_reebill(), maximum version should come out
        b0_max = self.reebill_dao.load_reebill('99999', 0)
        b1_max = self.reebill_dao.load_reebill('99999', 1)
        b2_max = self.reebill_dao.load_reebill('99999', 2)
        b3_max = self.reebill_dao.load_reebill('99999', 3)
        self.assertEqual(0, b0_max.sequence)
        self.assertEqual(0, b0_max.version)
        self.assertEqual(1, b1_max.sequence)
        self.assertEqual(2, b1_max.version)
        self.assertEqual(2, b2_max.sequence)
        self.assertEqual(0, b2_max.version)
        self.assertEqual(3, b3_max.sequence)
        self.assertEqual(1, b3_max.version)

        # try getting specific versions
        b1_1 = self.reebill_dao.load_reebill('99999', 1, version=1)
        b1_2 = self.reebill_dao.load_reebill('99999', 1, version=2)
        b3_1 = self.reebill_dao.load_reebill('99999', 3, version=1)
        self.assertEqual(1, b1_1.sequence)
        self.assertEqual(1, b1_1.version)
        self.assertEqual(1, b1_2.sequence)
        self.assertEqual(2, b1_2.version)
        self.assertEqual(1, b3_1.version)
        b0_max = self.reebill_dao.load_reebill('99999', 0, version='max')
        b1_max = self.reebill_dao.load_reebill('99999', 1, version='max')
        b2_max = self.reebill_dao.load_reebill('99999', 2, version='max')
        b3_max = self.reebill_dao.load_reebill('99999', 3, version='max')
        self.assertEqual(0, b0_max.version)
        self.assertEqual(2, b1_max.version)
        self.assertEqual(0, b2_max.version)
        self.assertEqual(1, b3_max.version)

        # get versions by issue date:
        # when date precedes all bills, version should always be max
        self.assertEqual(0, self.reebill_dao.load_reebill('99999', 0, version=date(2011,1,1)).version)
        self.assertEqual(2, self.reebill_dao.load_reebill('99999', 1, version=date(2011,1,1)).version)
        self.assertEqual(0, self.reebill_dao.load_reebill('99999', 2, version=date(2011,1,1)).version)
        self.assertEqual(1, self.reebill_dao.load_reebill('99999', 3, version=date(2011,1,1)).version)
        # when date follows all bills, version should always be max
        self.assertEqual(0, self.reebill_dao.load_reebill('99999', 0, version=date(2013,1,1)).version)
        self.assertEqual(2, self.reebill_dao.load_reebill('99999', 1, version=date(2013,1,1)).version)
        self.assertEqual(0, self.reebill_dao.load_reebill('99999', 2, version=date(2013,1,1)).version)
        self.assertEqual(1, self.reebill_dao.load_reebill('99999', 3, version=date(2013,1,1)).version)
        # date between issue dates of 1-0 and 1-1
        self.assertEqual(0, self.reebill_dao.load_reebill('99999', 1, version=date(2012,1,15)).version)
        # date between issue dates of 1-1 and 1-2
        self.assertEqual(1, self.reebill_dao.load_reebill('99999', 1, version=date(2012,3,1)).version)
        # date between issue dates of 3-0 and 3-1
        self.assertEqual(0, self.reebill_dao.load_reebill('99999', 3, version=date(2012,4,1)).version)

        # error when reebill is not found
        self.assertRaises(NoSuchReeBillException, self.reebill_dao.load_reebill, '10003', 1)
        self.assertRaises(NoSuchReeBillException, self.reebill_dao.load_reebill, '99999', 10)
        self.assertRaises(NoSuchReeBillException, self.reebill_dao.load_reebill, '99999', 1, version=5)

if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()
