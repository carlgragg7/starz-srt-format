import boto3
from botocore.exceptions import NoCredentialsError, ClientError, PartialCredentialsError
import botocore
import os
import json

import logging
import boto3.s3.transfer as s3transfer

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.s3 = boto3.resource('s3')
        self.s3_res = boto3.client('s3', region_name='us-east-2')


    def get_secret(self):
        secret_name = "OPENAI_API_KEY"
        region_name = "us-east-2"

        # Create a Secrets Manager client
        session = boto3.session.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=region_name
        )
        try:
            get_secret_value_response = client.get_secret_value(
                SecretId=secret_name
            )
        except ClientError as e:
            raise e

        secret = get_secret_value_response['SecretString']
        return json.loads(secret)


    def upload_file(self, file_name, bucket, object_name=None):
        if object_name is None:
            object_name = file_name
        try:
            response = self.s3_client.upload_file(file_name, bucket, object_name)
            logging.info(f"File {file_name} uploaded to {bucket}/{object_name}.")
            return response
        except ClientError as e:
            logging.error(f"Failed to upload {file_name} to {bucket}/{object_name}: {e}")
            return False
        except NoCredentialsError:
            logging.error("Credentials not available.")
            return False

    def transfer_file(self, og_bucket, og_key, to_bucket=None, to_key=None):
        if to_key is None:
            to_key = og_key
        if to_bucket is None:
            to_bucket = og_bucket

        transfer_config = s3transfer.TransferConfig(
            use_threads=True,
            max_concurrency=20,
        )

        s3t = s3transfer.create_transfer_manager(self.s3_client, transfer_config)
        copy_source = {
            'Bucket': og_bucket,
            'Key': og_key
        }
        s3t.copy(copy_source=copy_source, bucket=to_bucket, key=to_key)

    def download_file(self, bucket, object_name, file_name=None):
        if file_name is None:
            file_name = object_name
        logging.info(f'Downloading file: {object_name} from bucket: {bucket} to path: {file_name}')
        try:
            self.s3.Bucket(bucket).download_file(object_name, file_name)
            logging.info(f"File {object_name} downloaded from {bucket} to {file_name}.")
        except ClientError as e:
            logging.error(f"Failed to download {object_name} from {bucket}: {e}")
        except NoCredentialsError:
            logging.error("Credentials not available.")

    def list_files(self, bucket):
        try:
            response = self.s3_client.list_objects_v2(Bucket=bucket)
            if 'Contents' in response:
                for obj in response['Contents']:
                    logging.info(f"File found: {obj['Key']}")
            else:
                logging.info("No files found.")
        except ClientError as e:
            logging.error(f"Failed to list files in {bucket}: {e}")
        except NoCredentialsError:
            logging.error("Credentials not available.")

    def upload_to_s3_multipart(self, file_path, bucket_name, s3_key):
        s3_client = boto3.client('s3')

        config = boto3.s3.transfer.TransferConfig(
            multipart_threshold=5 * 1024 * 1024,
            multipart_chunksize=5 * 1024 * 1024,
            use_threads=True
        )

        try:
            s3_client.upload_file(file_path, bucket_name, s3_key, Config=config)
            print(f"Uploaded {file_path} to s3://{bucket_name}/{s3_key}")
        except Exception as e:
            print(f"Failed to upload {file_path} to S3: {str(e)}")

    def stream_and_move_file(self, source_bucket, source_key, destination_bucket, destination_key):
        try:
            # Get the source object
            source_object = self.s3_client.get_object(Bucket=source_bucket, Key=source_key)
            source_body = source_object['Body']

            # Upload the streamed data to the destination bucket
            self.s3_client.upload_fileobj(source_body, destination_bucket, destination_key)

            print(f"File successfully transferred from {source_bucket}/{source_key} to {destination_bucket}/{destination_key}")

        except NoCredentialsError:
            print("Credentials not available")
        except PartialCredentialsError:
            print("Incomplete credentials provided")
        except Exception as e:
            print(f"An error occurred: {e}")


    def update_status_in_s3(self, S3_BUCKET, s3_key, status, progress=None):
        try:
            status_file_key = f'status/{s3_key}.json'

            status_data = {
                "status": status
            }

            if progress is not None:
                status_data["progress"] = progress

            status_json = json.dumps(status_data)

            print("*"*50)
            print(status_json)

            self.s3_res.put_object(
                Bucket=S3_BUCKET,
                Key=status_file_key,
                Body=status_json,
                ContentType='application/json'
            )

            logging.info(f"Status updated to {status} for {s3_key}")

        except Exception as e:
            logging.error(f"Error updating status for {s3_key}: {e}")
            raise e
