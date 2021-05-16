import os
import json
import boto3
import openslide
from pylibdmtx import pylibdmtx
from datetime import datetime, timezone
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

FS_PATH = os.environ.get('FS_PATH', '/tmp')

def lambda_handler(event, context):
    image_filename = event['filename']
    osr = openslide.open_slide(os.path.join(FS_PATH, image_filename))
    
    # get image id from tiff tags; create output folder
    image_id = osr.properties.get(PROPERTY_NAME_APERIO_IMAGEID)
    
    # Extract label and thumbnail images
    label = osr.associated_images.get(u'label').convert('RGB')

    # decode slide id from 2D Data Matrix barcode in label image
    label_data = pylibdmtx.decode(label)
    if len(label_data) != 1:
        logger.error('Bad label data')
        return

    slide_id = label_data[0].data.decode('ascii')

    # get metadata
    width, height = osr.dimensions
    scan_date = osr.properties.get(PROPERTY_NAME_APERIO_DATE)
    scan_time = osr.properties.get(PROPERTY_NAME_APERIO_TIME)
    scan_timezone = osr.properties.get(PROPERTY_NAME_APERIO_TZ)
    scandate = datetime.strptime(f'{scan_date} {scan_time} {scan_timezone}', '%m/%d/%y %H:%M:%S %Z%z')
    metadata = {
        'Filename': image_filename.strip(),
        'ImageID': image_id.strip(),
        'SlideID': slide_id.strip(),
        'width': width,
        'height': height,
        'ScanDate': scandate.isoformat(),
        'MPP': osr.properties.get(PROPERTY_NAME_APERIO_MPP),
        'AppMag': osr.properties.get(PROPERTY_NAME_APERIO_APPMAG),
        'lastModified': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
    }

    # TODO: put metadata
    logger.info(f'Uploaded metadata for {image_filename}')