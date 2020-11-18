import os
import openslide
from openslide.deepzoom import DeepZoomGenerator
from PIL import Image
import xml.etree.ElementTree as xml
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DEEPZOOM_FORMAT_DEFAULT = 'jpeg'
DEEPZOOM_TILE_SIZE_DEFAULT = 254
DEEPZOOM_OVERLAP_DEFAULT = 1
DEEPZOOM_LIMIT_BOUNDS = False
DEEPZOOM_TILE_QUALITY = 70
IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')
ENV_TYPE = os.environ.get('ENV_TYPE', 'dev')


class CachedDeepZoomGenerator(DeepZoomGenerator):
    def __init__(self, image_id, tile_size, overlap, _format):
        osr = openslide.open_slide(os.path.join(IMAGES_PATH, f'{image_id}.svs'))
        DeepZoomGenerator.__init__(self, osr, tile_size, overlap)
        
        self.osr = osr
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
        z_size = self.get_region_size(level, (col, row), (1,1))
        args = self.get_region_parameters(level, (col, row), z_size)
        tile = self._osr.read_region(*args)

        # Premultiply alpha channel
        tile = tile.convert('RGB')

        # Scale to the correct size
        if tile.size != z_size:
            tile.thumbnail(z_size, Image.ANTIALIAS)
            
        if not cache_valid:
            # cache tile - EFS is async, so this shouldn't be a blocking call
            tiledir = os.path.dirname(file_path)
            os.makedirs(tiledir, exist_ok=True)
            tile.save(file_path, self.format, quality=DEEPZOOM_TILE_QUALITY)
            logger.info(f'Cached tile: {file_path}')
        
        return tile
    
    def get_dzi(self):
        return DeepZoomGenerator.get_dzi(self, self.format)

    def get_associated_image(self, name, _format):
        image = self.osr.associated_images.get(name).convert('RGB')
        imagedir = os.path.join(IMAGES_PATH, f'{self.image_id}_files/')
        os.makedirs(imagedir, exist_ok=True)
        image.save(os.path.join(imagedir, f'{name}.{_format}'))
        return image

    def get_region_size(self, dz_level, address, t_size):
        col, row = address
        num_cols, num_rows = t_size
        col_lim, row_lim = self.level_tiles[dz_level]
        if col < 0 or col+num_cols-1 >= col_lim or row < 0 or row+num_rows-1 >= row_lim:
            raise ValueError("Invalid address")

        # Calculate top/left and bottom/right overlap
        left_overlap = DEEPZOOM_OVERLAP_DEFAULT * int(col != 0)
        top_overlap = DEEPZOOM_OVERLAP_DEFAULT * int(row != 0)
        right_overlap = DEEPZOOM_OVERLAP_DEFAULT * int(col + num_cols != col_lim)
        bottom_overlap = DEEPZOOM_OVERLAP_DEFAULT * int(row + num_rows != row_lim)

        # Get final size of the region
        w_lim, h_lim = self.level_dimensions[dz_level]
        w = num_cols * min(DEEPZOOM_TILE_SIZE_DEFAULT, w_lim - DEEPZOOM_TILE_SIZE_DEFAULT * col) + left_overlap + right_overlap
        h = num_rows * min(DEEPZOOM_TILE_SIZE_DEFAULT, h_lim - DEEPZOOM_TILE_SIZE_DEFAULT * row) + top_overlap + bottom_overlap
        return w, h

    def get_best_slide_level_for_dz_level(self, dz_level):
        downsample = 2**(self.level_count-dz_level-1)
        for i in range(self._osr.level_count):
            if round(downsample) < round(self._osr.level_downsamples[i]):
                return 0 if i == 0 else i-1
        return self._osr.level_count - 1

    def get_region_parameters(self, dz_level, address, region_size):
        col, row = address
        x_size, y_size = region_size

        # Get preferred slide level
        slide_level = self.get_best_slide_level_for_dz_level(dz_level)
        l_downsample = round(self._osr.level_downsamples[slide_level])
        dz_downsample = int(2**(self.level_count-dz_level-1) / l_downsample)
        x_lim, y_lim = self._osr.level_dimensions[slide_level]

        # Calculate top/left and bottom/right overlap
        left_overlap = DEEPZOOM_OVERLAP_DEFAULT * int(col != 0)
        top_overlap = DEEPZOOM_OVERLAP_DEFAULT * int(row != 0)
        
        # Obtain the region coordinates in {slide_level} reference frame. Expand by top/left overlap if exists.
        xl = dz_downsample * ((DEEPZOOM_TILE_SIZE_DEFAULT * col) - left_overlap)
        yl = dz_downsample * ((DEEPZOOM_TILE_SIZE_DEFAULT * row) - top_overlap)
        # OpenSlide.read_region wants coordinates in level 0 reference frame.
        x0, y0 = l_downsample * xl, l_downsample * yl
        # OpenSlide.read_region wants dimensions in {slide_level} reference frame.
        w = min(dz_downsample * x_size, x_lim - xl)
        h = min(dz_downsample * y_size, y_lim - yl)
            
        # Return read_region() parameters plus tile size for final scaling
        return (x0,y0), slide_level, (w,h)

open_slides = {}

def load_slide(image_id, tile_size=None, overlap=None, _format=None):
    if image_id in open_slides:
        return open_slides[image_id]

    # set up tile params
    invalidate_cache = False
    dzi_path = os.path.join(IMAGES_PATH, f'{image_id}.dzi')
    saved_tile_size = tile_size
    saved_overlap = overlap
    saved_format = _format
    try:
        tree = xml.parse(dzi_path)
        root = tree.getroot()
        saved_tile_size = int(root.get('TileSize'))
        saved_overlap = int(root.get('Overlap'))
        saved_format = root.get('Format')
        if tile_size is not None and saved_tile_size != tile_size or overlap is not None and saved_overlap != overlap or _format is not None and saved_format != _format:
            invalidate = True
    except:
        invalidate_cache = True

    tile_size = tile_size or saved_tile_size or DEEPZOOM_TILE_SIZE_DEFAULT
    overlap = overlap if overlap is not None else saved_overlap or DEEPZOOM_OVERLAP_DEFAULT
    _format = _format or saved_format or DEEPZOOM_FORMAT_DEFAULT
    dz = open_slides[image_id] = CachedDeepZoomGenerator(image_id, tile_size, overlap, _format)

    if invalidate_cache:
        dzi_path = os.path.join(IMAGES_PATH, f'{image_id}.dzi')
        with open(dzi_path, 'wt', encoding='utf-8') as f:
            f.write(dz.get_dzi()) # this invalidates any cached tiles older than this write

    return dz

def check_cache(image_id, level, col, row, _format):
    dzi_path = os.path.join(IMAGES_PATH, f'{image_id}.dzi')
    if not os.path.exists(dzi_path):
        return None, False
    cache_lmtime = os.path.getmtime(dzi_path)
    file_path = os.path.join(IMAGES_PATH, f'{image_id}_files/{level}/{col}_{row}.{_format}')
    cache_valid = os.path.exists(file_path) and os.path.getsize(file_path) > 0 and os.path.getmtime(file_path) >= cache_lmtime
    return file_path, cache_valid
