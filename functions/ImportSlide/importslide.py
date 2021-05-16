import os
import json
import boto3
from urllib.parse import unquote_plus
import traceback as tb
from datetime import datetime, timezone, timedelta
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

FS_PATH = os.environ.get('FS_PATH', '/tmp')
s3 = boto3.client('s3')

def lambda_handler(event, context):
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    try:
        s3.download_file(bucket, key, os.path.join(FS_PATH, key))
    except Exception as e:
        logger.error(e)
        raise e
