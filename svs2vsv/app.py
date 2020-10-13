import os
import traceback as tb
import base64
import re
from io import BytesIO
import openslide
from openslide import ImageSlide, open_slide
from openslide.deepzoom import DeepZoomGenerator

DEEPZOOM_FORMAT = 'jpeg'
DEEPZOOM_TILE_SIZE = 254
DEEPZOOM_OVERLAP = 1
DEEPZOOM_LIMIT_BOUNDS = True
DEEPZOOM_TILE_QUALITY = 75
ALLOW_ORIGIN = os.environ['ALLOW_ORIGIN']
IMAGES_PATH = os.environ['IMAGES_PATH']

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
    print(content_type)
    if content_type:
        response['headers']['Content-Type'] = content_type
        if content_type.startswith('image'):
            response['isBase64Encoded'] = True
    print(response)
    return response

slides = {}

def load_slide(image_id):
    slide = open_slide(os.path.join(IMAGES_PATH, f'{image_id}.svs'))
    mpp_x = slide.properties[openslide.PROPERTY_NAME_MPP_X]
    mpp_y = slide.properties[openslide.PROPERTY_NAME_MPP_Y]
    slide_mpp = (float(mpp_x) + float(mpp_y)) / 2
    slides[image_id] = DeepZoomGenerator(slide)
    
def get_dzi(image_id):
    format = DEEPZOOM_FORMAT
    dzi = slides[image_id].get_dzi(format)
    return respond(dzi, content_type='application/xml')

def get_tile(image_id, level, col, row, format):
    format = format.lower()
    if format != 'jpeg' and format != 'png':
        # Not supported by Deep Zoom
        raise ValueError(f'Unsupported format: {format}')
    tile = slides[image_id].get_tile(level, (col, row))
    buf = BytesIO()
    tile.save(buf, format, quality=DEEPZOOM_TILE_QUALITY)
    return respond(base64.b64encode(buf.getvalue()), content_type=f'image/{format}')

def lambda_handler(event, context):
    try:
        resource_path = event['path']
        request = re.match(r'/images/(?P<image_id>\w+)((?P<ext>\.dzi)|_files/(?P<level>\d{1,2})/(?P<col>\d{1,3})_(?P<row>\d{1,3})\.(?P<format>jpeg|png))', resource_path)
        if not request:
            raise ValueError(f'Bad resource request: {resource_path}')

        image_id = request.group('image_id')
        if not image_id in slides:
            load_slide(image_id)
        
        if request.group('ext') == '.dzi':
            return get_dzi(image_id)

        level = int(request.group('level'))
        col = int(request.group('col'))
        row = int(request.group('row'))
        format = request.group('format')
        return get_tile(image_id, level, col, row, format)
    except Exception as e:
        return respond(None, e, 400)
