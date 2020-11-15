import os
import json
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
TABLE_NAME = os.environ.get('TABLE_NAME')
TILES_FUNCTION_NAME = os.environ.get('TILES_FUNCTION_NAME')
ENV_TYPE = os.environ.get('ENV_TYPE', 'dev')


def lambda_handler(event, context):
    image_filename = event['filename']
    osr = openslide.open_slide(os.path.join(IMAGES_PATH, image_filename))
    
    # get image id from tiff tags; create output folder
    image_id = osr.properties.get(PROPERTY_NAME_APERIO_IMAGEID)
    
    # Extract label and thumbnail images
    imagedir = os.path.join(IMAGES_PATH, f'{image_id}_files/')
    os.makedirs(imagedir, exist_ok=True)
    thumbnail = osr.associated_images.get(u'thumbnail').convert('RGB')
    thumbnail.save(os.path.join(IMAGES_PATH, f'{image_id}_files/thumbnail.jpg'))
    label = osr.associated_images.get(u'label').convert('RGB')
    label.save(os.path.join(IMAGES_PATH, f'{image_id}_files/label.jpg'))

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
    logger.info(f'Uploaded metadata for {image_filename}')

    # Pre-compute tiles and cache them for an entire SVS image, using lots of parallel Lambda invocations.
    dz = load_slide(image_id)
    lambda_client = boto3.client('lambda')
    event = { 'image_id': image_id, 'depth': 0 }
    lambda_client.invoke(
        FunctionName=TILES_FUNCTION_NAME,
        InvocationType='Event',
        LogType='None',
        Payload=json.dumps(event),
        Qualifier=ENV_TYPE
    )
