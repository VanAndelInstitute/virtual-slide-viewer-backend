import os
from shutil import rmtree
import boto3
from boto3.dynamodb.conditions import Key, Attr
from datetime import date, timedelta
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')
TABLE_NAME = os.environ.get('TABLE_NAME')
dynamodb = boto3.resource('dynamodb')
slide_table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    """ Delete files for slides marked as DELETED."""
    os.chdir(IMAGES_PATH)
    # only delete files at least a week old
    cutoff = date.today() - timedelta(weeks=1)
    result = slide_table.query(
        IndexName='Status-SlideID-index', 
        KeyConditionExpression=Key('Status').eq('DELETED'),
        FilterExpression=Attr('lastModified').lt(cutoff.isoformat()))
    for item in result['Items']:
        os.remove(item['Filename'])
        image_id = item['ImageID']
        os.remove(f'{image_id}.dzi')
        rmtree(f'{image_id}_files')
