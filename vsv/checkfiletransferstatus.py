import os
import json
import boto3
from datetime import datetime, timezone, timedelta
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')
TABLE_NAME = os.environ.get('TABLE_NAME')
ENV_TYPE = os.environ.get('ENV_TYPE', 'dev')
TASK_ARN = os.environ.get('TASK_ARN')

dynamodb = boto3.resource('dynamodb')
slide_table = dynamodb.Table(TABLE_NAME)
datasync_client = boto3.client('datasync')

def lambda_handler(event, context):
    input_files = set(file['filename'] for file in event['files'])
    found_files = set()
    for file in event['files']:
        filename = file['filename']
        result = slide_table.query(IndexName='Filename-index', KeyConditionExpression=dynamodb.conditions.Key('Filename').eq(filename))
        if result['Count'] > 0:
            found_files.add(filename)
            input_files.remove(filename)
        else:
            file_path = os.path.join(IMAGES_PATH, filename)
            if os.path.exists(file_path):
                input_files.remove(filename)
                if os.path.getsize(file_path) == file['size']: 
                    ctime = datetime.fromtimestamp(os.path.getctime(file_path), tz=timezone.utc)
                    if datetime.now(tz=timezone.utc) - ctime > timedelta(minutes=2): # at least 2 minutes old
                        found_files.add(filename)
    if len(input_files) > 0:
        task_description = datasync_client.describe_task(TaskArn=TASK_ARN)
        print(task_description)
        if task_description['Status'] == 'AVAILABLE':
            datasync_client.start_task_execution(TaskArn=TASK_ARN)
        #TODO check for problem files
    return list(found_files)
