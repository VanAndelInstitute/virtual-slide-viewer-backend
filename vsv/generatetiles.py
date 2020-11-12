import os
import boto3
import json
from slidecache import load_slide, check_cache, DEEPZOOM_FORMAT_DEFAULT, TRACT_LEN, PARCEL_LEN

ENV_TYPE = os.environ.get('ENV_TYPE', 'dev')
TILES_FUNCTION_NAME = os.environ.get('TILES_FUNCTION_NAME')

def lambda_handler(event, context):
    """ Pre-compute a DeepZoom image from an SVS image and cache it.
        This function will recursively call itself to spin up many functions in parallel.
    """
    # 1. Get coordinates for a "tract", which is a collection of "parcels", which is a collection of
    #    tiles. We compute multiple parcels in a single lambda invocation to minimize overhead and
    #    optimize cost. We compute a parcel at a time to maximize use of the OpenSlide tile cache.
    tract_x, tract_y = event.get('tract_x'), event.get('tract_y')
    if tract_x:
        # 4. Given full coordinates for a tract, begin the process of generating tiles.
        image_id, level = event['image_id'], event['level']
        dz = load_slide(image_id)
        num_tracts_x, num_tracts_y = dz.level_tracts[level]
        num_tiles_x, num_tiles_y = dz.level_tiles[level]

        # 5. Determine parcel coordinates and loop through all parcels in this tract
        num_parcels_x = TRACT_LEN if tract_x == num_tracts_x-1 else -(-num_tiles_x//PARCEL_LEN) % TRACT_LEN
        num_parcels_y = TRACT_LEN if tract_y == num_tracts_y-1 else -(-num_tiles_y//PARCEL_LEN) % TRACT_LEN
        parcel_addresses = ((tract_x*TRACT_LEN+parcel_x, tract_y*TRACT_LEN+parcel_y)
                for parcel_x in range(num_parcels_x) for parcel_y in range(num_parcels_y))
        for parcel_x, parcel_y in parcel_addresses:
            # 6. Determine tile coordinates and loop through all tiles in this parcel.
            num_cols = PARCEL_LEN if parcel_x < num_parcels_x-1 else num_tiles_x % PARCEL_LEN
            num_rows = PARCEL_LEN if parcel_y < num_parcels_y-1 else num_tiles_y % PARCEL_LEN
            tile_addresses = ((tract_x*TRACT_LEN+parcel_x*PARCEL_LEN+col, tract_y*TRACT_LEN+parcel_y*PARCEL_LEN+row)
                    for col in range(num_cols) for row in range(num_rows))
            is_next_native_level = False
            while not is_next_native_level:
                for col, row in tile_addresses:
                    # dz.get_tile() will load the image if it exists, so check here first to skip that
                    file_path, cache_valid = check_cache(image_id, level, col, row, DEEPZOOM_FORMAT_DEFAULT)
                    if not cache_valid:
                        dz.get_tile(level, (col, row))
                # 7. Now do the non-native levels below for this parcel, since a significant number of tiles will be
                #    in the tile cache already.
                level-=1
                tile_addresses = filter(lambda x, y: x % 2 and y % 2) # reduce number of tiles to half plus remainder
                tile_addresses = map(lambda x, y: (x // 2, y // 2)) # lower level addresses are half of upper level
                is_next_native_level = level in dz.native_levels

    elif tract_y:
        # 3. Given a level and a row, invoke a lambda for each column of the given row in this level.
        for tract_x in range(event['level_tracts'][0]):
            event['tract_x'] = tract_x
            lambda_client = boto3.client('lambda')
            lambda_client.invoke(
                FunctionName=TILES_FUNCTION_NAME,
                InvocationType='Event',
                LogType='None',
                Payload=json.dumps(event),
                Qualifier=ENV_TYPE
            )
    else:
        # 2. Given only a level, invoke a lambda for each row of the level.
        for tract_y in range(event['level_tracts'][1]):
            event['tract_y'] = tract_y
            lambda_client = boto3.client('lambda')
            lambda_client.invoke(
                FunctionName=TILES_FUNCTION_NAME,
                InvocationType='Event',
                LogType='None',
                Payload=json.dumps(event),
                Qualifier=ENV_TYPE
            )