import os
import boto3
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')
TABLE_NAME = os.environ.get('TABLE_NAME')
ASYNC_FUNCTION_NAME = os.environ.get('ASYNC_FUNTION_NAME')
dynamodb = boto3.resource('dynamodb')
slide_table = dynamodb.Table(TABLE_NAME)
lambda_client = boto3.client('lambda')

def lambda_handler(event, context):
    """ Handler for deleting image files."""
    logger.info(event['path'])
    response = { 'statusCode': 200 }
    try:
        os.chdir(IMAGES_PATH)
        image_id = event['pathParameters']['imageId']
        item = slide_table.get_item(Key={'ImageID':image_id},ProjectionExpression='Filename').get('Item')
        if item:
            os.remove(item['Filename'])
        lambda_client.invoke(
            FunctionName=ASYNC_FUNCTION_NAME,
            InvocationType='Event',
            LogType='None',
            Payload=f'{{ "imageId": "{image_id}" }}'
        )
    except Exception as error:
        logger.error(error)
        response['statusCode'] = 400
        response['body'] = str(error)

    return response
