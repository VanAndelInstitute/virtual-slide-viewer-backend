import os
import boto3
import json
from slidecache import load_slide, check_cache, DEEPZOOM_FORMAT_DEFAULT, TRACT_LEN, PARCEL_LEN
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ENV_TYPE = os.environ.get('ENV_TYPE', 'dev')
TILES_FUNCTION_NAME = os.environ.get('TILES_FUNCTION_NAME')
X = 0
Y = 1

def lambda_handler(event, context):
    """ Pre-compute a DeepZoom image from an SVS image and cache it.
        This function will recursively call itself to spin up many functions in parallel.
    """

    # A "tract" is a collection of "parcels", which is a collection of tiles. We compute multiple
    # parcels in a single lambda invocation to minimize overhead and optimize cost. We compute a 
    # parcel at a time to maximize use of the OpenSlide tile cache.
    depth = event.get('depth')
    if depth == 0:
        # 1. Given only an image ID, invoke a lambda for each row of each native level.
        image_id = event['image_id']
        dz = load_slide(image_id)
        lambda_client = boto3.client('lambda')
        for level in dz.native_levels:
            level_tracts = dz.level_tracts[level]
            for y in range(level_tracts[Y]):
                event = { 'image_id': image_id, 'depth': 1, 'level': level, 'tract': { 'y': y }, 'num_columns': level_tracts[X] }
                lambda_client.invoke(
                    FunctionName=TILES_FUNCTION_NAME,
                    InvocationType='Event',
                    LogType='None',
                    Payload=json.dumps(event),
                    Qualifier=ENV_TYPE
                )
    
    elif depth == 1:
        # 2. Given a level and a row, invoke a lambda for each column of the given row in this level.
        lambda_client = boto3.client('lambda')
        for x in range(event['num_columns']):
            event['tract']['x'] = x
            event['depth'] = 2
            lambda_client.invoke(
                FunctionName=TILES_FUNCTION_NAME,
                InvocationType='Event',
                LogType='None',
                Payload=json.dumps(event),
                Qualifier=ENV_TYPE
            )

    elif depth == 2:
        # 3. Given full coordinates for a tract, begin the process of generating tiles.
        image_id, level, tract = event['image_id'], event['level'], event['tract']
        dz = load_slide(image_id)
        level_tracts = dz.level_tracts[level]
        level_tiles = dz.level_tiles[level]
    
        # 4. Determine parcel coordinates and loop through all parcels in this tract
        remainder = { 'x': -(-level_tiles[X]//PARCEL_LEN)%TRACT_LEN, 'y': -(-level_tiles[Y]//PARCEL_LEN)%TRACT_LEN }
        tract_parcels = (TRACT_LEN,TRACT_LEN)
        if tract['x'] == level_tracts[X]-1 and remainder['x'] != 0:
            tract_parcels[X] = remainder['x']
        if tract['y'] == level_tracts[Y]-1 and remainder['y'] != 0:
            tract_parcels[Y] = remainder['y']
        parcels = [{ 'x': x, 'y': y } for x in range(tract_parcels[X]) for y in range(tract_parcels[Y])]
        remainder = { 'x': level_tiles[X] % PARCEL_LEN, 'y': level_tiles[Y] % PARCEL_LEN }
        for parcel in parcels:
            # 5. Determine tile coordinates and loop through all tiles in this parcel.
            num_cols = num_rows = PARCEL_LEN
            if tract['x'] == level_tracts[X]-1 and parcel['x'] == tract_parcels[X]-1 and remainder['x'] != 0:
                num_cols = remainder['x']
            if tract['y'] == level_tracts[Y]-1 and parcel['y'] == tract_parcels[Y]-1 and remainder['y'] != 0:
                num_rows = remainder['y']
            offset = { 'x': (tract['x']*TRACT_LEN+parcel['x'])*PARCEL_LEN, 'y': (tract['y']*TRACT_LEN+parcel['y'])*PARCEL_LEN }
            tile_addresses = [{ 'x': offset['x'] + x, 'y': offset['y'] + y }
                    for x in range(num_cols) for y in range(num_rows)]
            is_next_native_level = False
            while level >= 0 and not is_next_native_level:
                for tile in tile_addresses:
                    # dz.get_tile() will load the image if it exists, so check here first to skip that
                    file_path, cache_valid = check_cache(image_id, level, tile['x'], tile['y'], DEEPZOOM_FORMAT_DEFAULT)
                    if not cache_valid:
                        try:
                            dz.get_tile(level, (tile['x'], tile['y']))
                        except:
                            logger.info(((tile['x'], tile['y'])))
                            raise
                # 6. Now do the non-native levels below for this parcel, since a significant number of tiles will be
                #    in the tile cache already.
                level-=1
                tile_addresses = [{'x': t['x'] // 2, 'y': t['y'] // 2} for t in tile_addresses if t['x'] % 2 == 0 and t['y'] % 2 == 0]
                is_next_native_level = level in dz.native_levels

    else:
        logger.error(f'Recursion depth is {depth}')
        raise RecursionError