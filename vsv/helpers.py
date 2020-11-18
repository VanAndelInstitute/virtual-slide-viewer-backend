import os
import math
import openslide
from openslide.deepzoom import DeepZoomGenerator

DEEPZOOM_FORMAT = 'jpeg'
DEEPZOOM_TILE_SIZE = 254
DEEPZOOM_OVERLAP = 1
IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')
TRACT_LEN = 4
PARCEL_LEN = 8
X = 0
Y = 1

open_slides = {}

def load_slide(image_id):
    if image_id not in open_slides:
        open_slides[image_id] = openslide.open_slide(os.path.join(IMAGES_PATH, f'{image_id}.svs'))

    osr = open_slides[image_id]
    dz = DeepZoomGenerator(osr, DEEPZOOM_TILE_SIZE, DEEPZOOM_OVERLAP)
    setattr(dz, 'osr', osr)
    
    l0_l_downsamples = tuple(int(round(d)) for d in osr.level_downsamples)
    # Total downsamples for each Deep Zoom level
    l0_z_downsamples = [2**(dz.level_count-dz_level-1) for dz_level in range(dz.level_count)]
    native_levels = [l for l in range(dz.level_count) if l0_z_downsamples[l] in l0_l_downsamples]
    setattr(dz, 'native_levels', native_levels)
    level_tracts = [(-(-cols // (TRACT_LEN*PARCEL_LEN)), -(-rows // (TRACT_LEN*PARCEL_LEN))) for (cols, rows) in dz.level_tiles]
    setattr(dz, 'level_tracts', level_tracts)
    bg_color = '#' + osr.properties.get(openslide.PROPERTY_NAME_BACKGROUND_COLOR, 'ffffff')
    setattr(dz, 'bg_color', bg_color)
    return dz

def get_region_size(dz, dz_level, address, t_size):
    col, row = address
    num_cols, num_rows = t_size
    col_lim, row_lim = dz.level_tiles[dz_level]
    if col < 0 or col+num_cols-1 >= col_lim or row < 0 or row+num_rows-1 >= row_lim:
        raise ValueError("Invalid address")

    # Calculate top/left and bottom/right overlap
    left_overlap = DEEPZOOM_OVERLAP * int(col != 0)
    top_overlap = DEEPZOOM_OVERLAP * int(row != 0)
    right_overlap = DEEPZOOM_OVERLAP * int(col + num_cols != col_lim)
    bottom_overlap = DEEPZOOM_OVERLAP * int(row + num_rows != row_lim)

    # Get final size of the region
    w_lim, h_lim = dz.level_dimensions[dz_level]
    w = num_cols * min(DEEPZOOM_TILE_SIZE, w_lim - DEEPZOOM_TILE_SIZE * col) + left_overlap + right_overlap
    h = num_rows * min(DEEPZOOM_TILE_SIZE, h_lim - DEEPZOOM_TILE_SIZE * row) + top_overlap + bottom_overlap
    return w, h

def get_best_level_for_downsample(osr, downsample):
    for i in range(osr.level_count):
        if round(downsample) < round(osr.level_downsamples[i]):
            return 0 if i == 0 else i-1
    return osr.level_count - 1

def get_region_parameters(dz, dz_level, address, region_size):
    col, row = address
    
    # Get preferred slide level
    slide_level = get_best_level_for_downsample(dz.osr, 2**(dz.level_count-dz_level-1))
    l_downsample = round(dz.osr.level_downsamples[slide_level])
    dz_downsample = int(2**(dz.level_count-dz_level-1) / l_downsample)
    l_lim = dz.osr.level_dimensions[slide_level]

    # Calculate top/left and bottom/right overlap
    left_overlap = DEEPZOOM_OVERLAP * int(col != 0)
    top_overlap = DEEPZOOM_OVERLAP * int(row != 0)
    
    # Obtain the region coordinates in {slide_level} reference frame. Expand by top/left overlap if exists.
    xl = dz_downsample * ((DEEPZOOM_TILE_SIZE * col) - left_overlap)
    yl = dz_downsample * ((DEEPZOOM_TILE_SIZE * row) - top_overlap)
    # OpenSlide.read_region wants coordinates in level 0 reference frame.
    x0, y0 = l_downsample * xl, l_downsample * yl
    # OpenSlide.read_region wants dimensions in {slide_level} reference frame.
    w = min(dz_downsample * region_size[X], l_lim[X] - xl)
    h = min(dz_downsample * region_size[Y], l_lim[Y] - yl)
        
    # Return read_region() parameters plus tile size for final scaling
    return (x0,y0), slide_level, (w,h)
