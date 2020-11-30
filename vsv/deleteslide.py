import os
import traceback as tb
import boto3
import glob
from shutil import rmtree
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')
TABLE_NAME = os.environ.get('TABLE_NAME')

dynamodb = boto3.resource('dynamodb')
slide_table = dynamodb.Table(TABLE_NAME)
    
def lambda_handler(event, context):
    """ Handler for deleting image files."""
    status = 200
    error = None
    try:
        os.chdir(IMAGES_PATH)
        image_id = event['pathParameters']['imageId']
        logger.info(image_id)

        item = slide_table.get_item(Key={'ImageID':image_id},ProjectionExpression='Filename').get('Item')
        if item:
            os.remove(item['Filename'])
        os.remove(f'{image_id}.dzi')
        rmtree(f'{image_id}_files')
    except Exception as error:
        status = 400

    return {
        'statusCode': status,
        'body': error
    }
