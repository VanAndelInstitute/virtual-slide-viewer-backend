import os
import traceback as tb
import base64
import json
import re
from io import BytesIO
import openslide
from openslide.deepzoom import DeepZoomGenerator
from PIL import Image
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DEEPZOOM_TILE_SIZE_DEFAULT = 720
DEEPZOOM_OVERLAP_DEFAULT = 0
DEEPZOOM_FORMAT_DEFAULT = 'jpeg'
DEEPZOOM_TILE_QUALITY = 70
FS_PATH = os.environ.get('FS_PATH', '/tmp')

class Object(object):
    pass
open_slides = {}

def load_slide(image_id, tile_size=None, overlap=None, _format=None):
    if image_id in open_slides:
        return open_slides[image_id]

    tile_size = tile_size or DEEPZOOM_TILE_SIZE_DEFAULT
    overlap = overlap if overlap is not None else DEEPZOOM_OVERLAP_DEFAULT
    _format = _format or DEEPZOOM_FORMAT_DEFAULT
    slide = Object()
    slide.osr = openslide.open_slide(os.path.join(FS_PATH, f'{image_id}.svs'))
    slide.dz = DeepZoomGenerator(slide.osr, tile_size, overlap)
    open_slides[image_id] = slide
    return slide

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
    """ Handler for individual DeepZoom protocol requests.
        Returns: one DeepZoom tile OR a DeepZoom info (dzi) xml document."""
    try:
        image_path = event['pathParameters']['imagePath']
        logger.info(image_path)
        # 1001610.dzi
        # 1001610_files/14/15_16.jpeg
        match = re.match(r'(?P<image_id>\w+)((?P<dzi>\.dzi)|_files/((?P<assoc>thumbnail|label)|(?P<level>\d{1,2})/(?P<col>\d{1,3})_(?P<row>\d{1,3}))\.(?P<format>jpeg|png))', image_path)
        if not match:
            raise ValueError(f'Bad resource request: {image_path}')

        image_id = match.group('image_id')
        is_dzi_request = bool(match.group('dzi'))
        is_associated_image_request = bool(match.group('assoc'))
        if is_dzi_request:
            try:
                tile_size = event['queryStringParameters']['tilesize']
            except:
                tile_size = DEEPZOOM_TILE_SIZE_DEFAULT
            try:
                overlap = event['queryStringParameters']['overlap']
            except:
                overlap = DEEPZOOM_OVERLAP_DEFAULT
            try:
                _format = event['queryStringParameters']['fmt'].lower()
            except:
                _format = DEEPZOOM_FORMAT_DEFAULT
            slide = load_slide(image_id, tile_size, overlap, _format)
            dzi = slide.dz.get_dzi(_format)
            return respond(dzi, content_type='application/xml')
        elif is_associated_image_request:
            _format = match.group('format')
            file_path = os.path.join(FS_PATH, image_path).replace('_files/', '/', 1)
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                with open(file_path, 'rb') as f:
                    result = f.read()
            else:
                name = match.group('assoc')
                slide = load_slide(image_id)
                image = slide.osr.associated_images.get(name).convert('RGB')
                buf = BytesIO()
                image.save(buf, _format, quality=DEEPZOOM_TILE_QUALITY)
                image.close()
                result = buf.getvalue()
        else:
            level = int(match.group('level'))
            col = int(match.group('col'))
            row = int(match.group('row'))
            _format = match.group('format')
            slide = load_slide(image_id)
            tile = slide.dz.get_tile(level, (col, row))
            buf = BytesIO()
            tile.save(buf, _format, quality=DEEPZOOM_TILE_QUALITY)
            tile.close()
            result = buf.getvalue()

        return respond(base64.b64encode(result), content_type=f'image/{_format}')
        
    except Exception as e:
        return respond(None, e, 400)
