import os
import botocore
import boto3
import traceback as tb
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
import json

TRANSFER_FUNCTION = os.environ.get('TRANSFER_FUNCTION')
DELETE_FUNCTION = os.environ.get('DELETE_FUNCTION')
lambda_client = boto3.client('lambda')

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
    """ Transfer or delete image files."""
    body = json.loads(event['body'])
    op = body['Operation']
    if op.startswith('TRANSFER'):
        functionName = TRANSFER_FUNCTION
    elif op.startswith('DELETE'):
        functionName = DELETE_FUNCTION
    else:
        return
    for image in body['Images']:
        try:
            response = lambda_client.invoke(
                FunctionName=functionName,
                InvocationType='Event', # run async b/c of APIG timeout
                LogType='None',
                Payload=json.dumps(image)
            )
            if response['StatusCode'] != 202:
                logger.error(response['FunctionError'])
                return respond(None, FunctionError(response['FunctionError']), response['StatusCode'])
        except botocore.exceptions.ClientError as error:
            logger.error(error.response['Error'])
            return respond(None, FunctionError(response['FunctionError']), response['StatusCode'])

    return respond({})