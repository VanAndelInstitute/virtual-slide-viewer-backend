import os
import botocore
import boto3
import logging
import glob
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')
TABLE_NAME = os.environ.get('TABLE_NAME')
IMAGES_BUCKET = os.environ.get('IMAGES_BUCKET')

dynamodb = boto3.resource('dynamodb')
slide_table = dynamodb.Table(TABLE_NAME)
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """ Transfer image file to archive/3rd party."""
    filepath = os.path.join(IMAGES_PATH, event['Filename'])
    try:
        # upload to S3
        response = s3_client.put_object(
            Body=open(filepath, 'rb'),
            Bucket=IMAGES_BUCKET,
            Key=event['Filename'],
            StorageClass='STANDARD_IA',
        )
        logger.info(f'Uploaded {event["Filename"]} to S3.')
        
        # delete files
        os.chdir(IMAGES_PATH)
        os.remove(event['Filename'])
        image_id = event['ImageID']
        os.remove(f'{image_id}.dzi')
        for file in glob.glob(f'{image_id}_files/*.*'):
            if not file.startswith('thumbnail') and not file.startswith('label'):
                os.remove(file)
        logger.info(f'Deleted files for image {event["Filename"]}.')
        
        # update db status
        slide_table.update_item(
            Key={'ImageID': event['ImageID']},
            UpdateExpression='set #Status = :val1',
            ExpressionAttributeNames={
                '#Status': 'Status'
            },
            ExpressionAttributeValues={
                ':val1': 'TRANSFERRED'
            }
        )
        logger.info(f'Updated status for image {event["Filename"]}.')

    except botocore.exceptions.ClientError as error:
        logger.error(error.response['Error'])
