import os
from shutil import rmtree
import botocore
import boto3
import logging
import glob
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

FS_PATH = os.environ.get('FS_PATH', '/tmp')
TABLE_NAME = os.environ.get('TABLE_NAME')
ARCHIVE_BUCKET = os.environ.get('ARCHIVE_BUCKET')

dynamodb = boto3.resource('dynamodb')
slide_table = dynamodb.Table(TABLE_NAME)
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """ Backup image file to S3."""
    filepath = os.path.join(FS_PATH, event['Filename'])
    try:
        # upload to S3
        response = s3_client.put_object(
            Body=open(filepath, 'rb'),
            Bucket=ARCHIVE_BUCKET,
            Key=event['Filename'],
            StorageClass='INTELLIGENT_TIERING',
        )
        logger.info(f'Uploaded {event["Filename"]} to S3.')
    
    except botocore.exceptions.ClientError as error:
        logger.error(error.response['Error'])
