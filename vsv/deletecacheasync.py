import os
from shutil import rmtree
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')
    
def lambda_handler(event, context):
    """ Handler for deleting cached DeepZoom files asynchronously."""
    logger.info(event)
    try:
        os.chdir(IMAGES_PATH)
        image_id = event['imageId']
        os.remove(f'{image_id}.dzi')
        rmtree(f'{image_id}_files')
    except Exception as error:
        logger.error(error)