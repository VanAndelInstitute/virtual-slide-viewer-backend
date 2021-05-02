import os
from datetime import datetime, timezone, timedelta
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

FS_PATH = os.environ.get('FS_PATH', '/tmp')
ENV_TYPE = os.environ.get('ENV_TYPE', 'dev')

def lambda_handler(event, context):
    file_path = os.path.join(FS_PATH, event['filename'])
    if os.path.exists(file_path):
        # file transfer has started/occurred
        if os.path.getsize(file_path) == event['size']:
            # transferred file size matches original
            ctime = datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.utc)
            if datetime.now(tz=timezone.utc) - ctime > timedelta(seconds=15):
                # transferred file has not been modified in the last 15 seconds
                return 'Done'
    return 'NotSynced'