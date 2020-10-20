import os
import traceback as tb
import base64
import re
from io import BytesIO
import openslide
from openslide import ImageSlide, open_slide
from openslide.deepzoom import DeepZoomGenerator
from PIL import Image
import threading

DEEPZOOM_FORMAT_DEFAULT = 'jpeg'
DEEPZOOM_TILE_SIZE_DEFAULT = 240
DEEPZOOM_OVERLAP = 0
DEEPZOOM_LIMIT_BOUNDS = False
DEEPZOOM_TILE_QUALITY = 70
ALLOW_ORIGIN = os.environ['ALLOW_ORIGIN']
IMAGES_PATH = os.environ['IMAGES_PATH']
ENV_TYPE = os.environ['ENV_TYPE']

    
def cache_tile(tile, outfile, _format):
    tiledir = os.path.dirname(outfile)
    filename = os.path.basename(outfile)
    filepath = os.path.join(tiledir, filename)
    os.makedirs(tiledir, exist_ok=True)
    tile.save(filepath, _format, quality=DEEPZOOM_TILE_QUALITY)

class CachedDeepZoomGenerator(DeepZoomGenerator):
    def __init__(self, image_id, _format):
        osr = open_slide(os.path.join(IMAGES_PATH, f'{image_id}.svs'))
        tile_height = int(osr.properties.get(u'openslide.level[0].tile-height', DEEPZOOM_TILE_SIZE_DEFAULT))
        tile_width = int(osr.properties.get(u'openslide.level[0].tile-width', DEEPZOOM_TILE_SIZE_DEFAULT))
        self.tile_size = min(tile_height, tile_width)
        DeepZoomGenerator.__init__(self, osr, self.tile_size, DEEPZOOM_OVERLAP, DEEPZOOM_LIMIT_BOUNDS)
        
        self.image_id = image_id
        mpp_x = osr.properties[openslide.PROPERTY_NAME_MPP_X]
        mpp_y = osr.properties[openslide.PROPERTY_NAME_MPP_Y]
        self.mpp = (float(mpp_x) + float(mpp_y)) / 2
        self.format = _format
        if self.format != 'jpeg' and self.format != 'png':
            # Not supported by Deep Zoom
            raise ValueError(f'Unsupported format: {self.format}')

        l0_l_downsamples = tuple(int(round(d)) for d in osr.level_downsamples)
        # Total downsamples for each Deep Zoom level
        l0_z_downsamples = tuple(2 ** (self.level_count - dz_level - 1)
                    for dz_level in range(self.level_count))

        native = lambda dz_level: l0_z_downsamples[dz_level] in l0_l_downsamples
        self._dz_from_slide_level = tuple(filter(native, range(self.level_count)))

        self.lowest_valid_level = next(i for i, dim in enumerate(self.level_dimensions) if dim[0] >= 240 or dim[1] >= 240) - 2 # for good measure
        
    @property
    def native_levels(self):
        return self._dz_from_slide_level

    @property
    def first_level(self):
        return self.lowest_valid_level

    def get_tile(self, level, address):
        """Return an RGB PIL.Image for a tile (not from cache), caching it first.

        level:     the Deep Zoom level.
        address:   the address of the tile within the level as a (col, row)
                   tuple."""
        col, row = address
        file_path = os.path.join(IMAGES_PATH, f'{self.image_id}_files/{level}/{col}_{row}.{self.format}')
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            # cache hit
            return Image.open(file_path)
    
        if level in self.native_levels:
            tile = DeepZoomGenerator.get_tile(self, level, address)
        else:
            # Dowsample this tile from native tiles if this is not a native tile so we only need to
            # extract each native tile one time.
            tile = self._generate_tile(level, address)

        # cache tile, but don't block before returning it
        threading.Thread(target=cache_tile, args=(tile, file_path, self.format)).start()
        
        return tile
        
    def _generate_tile(self, level, address):
        """Generate a non-native tile from native tiles (possibly up several levels)

        level:     the Deep Zoom level.
        address:   the address of the tile within the level as a (col, row)
                   tuple.""" 
        col, row = address
        x_count, y_count = self.level_tiles[level+1]
        xs = (2*col, 2*col+1 if x_count-1 > 2*col else None)
        ys = (2*row, 2*row+1 if y_count-1 > 2*row else None)
        parent_tiles = tuple(None if x is None or y is None else self.get_tile(level+1, (x, y))
            for x in xs for y in ys)
        uplevel_height = parent_tiles[0].size[1]
        if parent_tiles[1]: uplevel_height += parent_tiles[1].size[1]
        uplevel_width = parent_tiles[0].size[0]
        if parent_tiles[2]: uplevel_width += parent_tiles[2].size[0]
        new_tile = Image.new('RGB', (uplevel_width, uplevel_height))
        for i, parent_tile in enumerate(parent_tiles):
            if parent_tile:
                w, h = parent_tile.size
                x = i // 2 * self.tile_size
                y = i % 2 * self.tile_size
                new_tile.paste(parent_tile, (x, y, x + w, y + h))
        new_tile.thumbnail(self.get_tile_dimensions(level, address), Image.ANTIALIAS)
        return new_tile
    
    def get_dzi(self):
        return DeepZoomGenerator.get_dzi(self, self.format)

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
    print(response)
    return response

open_slides = {}

def load_slide(image_id, _format):
    if image_id in open_slides:
        return open_slides[image_id]
    dz = open_slides[image_id] = CachedDeepZoomGenerator(image_id, _format)
    return dz

def lambda_handler(event, context):
    try:
        image_path = event['path']
        # 170782.dzi
        # 170782_files/14/15_16.jpeg
        request = re.match(r'/images/(?P<image_id>\w+)((?P<dzi>\.dzi)|_files/(?P<level>\d{1,2})/(?P<col>\d{1,3})_(?P<row>\d{1,3})\.(?P<format>jpeg|png))', image_path)
        if not request:
            raise ValueError(f'Bad resource request: {image_path}')

        image_id = request.group('image_id')
        is_dzi_request = bool(request.group('dzi'))
        if is_dzi_request:
            try:
                _format = event['queryStringParameters']['fmt'].lower()
            except:
                _format = DEEPZOOM_FORMAT_DEFAULT
            dz = load_slide(image_id, _format)
            dzi = dz.get_dzi()
            return respond(dzi, content_type='application/xml')

        level = int(request.group('level'))
        col = int(request.group('col'))
        row = int(request.group('row'))
        _format = request.group('format')
        file_path = os.path.join(IMAGES_PATH, f'{image_id}_files/{level}/{col}_{row}.{_format}')
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            # cache hit
            result = open(file_path, 'rb').read()
        else:
            # cache miss
            dz = load_slide(image_id, _format)
            tile = dz.get_tile(level, (col, row))
            buf = BytesIO()
            tile.save(buf, _format, quality=DEEPZOOM_TILE_QUALITY)
            result = buf.getvalue()
        return respond(base64.b64encode(result), content_type=f'image/{_format}')
        
    except Exception as e:
        return respond(None, e, 400)

import boto3
import json
client = boto3.client('lambda')

def generate_tiles(image_id, level=None, address=None, _format=DEEPZOOM_FORMAT_DEFAULT):
    dz = load_slide(image_id, _format)

    if level and address:
        col, row = address
        # dz.get_tile() will load the image if it exists, so check here first to skip that
        file_path = os.path.join(IMAGES_PATH, f'{image_id}_files/{level}/{col}_{row}.{_format}')
        if not os.path.exists(file_path):
            dz.get_tile(level, (col, row))
    else:
        # get the levels immediately above the native ones (except the last one), and add in the 0 level
        levels = tuple(level + 1 for level in dz.native_levels[:-1])
        levels = (0,) + levels
        for level in levels:
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