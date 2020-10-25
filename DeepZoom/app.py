import os
import traceback as tb
import base64
import re
from io import BytesIO
import openslide
from openslide import ImageSlide, open_slide
from openslide.deepzoom import DeepZoomGenerator
import threading
import xml.etree.ElementTree as xml
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger()
logger.setLevel(logging.INFO)

DEEPZOOM_FORMAT_DEFAULT = 'jpeg'
DEEPZOOM_TILE_SIZE_DEFAULT = 254
DEEPZOOM_OVERLAP_DEFAULT = 1
DEEPZOOM_LIMIT_BOUNDS = False
DEEPZOOM_TILE_QUALITY = 70
ALLOW_ORIGIN = os.environ.get('ALLOW_ORIGIN')
IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')
ENV_TYPE = os.environ.get('ENV_TYPE', 'dev')


def cache_tile(tile, outfile, _format):
    tiledir = os.path.dirname(outfile)
    filename = os.path.basename(outfile)
    filepath = os.path.join(tiledir, filename)
    os.makedirs(tiledir, exist_ok=True)
    tile.save(filepath, _format, quality=DEEPZOOM_TILE_QUALITY)
    logger.info(f'Cached tile: {outfile}')

class CachedDeepZoomGenerator(DeepZoomGenerator):
    def __init__(self, image_id, tile_size, overlap, _format):
        osr = open_slide(os.path.join(IMAGES_PATH, f'{image_id}.svs'))
        DeepZoomGenerator.__init__(self, osr, tile_size, overlap, _format)
        
        self.image_id = image_id
        self.tile_size = tile_size
        self.overlap = overlap
        self.format = _format
        mpp_x = osr.properties[openslide.PROPERTY_NAME_MPP_X]
        mpp_y = osr.properties[openslide.PROPERTY_NAME_MPP_Y]
        self.mpp = (float(mpp_x) + float(mpp_y)) / 2
        if self.format != 'jpeg' and self.format != 'png':
            # Not supported by Deep Zoom
            raise ValueError(f'Unsupported format: {self.format}')

    def get_tile(self, level, address):
        """Return an RGB PIL.Image for a tile (not from cache), caching it first.

        level:     the Deep Zoom level.
        address:   the address of the tile within the level as a (col, row)
                   tuple."""
        col, row = address
        file_path, cache_valid = check_cache(self.image_id, level, col, row, self.format)
        tile = DeepZoomGenerator.get_tile(self, level, address)

        if not cache_valid:
            # cache tile, but don't block before returning it
            threading.Thread(target=cache_tile, args=(tile, file_path, self.format)).start()
        
        return tile
    
    def get_dzi(self, tile_size=None, overlap=None, _format=None):
        """Get the dzi document from cache, unless the parameters have changed.
        
        Specifying parameters different from the tile cache invalidates it."""
        invalidate = False
        dzi_path = os.path.join(IMAGES_PATH, f'{self.image_id}.dzi')
        try:
            with open(dzi_path, 'rt', encoding='utf-8') as f:
                dzi_str = f.read()
            root = xml.fromstring(dzi_str)
            self.tile_size = int(root.get('TileSize'))
            self.overlap = int(root.get('Overlap'))
            self.format = root.get('Format')
            if tile_size is not None and self.tile_size != tile_size or overlap is not None and self.overlap != overlap or _format is not None and self.format != _format:
                invalidate = True
        except:
            invalidate = True
        
        if invalidate:
            self.__init__(self.image_id, tile_size or DEEPZOOM_TILE_SIZE_DEFAULT, overlap if overlap is not None else DEEPZOOM_OVERLAP_DEFAULT, _format or DEEPZOOM_FORMAT_DEFAULT)
            dzi_str = DeepZoomGenerator.get_dzi(self, self.format)
            with open(dzi_path, 'wt', encoding='utf-8') as f:
                f.write(dzi_str) # this invalidates any cached tiles older than this write
        return dzi_str

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

open_slides = {}

def load_slide(image_id):
    if image_id in open_slides:
        return open_slides[image_id]

    # set up tile params
    dzi_path = os.path.join(IMAGES_PATH, f'{image_id}.dzi')
    try:
        tree = xml.parse(dzi_path)
        root = tree.getroot()
        tile_size = int(root.get('TileSize'))
        overlap = int(root.get('Overlap'))
        _format = root.get('Format')
    except:
        tile_size = DEEPZOOM_TILE_SIZE_DEFAULT
        overlap = DEEPZOOM_OVERLAP_DEFAULT
        _format = DEEPZOOM_FORMAT_DEFAULT
    
    dz = open_slides[image_id] = CachedDeepZoomGenerator(image_id, tile_size, overlap, _format)
    return dz

def check_cache(image_id, level, col, row, _format):
    dzi_path = os.path.join(IMAGES_PATH, f'{image_id}.dzi')
    cache_lmtime = os.path.getmtime(dzi_path)
    file_path = os.path.join(IMAGES_PATH, f'{image_id}_files/{level}/{col}_{row}.{_format}')
    cache_valid = os.path.exists(file_path) and os.path.getsize(file_path) > 0 and os.path.getmtime(file_path) >= cache_lmtime
    return file_path, cache_valid

def image_request_handler(event, context):
    """ Handler for individual DeepZoom protocol requests.
        Returns: one DeepZoom tile OR a DeepZoom info (dzi) xml document."""
    try:
        image_path = event['pathParameters']['imagePath']
        logger.info(image_path)
        # 170782.dzi
        # 170782_files/14/15_16.jpeg
        request = re.match(r'(?P<image_id>\w+)((?P<dzi>\.dzi)|_files/(?P<level>\d{1,2})/(?P<col>\d{1,3})_(?P<row>\d{1,3})\.(?P<format>jpeg|png))', image_path)
        if not request:
            raise ValueError(f'Bad resource request: {image_path}')

        image_id = request.group('image_id')
        is_dzi_request = bool(request.group('dzi'))
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
            dz = load_slide(image_id)
            dzi = dz.get_dzi(tile_size, overlap, _format)
            return respond(dzi, content_type='application/xml')

        level = int(request.group('level'))
        col = int(request.group('col'))
        row = int(request.group('row'))
        _format = request.group('format')
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

import boto3
import json
client = boto3.client('lambda')

def generate_tiles_handler(image_id, level=None, address=None, tile_size=DEEPZOOM_TILE_SIZE_DEFAULT, overlap=DEEPZOOM_OVERLAP_DEFAULT, _format=DEEPZOOM_FORMAT_DEFAULT):
    """ Pre-compute tiles and cache them for an entire SVS image, using lots of parallel Lambda invocations.
        First code block is for individual invoke; second block is for massive parallelism."""
    if level and address:
        col, row = address
        # dz.get_tile() will load the image if it exists, so check here first to skip that
        file_path, cache_valid = check_cache(image_id, level, col, row, _format)
        if not cache_valid:
            dz = load_slide(image_id)
            dz.get_tile(level, (col, row))
    else:        
        dz = load_slide(image_id)
        dz.get_dzi(tile_size, overlap, _format)
        for level in range(dz.level_count):
            x_count, y_count = dz.level_tiles[level]
            for col, row in ((x, y) for x in range(x_count) for y in range(y_count)):
                request = { 'image_id': image_id, 'level': level, 'col': col, 'row': row, '_format': _format }
                client.invoke(
                    FunctionName='generate_tile',
                    InvocationType='Event',
                    LogType='None',
                    Payload=json.dumps(request),
                    Qualifier=ENV_TYPE
                )

import sys
import json
if __name__ == '__main__':
    image_request_handler(json.loads(sys.argv[1]), None)