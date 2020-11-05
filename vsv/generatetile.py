from slidecache import load_slide, check_cache

def lambda_handler(event, context):
    """ Pre-compute a tile from an SVS image and cache it.
    """
    image_id, level, col, row, _format = event

    # dz.get_tile() will load the image if it exists, so check here first to skip that
    file_path, cache_valid = check_cache(image_id, level, col, row, _format)
    if not cache_valid:
        dz = load_slide(image_id)
        dz.get_tile(level, (col, row))