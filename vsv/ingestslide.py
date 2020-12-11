import os
import json
import boto3
from boto3.dynamodb.conditions import Key
import traceback as tb
from datetime import datetime, timezone, timedelta
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get('TABLE_NAME')
ENV_TYPE = os.environ.get('ENV_TYPE', 'dev')
TASK_ARN = os.environ.get('TASK_ARN')
CHECK_FILE_FUNCTION = os.environ.get('CHECK_FILE_FUNCTION')
METADATA_FUNCTION = os.environ.get('METADATA_FUNCTION')

dynamodb = boto3.resource('dynamodb')
slide_table = dynamodb.Table(TABLE_NAME)
lambda_client = boto3.client('lambda')
datasync_client = boto3.client('datasync')

class FunctionError(Exception):
    pass

def respond(success, error=None, status=200):
 
    response = {
        'isBase64Encoded': False,
        'statusCode': status,
        'headers': {
            'Content-Type' : 'application/json'
        }
    }
    if success or error:
        response['body'] = ''.join(tb.format_exception(type(error), error, error.__traceback__)) if error else json.dumps(success)

    log_msg = {x: response[x] if not type(response[x]) is bytes else response[x].decode('ascii') for x in response}
    logger.debug(json.dumps(log_msg))

    return response

def lambda_handler(event, context):

    body = json.loads(event['body'])
    file = body['file']

    # query for metadata
    filename = file['filename']
    result = slide_table.query(IndexName='Filename-index', KeyConditionExpression=Key('Filename').eq(filename))
    if result['Count'] > 0:
        # Case 1: File metadata has already been processed.
        # Non-empty return value indicates that the local file can now be deleted.
        return respond(file)

    # check for file (runs within VPC b/c of EFS)
    response = lambda_client.invoke(
        FunctionName=CHECK_FILE_FUNCTION,
        LogType='None',
        Payload=file
    )
    if response['StatusCode'] == 404:
        # Case 2: File was not found in EFS
        # Start DataSync task (if not already running).
        datasync_client.start_task_execution(TaskArn=TASK_ARN)
    elif response['StatusCode'] == 202:
        # Case 3: File was found in EFS, but transfer is not finished yet.
        # Nothing to do but wait until next invocation.
        pass
    elif response['StatusCode'] == 200:
        # Case 4: File transfer to EFS is complete, but metadata not yet uploaded.
        # extract,upload file metadata
        response = lambda_client.invoke(
            FunctionName=METADATA_FUNCTION,
            InvocationType='Event', # run async b/c of APIG timeout
            LogType='None',
            Payload=f'{{ "filename": "{filename}" }}'
        )
        if response['StatusCode'] != 202:
            logger.error(response['FunctionError']) 
            return respond(None, FunctionError(response['FunctionError']), response['StatusCode'])
        logger.info(f'Processing new file "{filename}"')
    else:
        # Some unexpected error.
        logger.error(response['FunctionError'])
        return respond(None, FunctionError(response['FunctionError']), response['StatusCode'])
    result = json.loads(response['Payload'])

    return respond({})
