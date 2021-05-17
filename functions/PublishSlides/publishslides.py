import os
import botocore
import boto3
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
import json

SLIDES_BUCKET = os.environ.get('SLIDES_BUCKET')
PUBLISH_BUCKET = os.environ.get('PUBLISH_BUCKET')

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """ Copy image file to publish bucket."""
    body = json.loads(event['body'])
    for image in body['Images']:
        try:
            # upload to S3
            copy_source = {
                'Bucket': SLIDES_BUCKET,
                'Key': event['Filename']
            }
            extra_args = {
                'StorageClass': 'INTELLIGENT_TIERING'
            }
            response = s3_client.copy_object(
                CopySource=copy_source,
                Bucket=PUBLISH_BUCKET,
                Key=event['Filename'],
                ExtraArgs=extra_args
            )
            logger.info(f'Published {event["Filename"]}.')
        
        except botocore.exceptions.ClientError as error:
            logger.error(error.response['Error'])
