#!/usr/bin/python
import sys
from mock import Mock
import unittest
from StringIO import StringIO
import ConfigParser
import logging
import os
import shutil
import errno
from datetime import date, datetime, timedelta
from billing.processing.billupload import BillUpload

import pprint
pp = pprint.PrettyPrinter(indent=1).pprint

class BillUploadTest(unittest.TestCase):
    # TODO: this should be a unit test. make it one!

    def setUp(self):
        config_file = StringIO('''
[billimages]
bill_image_directory = /tmp/test/billimages
show_reebill_images = true
[billdb]
billpath = /tmp/test/db-test/skyline/bills/
database = skyline
utilitybillpath = /tmp/test/db-test/skyline/utilitybills/
utility_bill_trash_directory = /tmp/test/db-test/skyline/utilitybills-deleted
collection = reebills
host = localhost
port = 27017
''')
        config = ConfigParser.RawConfigParser()
        config.readfp(config_file)
        self.billupload = BillUpload(config, logging.getLogger('billupload_test'))

        # ensure that test directory exists and is empty
        try:
            shutil.rmtree('/tmp/test')
        except OSError as e:
            if e.errno == errno.EEXIST:
                pass
        os.mkdir('/tmp/test')

        self.utilbill = Mock()
        self.utilbill.period_start = date(2012,1,1)
        self.utilbill.period_end = date(2012,2,1)
        self.utilbill.customer.account = '99999'

    def tearDown(self):
        # remove test directory
        shutil.rmtree('/tmp/test')

    @unittest.skip("soon these files won't be moved anymore")
    def test_move_utilbill_file(self):
        # 3 utility bills with different dates, extensions, and states
        situations = [
            ('.pdf', date(2012,1,1), date(2012,2,1)),
            ('.abcdef', date(2012,2,1), date(2012,3,1)),
            ('', date(2012,3,1), date(2012,4,1))
        ]

        for extension, start, end in situations:
            # bill dates will be moved forward 1 day
            new_start, new_end = start + timedelta(1), end + timedelta(1)

            path = self.billupload.get_utilbill_file_path(self.utilbill,
                    extension=extension)
            new_path = self.billupload.get_utilbill_file_path(self.utilbill,
                    new_end, extension=extension)

            # neither old path nor new path should exist yet
            assert not any([os.access(path, os.F_OK), os.access(new_path, os.F_OK)])

            # ensure that parent directories of bill file exist, then create
            # bill file itself with some text in it
            try:
                os.makedirs(os.path.split(path)[0])
            except OSError as e:
                if e.errno == errno.EEXIST:
                    pass
            with open(path, 'w') as bill_file:
                bill_file.write('this is a test')

            # move the file
            self.billupload.move_utilbill_file(self.utilbill, new_start,
                    new_end)

            # new file should exist and be readable and old should not
            self.assertTrue(os.access(new_path, os.R_OK))
            self.assertFalse(os.access(path, os.F_OK))

            # new file should also be findable with extension and without
            self.assertEqual(new_path,
                    self.billupload.get_utilbill_file_path(self.utilbill,
                                                           new_start, new_end))
            self.assertEqual(new_path,
                    self.billupload.get_utilbill_file_path(self.utilbill,
                                       new_start, new_end, extension=extension))

    def test_delete_utilbill_file(self):
        start, end = date(2012,1,1), date(2012,2,1)
        path = self.billupload.get_utilbill_file_path(self.utilbill,
                                                      extension='.pdf')

        # path should not exist yet, and the trash directory should be empty
        assert not os.access(path, os.F_OK)
        for root, dirs, files in os.walk(self.billupload.utilbill_trash_dir):
            assert (dirs, files) == ([], [])

        # create parent directories of bill file, then create bill file itself
        # with some text in it
        os.makedirs(os.path.split(path)[0])
        with open(path, 'w') as bill_file:
            bill_file.write('this is a test')

        # delete the file, and get the path it was moved to
        new_path = self.billupload.delete_utilbill_file(self.utilbill)

        # now the file should not exist at its original path
        self.assertFalse(os.access(path, os.F_OK))

        # but there should now be one file in the trash path, and its path
        # should be 'new_path'
        self.assertEqual(1,
                len(list(os.walk(self.billupload.utilbill_trash_dir))))
        for root, dirs, files in os.walk(self.billupload.utilbill_trash_dir):
            self.assertEqual([], dirs)
            self.assertEqual(1, len(files))
            self.assertEqual(new_path, os.path.join(root, files[0]))

if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()