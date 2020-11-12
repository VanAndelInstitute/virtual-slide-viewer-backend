import os
import traceback as tb
import base64
import json
import re
from io import BytesIO
from slidecache import load_slide, check_cache
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DEEPZOOM_TILE_QUALITY = 70
ALLOW_ORIGIN = os.environ.get('ALLOW_ORIGIN')
IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')
ENV_TYPE = os.environ.get('ENV_TYPE', 'dev')

def respond(success, error=None, status=200, content_type=None):
 
    response = {
        'statusCode': status,
        'body': ''.join(tb.format_exception(type(error), error, error.__traceback__)) if error else success,
        'headers': {
            'Access-Control-Allow-Headers' : 'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Origin': ALLOW_ORIGIN,
            'Access-Control-Allow-Methods': 'OPTIONS,GET'
        },
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
        # 170782.dzi
        # 170782_files/14/15_16.jpeg
        match = re.match(r'(?P<image_id>\w+)((?P<dzi>\.dzi)|_files/(?P<level>\d{1,2})/(?P<col>\d{1,3})_(?P<row>\d{1,3})\.(?P<format>jpeg|png))', image_path)
        if not match:
            raise ValueError(f'Bad resource request: {image_path}')

        image_id = match.group('image_id')
        is_dzi_request = bool(match.group('dzi'))
        if is_dzi_request:
            try:
                tile_size = event['queryStringParameters']['tilesize']
            except:
                tile_size = None
            try:
                overlap = event['queryStringParameters']['overlap']
            except:
                overlap = None
            try:
                _format = event['queryStringParameters']['fmt'].lower()
            except:
                _format = None
            dz = load_slide(image_id, tile_size, overlap, _format)
            return respond(dz.get_dzi(), content_type='application/xml')

        level = int(match.group('level'))
        col = int(match.group('col'))
        row = int(match.group('row'))
        _format = match.group('format')
        file_path, cache_valid = check_cache(image_id, level, col, row, _format)
        if cache_valid:
            logger.info('From cache')
            # cache hit
            with open(file_path, 'rb') as f:
                result = f.read()
        else:
            # cache miss
            dz = load_slide(image_id)
            tile = dz.get_tile(level, (col, row))
            buf = BytesIO()
            tile.save(buf, _format, quality=DEEPZOOM_TILE_QUALITY)
            tile.close()
            result = buf.getvalue()
        return respond(base64.b64encode(result), content_type=f'image/{_format}')
        
    except Exception as e:
        return respond(None, e, 400)