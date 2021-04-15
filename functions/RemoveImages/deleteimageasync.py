import os
from shutil import rmtree
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')

def lambda_handler(event, context):
    """ Delete image files."""
    os.chdir(IMAGES_PATH)
    os.remove(event['Filename'])
    image_id = event['ImageID']
    os.remove(f'{image_id}.dzi')
    rmtree(f'{image_id}')
    logger.info(f'Deleted {event["ImageID"]} files')
