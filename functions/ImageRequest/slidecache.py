import os
import openslide
from openslide.deepzoom import DeepZoomGenerator
from PIL import Image
import logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

IMAGES_PATH = os.environ.get('IMAGES_PATH', '/tmp')

class VsvDeepZoomGenerator(DeepZoomGenerator):
    def __init__(self, image_id, tile_size, overlap, _format):
        osr = openslide.open_slide(os.path.join(IMAGES_PATH, f'{image_id}.svs'))
        DeepZoomGenerator.__init__(self, osr, tile_size, overlap)
        
        self.osr = osr
        self.image_id = image_id
        self.tile_size = tile_size
        self.overlap = overlap
        self.format = _format
        if self.format != 'jpeg' and self.format != 'png':
            # Not supported by Deep Zoom
            raise ValueError(f'Unsupported format: {self.format}')

    def get_tile(self, level, address):
        """Return an RGB PIL.Image for a tile.

        level:     the Deep Zoom level.
        address:   the address of the tile within the level as a (col, row)
                   tuple."""
        col, row = address
        z_size = self.get_region_size(level, (col, row), (1,1))
        args = self.get_region_parameters(level, (col, row), z_size)
        tile = self._osr.read_region(*args)

        # Premultiply alpha channel
        tile = tile.convert('RGB')

        # Scale to the correct size
        if tile.size != z_size:
            tile.thumbnail(z_size, Image.ANTIALIAS)
        
        return tile
    
    def get_dzi(self):
        return DeepZoomGenerator.get_dzi(self, self.format)

    def get_associated_image(self, name, _format):
        return self.osr.associated_images.get(name).convert('RGB')

    def get_region_size(self, dz_level, address, t_size):
        col, row = address
        num_cols, num_rows = t_size
        col_lim, row_lim = self.level_tiles[dz_level]
        if col < 0 or col+num_cols-1 >= col_lim or row < 0 or row+num_rows-1 >= row_lim:
            raise ValueError("Invalid address")

        # Calculate top/left and bottom/right overlap
        left_overlap = self.overlap * int(col != 0)
        top_overlap = self.overlap * int(row != 0)
        right_overlap = self.overlap * int(col + num_cols != col_lim)
        bottom_overlap = self.overlap * int(row + num_rows != row_lim)

        # Get final size of the region
        w_lim, h_lim = self.level_dimensions[dz_level]
        w = num_cols * min(self.tile_size, w_lim - self.tile_size * col) + left_overlap + right_overlap
        h = num_rows * min(self.tile_size, h_lim - self.tile_size * row) + top_overlap + bottom_overlap
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
        left_overlap = self.overlap * int(col != 0)
        top_overlap = self.overlap * int(row != 0)
        
        # Obtain the region coordinates in {slide_level} reference frame. Expand by top/left overlap if exists.
        xl = dz_downsample * ((self.tile_size * col) - left_overlap)
        yl = dz_downsample * ((self.tile_size * row) - top_overlap)
        # OpenSlide.read_region wants coordinates in level 0 reference frame.
        x0, y0 = l_downsample * xl, l_downsample * yl
        # OpenSlide.read_region wants dimensions in {slide_level} reference frame.
        w = min(dz_downsample * x_size, x_lim - xl)
        h = min(dz_downsample * y_size, y_lim - yl)
            
        # Return read_region() parameters plus tile size for final scaling
        return (x0,y0), slide_level, (w,h)
