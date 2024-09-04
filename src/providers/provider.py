import os
import logging
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

class Provider:
    def __init__(self):
        self.setup_logging()
        self.output_prefix = None

    def create_output_prefix(self, filename, output_prefix):
        filename_no_ext = filename.split('.')[0]
        self.output_prefix = f'{output_prefix}/{filename_no_ext}'

    def create_output_key(self, filename, sub_prefix=None, new_file_ext=None, add_output_prefix=True):
        base = ''
        if new_file_ext:
            filename_no_ext = filename.split('.')[0]
            filename = f'{filename_no_ext}.{new_file_ext}'
        if add_output_prefix:
            base = f'{self.output_prefix}/'
        if sub_prefix:
            return f'{base}{sub_prefix}/{filename}'
        return f'{base}{filename}'

    def create_local_path(self, filename, sub_prefix=None, new_file_ext=None):
        if new_file_ext:
            filename_no_ext = filename.split('.')[0]
            filename = f'{filename_no_ext}.{new_file_ext}'
        if sub_prefix:
            return f'{sub_prefix}/{filename}'
        return filename

    def get_destination_folder(self):
        return os.environ.get('DESTINATION_FOLDER')

    def get_open_ai_url(self):
        return os.environ.get('OPEN_AI_URL')

    def get_input_s3_key(self):
        return os.environ.get('KEY')

    def get_bucket(self):
        return os.environ.get('BUCKET')

    def setup_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        try:
            boto3.client('sts').get_caller_identity()
            logging.info("AWS credentials are valid and present.")
        except (NoCredentialsError, PartialCredentialsError):
            logging.error("AWS credentials not found or incomplete.")
            logging.info("Proceeding with local logging only.")


    def get_logger(self, name):
        return logging.getLogger(name)
