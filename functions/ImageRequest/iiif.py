import os
import openslide
from PIL import Image
import traceback as tb
import base64
import json
from urllib.parse import urljoin
import re
from io import BytesIO
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

FS_PATH = os.environ.get('FS_PATH', '/tmp')
API_PATH = os.environ.get('API_PATH')
TILE_SIZE = 720
TILE_QUALITY = 70

open_slides = {}

def load_slide(image_id):
    if image_id in open_slides:
        return open_slides[image_id]

    osr = open_slides[image_id] = openslide.open_slide(os.path.join(FS_PATH, f'{image_id}.svs'))
    return osr

def get_info(image_id):
    osr = load_slide(image_id)
    width, height = osr.dimensions
    downsamples = list(map(lambda d: round(d), osr.level_downsamples))
    info =   {
        "@context": "http://iiif.io/api/image/2/context.json",
        "@id": urljoin(API_PATH, image_id),
        "type": "ImageService3",
        "protocol": "http://iiif.io/api/image",
        "profile": [ "http://iiif.io/api/image/2/level2.json" ],
        "width": width,
        "height": height,
        "tiles": [
            { "width": TILE_SIZE, "scaleFactors": downsamples }
        ]
    }
    return json.dumps(info)

def get_best_level_for_downsample(osr, downsample):
    """ Use our own implementation of this since OpenSlide's doesn't handle 
        the slightly-off Aperio SVS values."""
    for i in range(osr.level_count):
        if round(downsample) < round(osr.level_downsamples[i]):
            return 0 if i == 0 else i-1
    return osr.level_count - 1

def respond(success, error=None, status=200, content_type=None):
 
    response = {
        'statusCode': status,
        'body': ''.join(tb.format_exception(type(error), error, error.__traceback__)) if error else success,
        'headers': {},
    }
    if content_type:
        response['headers']['Content-Type'] = content_type
        if content_type.startswith('image'):
            response['isBase64Encoded'] = True

    log_msg = {x: response[x] if not type(response[x]) is bytes else response[x].decode('ascii') for x in response}
    logger.debug(json.dumps(log_msg))

    return response

def lambda_handler(event, context):
    """ Handler for individual IIIF protocol requests.
        Returns: one IIIF tile OR a IIIF info (dzi) xml document."""
    try:
        image_path = event['pathParameters']['imagePath']
        logger.info(image_path)
        # 1001610/info.json
        # 1001610/0,0,2880,2880/720,/0/default.jpg
        match = re.match(r'(?P<image_id>\w+)/((?P<info>(info|properties)\.json)|(?P<assoc>(thumbnail|label)\.jpeg)|(?P<region>\d+,\d+,\d+,\d+)/(?P<size>\d*,\d*)/(?P<rotation>\d{1,3})/(?P<quality>color|gray|bitonal|default)\.(?P<format>jpg|tif|png|gif|jp2|pdf|webp))', image_path)
        if not match:
            raise ValueError(f'Bad resource request: {image_path}')

        image_id = match.group('image_id')
        info_request_type = match.group('info')
        assoc_request_type = match.group('assoc')
        if info_request_type == 'info.json':
            return respond(get_info(image_id), content_type='application/json')
        elif info_request_type == 'properties.json':
            osr = load_slide(image_id)
            return respond(json.dumps(dict(osr.properties)), content_type='application/json')
        elif bool(assoc_request_type):
            file_path = os.path.join(FS_PATH, image_path)
            _format = 'jpeg'
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                with open(file_path, 'rb') as f:
                    result = f.read()
            else:
                name = assoc_request_type
                osr = load_slide(image_id)
                image = osr.associated_images.get(name).convert('RGB')
                buf = BytesIO()
                image.save(buf, 'jpg', quality=TILE_QUALITY)
                image.close()
                result = buf.getvalue()
        else:
            _format = 'jpeg' if match.group('format') == 'jpg' else _format
            region = match.group('region').split(',')
            x = int(region[0])
            y = int(region[1])
            w = int(region[2])
            h = int(region[3])
            osr = load_slide(image_id)
            downsample = max(w//TILE_SIZE, h//TILE_SIZE)
            downsamples = list(map(lambda d: round(d), osr.level_downsamples))
            level = get_best_level_for_downsample(osr, downsample)
            size = match.group('size').split(',')
            size = (int(size[0] or size[1]),int(size[1] or size[0]))
            region_size = tuple(l * downsample // downsamples[level] for l in size)
            tile = osr.read_region((x,y), level, region_size)
            if tile.size != size:
                tile.thumbnail(size, Image.ANTIALIAS)
            tile = tile.convert('RGB')
            buf = BytesIO()
            tile.save(buf, _format, quality=TILE_QUALITY)
            tile.close()
            result = buf.getvalue()

        return respond(base64.b64encode(result), content_type=f'image/{_format}')
        
    except Exception as e:
        return respond(None, e, 400)
