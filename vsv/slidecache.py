import os
import openslide
from openslide.deepzoom import DeepZoomGenerator
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

TRACT_LEN = 1
PARCEL_LEN = 16

class CachedDeepZoomGenerator(DeepZoomGenerator):
    def __init__(self, image_id, tile_size, overlap, _format):
        osr = openslide.open_slide(os.path.join(IMAGES_PATH, f'{image_id}.svs'))
        DeepZoomGenerator.__init__(self, osr, tile_size, overlap)
        
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

        l0_l_downsamples = tuple(int(round(d)) for d in osr.level_downsamples)
        # Total downsamples for each Deep Zoom level
        l0_z_downsamples = tuple(2 ** (self.level_count - dz_level - 1)
                    for dz_level in range(self.level_count))

        native = lambda dz_level: l0_z_downsamples[dz_level] in l0_l_downsamples
        self._dz_from_slide_level = tuple(filter(native, range(self.level_count)))

    @property
    def native_levels(self):
        return self._dz_from_slide_level

    @property
    def level_tracts(self):
        """ A list of (tracts_x, tracts_y) tuples for each Deep Zoom level. level_tracts[k] are the tile counts of level k.
            Round up using ceiling (reverse floor) division: -(-n//d)
        """
        tiles_to_tracts = lambda tile_dims: (-(-tile_dims[0] // (TRACT_LEN*PARCEL_LEN)), -(-tile_dims[1] // (TRACT_LEN*PARCEL_LEN)))
        return [*map(tiles_to_tracts, self.level_tiles)]

    def get_tile(self, level, address):
        """Return an RGB PIL.Image for a tile (not from cache), caching it first.

        level:     the Deep Zoom level.
        address:   the address of the tile within the level as a (col, row)
                   tuple."""
        col, row = address
        file_path, cache_valid = check_cache(self.image_id, level, col, row, self.format)
        tile = DeepZoomGenerator.get_tile(self, level, address)

        if not cache_valid:
            # cache tile - EFS is async, so this shouldn't be a blocking call
            tiledir = os.path.dirname(file_path)
            os.makedirs(tiledir, exist_ok=True)
            tile.save(file_path, self.format, quality=DEEPZOOM_TILE_QUALITY)
            logger.info(f'Cached tile: {file_path}')
        
        return tile
    
    def get_dzi(self):
        return DeepZoomGenerator.get_dzi(self, self.format)


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
