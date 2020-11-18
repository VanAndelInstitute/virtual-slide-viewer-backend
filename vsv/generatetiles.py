import os
import boto3
import json
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
from helpers import *
from PIL import Image

DEEPZOOM_FORMAT = 'jpeg'
DEEPZOOM_TILE_QUALITY = 70
X = 0
Y = 1

def lambda_handler(event, context):
    """ Pre-compute part of a DeepZoom image from an SVS image and cache it.
        This function is called many times in parallel, once for each tract.
        A "tract" is a collection of "parcels", which is a collection of tiles. We compute multiple
        parcels in a single lambda invocation to minimize overhead and optimize cost. We compute a 
        parcel at a time to maximize use of the OpenSlide tile cache.
    """
    image_id, levels, tract = event['image_id'], event['levels'], event.get('tract')
    dz = load_slide(image_id)
    level_tiles = dz.level_tiles[levels[-1]]
    if levels[0] == 0:
        tile_addresses = [(x,y) for x in range(level_tiles[X]) for y in range(level_tiles[Y])]
        process_tiles(image_id, dz, levels, tile_addresses)
        #process_region(image_id, dz, levels, (0,0), level_tiles)
    else:
        # Determine parcel coordinates and loop through all parcels in this tract
        level_tracts = dz.level_tracts[levels[-1]]
        remainder = (-(-level_tiles[X]//PARCEL_LEN)%TRACT_LEN,-(-level_tiles[Y]//PARCEL_LEN)%TRACT_LEN)
        tract_parcels = (remainder[X] if tract[X] == level_tracts[X]-1 and remainder[X] != 0 else TRACT_LEN,
                remainder[Y] if tract[Y] == level_tracts[Y]-1 and remainder[Y] != 0 else TRACT_LEN)
        parcels = [(x,y) for x in range(tract_parcels[X]) for y in range(tract_parcels[Y])]
        remainder = (level_tiles[X] % PARCEL_LEN, level_tiles[Y] % PARCEL_LEN)
        for parcel in parcels:
            # Determine tile coordinates and loop through all tiles in this parcel.
            num_cols = num_rows = PARCEL_LEN
            if tract[X] == level_tracts[X]-1 and parcel[X] == tract_parcels[X]-1 and remainder[X] != 0:
                num_cols = remainder[X]
            if tract[Y] == level_tracts[Y]-1 and parcel[Y] == tract_parcels[Y]-1 and remainder[Y] != 0:
                num_rows = remainder[Y]
            offset = ((tract[X]*TRACT_LEN+parcel[X])*PARCEL_LEN,(tract[Y]*TRACT_LEN+parcel[Y])*PARCEL_LEN)
            tile_addresses = [(offset[X] + x,offset[Y] + y) for x in range(num_cols) for y in range(num_rows)]
            process_tiles(image_id, dz, levels, tile_addresses)
            #process_region(image_id, dz, levels, t_location, (num_cols, num_rows))

# def process_region(image_id, dz, levels, t_location, t_size):
#     x, y = t_location
#     num_cols, num_rows = t_size
#     for level in reversed(levels):

#         # Read region
#         dz_size = get_region_size(dz, level, (x,y), (num_cols,num_rows))
#         args = get_region_parameters(dz, level, (x,y), dz_size)
#         region = dz.osr.read_region(*args)

#         # Apply on solid background
#         bg = Image.new('RGB', region.size, dz.bg_color)
#         region = Image.composite(region, bg, region)

#         # Scale to the correct size
#         if region.size != dz_size:
#             region.thumbnail(dz_size, Image.ANTIALIAS)
            
#         for col in range(num_cols):
#             for row in range(num_rows):
#                 x_size,y_size = get_region_size(dz, level, (col,row), (1,1))
#                 left,top = DEEPZOOM_TILE_SIZE * col, DEEPZOOM_TILE_SIZE * row
#                 right,bottom = left+x_size, top+y_size
#                 tile = region.crop((left,top,right,bottom))
#                 file_path = os.path.join(IMAGES_PATH, f'{image_id}_files/{level}/{col+x}_{row+y}.{DEEPZOOM_FORMAT}')
#                 tile.save(file_path, DEEPZOOM_FORMAT, quality=DEEPZOOM_TILE_QUALITY)
#                 logger.info(f'Cached tile: {file_path}')

#         # Now do the non-native levels below for this set of tiles, since a significant number of tiles will be
#         # in the tile cache already.
#         num_cols, num_rows = (num_cols+1)//2, (num_rows+1)//2
#         x, y = x//2, y//2

def process_tiles(image_id, dz, levels, tile_addresses):
    for level in reversed(levels):
        for (col, row) in tile_addresses:

            #tile = dz.get_tile(plevel, (col, row))
            # Read tile
            #args, z_size = dz._get_tile_info(level, (col, row))
            z_size = get_region_size(dz, level, (col, row), (1,1))
            args = get_region_parameters(dz, level, (col, row), z_size)
            tile = dz.osr.read_region(*args)

            # Apply on solid background
            bg = Image.new('RGB', tile.size, dz.bg_color)
            tile = Image.composite(tile, bg, tile)

            # Scale to the correct size
            if tile.size != z_size:
                tile.thumbnail(z_size, Image.ANTIALIAS)
            
            file_path = os.path.join(IMAGES_PATH, f'{image_id}_files/{level}/{col}_{row}.{DEEPZOOM_FORMAT}')
            tile.save(file_path, DEEPZOOM_FORMAT, quality=DEEPZOOM_TILE_QUALITY)
            logger.info(f'Cached tile: {file_path}')

        
        # Now do the non-native levels below for this set of tiles, since a significant number of tiles will be
        # in the tile cache already.
        tile_addresses = [(col//2,row//2) for (col,row) in tile_addresses if col%2==0 and row%2==0]
