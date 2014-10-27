#!/usr/bin/python
import hashlib

from boto.s3.connection import S3Connection

from billing import config


class BillUpload(object):
    '''This class handles everything related to utility bill files, which are
    now stored in Amazon S3.
    TODO: rename.
    '''
    HASH_CHUNK_SIZE = 1024 ** 2

    def __init__(self, connection, bucket_name, utilbill_loader, url_format):
        ''':param connection: boto.s3.S3Connection
        :param bucket_name: name of S3 bucket where utility bill files are
        :param url_format: format string for URL where utility bill files can
        be accessed, e.g.
        "https://s3.amazonaws.com/%(bucket_name)s/utilbill/%(key_name)s"
        (must be formattable with a dict having "bucket_name" and "key_name"
        keys).
        '''
        self._connection = connection
        self._bucket_name = bucket_name
        self._utilbill_loader = utilbill_loader
        self._url_format = url_format

    @classmethod
    def from_config(cls):
        return cls(S3Connection(config.get('aws_s3', 'aws_access_key_id'),
                                config.get('aws_s3', 'aws_secret_access_key'),
                                is_secure=config.get('aws_s3', 'is_secure'),
                                port=config.get('aws_s3', 'port'),
                                host=config.get('aws_s3', 'host'),
                                calling_format=config.get('aws_s3',
                                                          'calling_format')))

    @classmethod
    def compute_hexdigest(cls, file):
        '''Return SHA-256 hash of the given file (must be seekable).
        '''
        hash_function = hashlib.sha256()
        position = file.tell()
        while True:
            data = file.read(cls.HASH_CHUNK_SIZE)
            hash_function.update(data)
            if data == '':
                break
        file.seek(position)
        return hash_function.hexdigest()

    @staticmethod
    def _get_key_name(utilbill):
        return utilbill.sha256_hexdigest

    def _get_amazon_bucket(self):
        return self._connection.get_bucket(self._bucket_name)

    def get_s3_url(self, utilbill):
        '''Return URL for the file corresponding to the given utility bill.
        '''
        return self._url_format % dict(bucket_name=self._bucket_name,
                                      key_name=utilbill.sha256_hexdigest)

    def delete_utilbill_pdf_from_s3(self, utilbill):
        """Removes the pdf file associated with utilbill from s3.
        """
        # TODO: fail if count is not 1?
        if self._utilbill_loader.count_utilbills_with_hash(
                utilbill.sha256_hexdigest) == 1:
            key_name = BillUpload._get_key_name(utilbill)
            key = self._get_amazon_bucket().get_key(key_name)
            key.delete()

    def upload_utilbill_pdf_to_s3(self, utilbill, file):
        """Uploads the pdf file to amazon s3
        :param utilbill: a :class:`billing.process.state.UtilBill`
        :param file: a file
        """
        utilbill.sha256_hexdigest = BillUpload.compute_hexdigest(file)
        key_name = self._get_key_name(utilbill)
        key = self._get_amazon_bucket().new_key(key_name)
        key.set_contents_from_file(file)

    # TODO: this should go away when recent changes are merged
