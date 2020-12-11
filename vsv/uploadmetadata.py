import os
import json
import boto3
import openslide
import traceback as tb
from pylibdmtx import pylibdmtx
from datetime import datetime
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

PROPERTY_NAME_APERIO_IMAGEID = u'aperio.ImageID'
PROPERTY_NAME_APERIO_DATE = u'aperio.Date'
PROPERTY_NAME_APERIO_TIME = u'aperio.Time'
PROPERTY_NAME_APERIO_TZ = u'aperio.Time Zone'
PROPERTY_NAME_APERIO_MPP = u'aperio.MPP'
PROPERTY_NAME_APERIO_APPMAG = u'aperio.AppMag'

IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')
TABLE_NAME = os.environ.get('TABLE_NAME')
METADATA_FUNCTION = os.environ.get('METADATA_FUNCTION')

dynamodb = boto3.resource('dynamodb')
slide_table = dynamodb.Table(TABLE_NAME)
lambda_client = boto3.client('lambda')

def respond(success, error=None, status=200):
 
    response = {
        'isBase64Encoded': False,
        'statusCode': status,
        'headers': {
            'Content-Type' : 'application/json'
        },
        'body': ''.join(tb.format_exception(type(error), error, error.__traceback__)) if error else json.dumps(success)
    }

    log_msg = {x: response[x] if not type(response[x]) is bytes else response[x].decode('ascii') for x in response}
    logger.debug(json.dumps(log_msg))

    return response

def lambda_handler(event, context):
    filename = event['filename']
    # Call VPC function
    response = lambda_client.invoke(
        FunctionName=METADATA_FUNCTION,
        LogType='None',
        Payload=f'{{ "filename": "{filename}" }}'
    )
    metadata = json.loads(response['Payload'])

    # DynamoDB - put metadata
    slide_table.put_item(Item=metadata)
    logger.info(f'Uploaded metadata for {filename}')
