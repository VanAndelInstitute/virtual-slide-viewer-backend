import os
import glob
import boto3
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')
ASYNC_FUNCTION_NAME = os.environ.get('ASYNC_FUNCTION_NAME')
ENV_TYPE = os.environ.get('ENV_TYPE', 'dev')

def lambda_handler(event, context):
    os.chdir(IMAGES_PATH)
    new_image_ids = { f[:-4] for f in glob.glob('*.svs') } - { f[:-4] for f in glob.glob('*_files') }
    lambda_client = boto3.client('lambda')
    for image_id in new_image_ids:
        filename = image_id+'.svs'
        lambda_client.invoke(
            FunctionName=ASYNC_FUNCTION_NAME,
            InvocationType='Event',
            LogType='None',
            Payload=f'{{ "filename": "{filename}" }}'
        )
        logger.info(f'Processing new file "{filename}"')
