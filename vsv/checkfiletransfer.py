import os
import json
import traceback as tb
from datetime import datetime, timezone, timedelta
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')
ENV_TYPE = os.environ.get('ENV_TYPE', 'dev')

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
    filename = event['filename']
    file_path = os.path.join(IMAGES_PATH, filename)
    if os.path.exists(file_path):
        # file transfer has started/occurred
        statusCode = 202
        if os.path.getsize(file_path) == event['size']:
            # transferred file size matches original
            ctime = datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.utc)
            if datetime.now(tz=timezone.utc) - ctime > timedelta(seconds=15):
                # transferred file has not been modified in the last 15 seconds
                statusCode = 200
    else:
        statusCode = 404
    
    return respond(None, None, statusCode)