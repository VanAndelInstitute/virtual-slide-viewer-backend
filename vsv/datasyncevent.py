import os
import base64
import gzip
import json
import re
import openslide
from slidecache import load_slide
import boto3
from pylibdmtx import pylibdmtx
from datetime import datetime
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

PROPERTY_NAME_APERIO_IMAGEID = u'aperio.ImageID'
PROPERTY_NAME_APERIO_DATE = u'aperio.Date'
PROPERTY_NAME_APERIO_TIME = u'aperio.Time'
PROPERTY_NAME_APERIO_TZ = u'aperio.Time Zone'
PROPERTY_NAME_APERIO_MPP = u'aperio.MPP'
PROPERTY_NAME_APERIO_APPMAG = u'aperio.AppMag'

IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')
ENV_TYPE = os.environ.get('ENV_TYPE', 'dev')
TABLE_NAME = os.environ.get('TABLE_NAME')
TILES_FUNCTION_NAME = os.environ.get('TILES_FUNCTION_NAME')


def lambda_handler(event, context):
    compressed_payload = base64.b64decode(event['awslogs']['data'])
    uncompressed_payload = gzip.decompress(compressed_payload)
    payload = json.loads(uncompressed_payload)
    log_events = payload['logEvents']
    logger.debug(payload)
    loggroup = payload['logGroup']
    logstream = payload['logStream']
    for log_event in log_events:
        match = re.match(r'\[NOTICE\] Verified file /(?P<filename>\w+\.svs), \d+ bytes', log_event['message'])
        preprocess_image(match.group('filename'))

def preprocess_image(image_filename):
    osr = openslide.open_slide(os.path.join(IMAGES_PATH, image_filename))
    
    # get image id from tiff tags; create output folder
    image_id = osr.properties.get(PROPERTY_NAME_APERIO_IMAGEID)
    
    # Extract label and thumbnail images
    thumbnail = osr.associated_images.get(u'thumbnail')
    thumbnail.convert('RGB').save(os.path.join(IMAGES_PATH, f'{image_id}_thumbnail.jpg'))
    label = osr.associated_images.get(u'label')
    label.convert('RGB').save(os.path.join(IMAGES_PATH, f'{image_id}_label.jpg'))

    # decode slide id from 2D Data Matrix barcode in label image
    label_data = pylibdmtx.decode(label)
    if len(label_data) != 1:
        logger.error('Bad label data')
        return
    slide_id = label_data[0].data.decode('ascii')
    # guess at case id
    last_index = slide_id.rfind('-')
    case_id = slide_id[0:last_index]

    # get metadata
    metadata = {}
    metadata['ImageID'] = image_id
    metadata['SlideID'] = slide_id
    metadata['CaseID'] = case_id
    metadata['Status'] = 'NEW'
    width, height = osr.dimensions
    metadata['width'] = width
    metadata['height'] = height
    scan_date = osr.properties.get(PROPERTY_NAME_APERIO_DATE)
    scan_time = osr.properties.get(PROPERTY_NAME_APERIO_TIME)
    scan_timezone = osr.properties.get(PROPERTY_NAME_APERIO_TZ)
    scandate = datetime.strptime(f'{scan_date} {scan_time} {scan_timezone}', '%m/%d/%y %H:%M:%S %Z%z')
    metadata['ScanDate'] = scandate.isoformat()
    metadata['MPP'] = osr.properties.get(PROPERTY_NAME_APERIO_MPP)
    metadata['AppMag'] = osr.properties.get(PROPERTY_NAME_APERIO_APPMAG)
    metadata['lastModified'] = datetime.utcnow().isoformat()
    
    # upload metadata to slide table in DynamoDB
    dynamodb = boto3.resource('dynamodb')
    slide_table = dynamodb.Table(TABLE_NAME)
    slide_table.put_item(Item=metadata)

    # Pre-compute tiles and cache them for an entire SVS image, using lots of parallel Lambda invocations.
    dz = load_slide(image_id)
    lambda_client = boto3.client('lambda')
    for level in dz.native_levels:
        event = { 'image_id': image_id, 'level': level, 'level_tracts': dz.level_tracts[level] }
        lambda_client.invoke(
            FunctionName=TILES_FUNCTION_NAME,
            InvocationType='Event',
            LogType='None',
            Payload=json.dumps(event),
            Qualifier=ENV_TYPE
        )

