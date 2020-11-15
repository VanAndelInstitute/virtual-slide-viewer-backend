import os
import glob
import boto3
import json
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')
FILE_FUNCTION_NAME = os.environ.get('FILE_FUNCTION_NAME')
ENV_TYPE = os.environ.get('ENV_TYPE', 'dev')

def lambda_handler(event, context):
    os.chdir(IMAGES_PATH)
    new_image_ids = { f[:-4] for f in glob.glob('*.svs') } - { f[:-4] for f in glob.glob('*.dzi') }
    lambda_client = boto3.client('lambda')
    for image_id in new_image_ids:
        filename = image_id+'.svs'
        lambda_client.invoke(
            FunctionName=FILE_FUNCTION_NAME,
            InvocationType='Event',
            LogType='None',
            Payload=json.dumps({ 'filename': filename }),
            Qualifier=ENV_TYPE
        )
        logger.info(f'Processing new file "{filename}"')
