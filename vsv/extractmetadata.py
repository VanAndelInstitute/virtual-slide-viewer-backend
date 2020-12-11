import os
import json
import openslide
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
        slide_id = case_id = image_id
    else:
        slide_id = label_data[0].data.decode('ascii')
        # guess at case id
        last_index = slide_id.rfind('-')
        case_id = slide_id[0:last_index]

    # get metadata
    width, height = osr.dimensions
    scan_date = osr.properties.get(PROPERTY_NAME_APERIO_DATE)
    scan_time = osr.properties.get(PROPERTY_NAME_APERIO_TIME)
    scan_timezone = osr.properties.get(PROPERTY_NAME_APERIO_TZ)
    scandate = datetime.strptime(f'{scan_date} {scan_time} {scan_timezone}', '%m/%d/%y %H:%M:%S %Z%z')
    metadata = {
        'Filename': image_filename,
        'ImageID': image_id,
        'SlideID': slide_id,
        'CaseID': case_id,
        'Status': 'NEW',
        'width': width,
        'height': height,
        'ScanDate': scandate.isoformat(),
        'MPP': osr.properties.get(PROPERTY_NAME_APERIO_MPP),
        'AppMag': osr.properties.get(PROPERTY_NAME_APERIO_APPMAG),
        'lastModified': datetime.utcnow().isoformat(),
    }

    return metadata
