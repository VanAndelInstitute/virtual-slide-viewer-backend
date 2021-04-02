/* eslint max-len: ["error", { "code": 120 }] */
import JpegDecoder from './jpeg.js';
import { resampleInterleaved } from './resample.js';

/**
 * TIFF sub-file image.
 */
class TIFFImage {
  /**
   * @constructor
   * @param {Object} fileDirectory The parsed file directory
   * @param {DataView} dataView The DataView for the underlying file.
   * @param {Boolean} littleEndian Whether the file is encoded in little or big endian
   * @param {Boolean} cache Whether or not decoded tiles shall be cached
   * @param {Source} source The datasource to read from
   */
  constructor(fileDirectory, dataView, littleEndian, cache, source) {
    this.fileDirectory = fileDirectory;
    this.dataView = dataView;
    this.littleEndian = littleEndian;
    this.tiles = cache ? {} : null;
    this.isTiled = !fileDirectory.StripOffsets;
    this.source = source;
  }

  /**
   * Returns the associated parsed file directory.
   * @returns {Object} the parsed file directory
   */
  getFileDirectory() {
    return this.fileDirectory;
  }

  /**
   * Returns the width of the image.
   * @returns {Number} the width of the image
   */
  getWidth() {
    return this.fileDirectory.ImageWidth;
  }

  /**
   * Returns the height of the image.
   * @returns {Number} the height of the image
   */
  getHeight() {
    return this.fileDirectory.ImageLength;
  }

  /**
   * Returns the number of samples per pixel.
   * @returns {Number} the number of samples per pixel
   */
   getSamplesPerPixel() {
    return typeof this.fileDirectory.SamplesPerPixel !== 'undefined'
      ? this.fileDirectory.SamplesPerPixel : 1;
  }

  /**
   * Returns the width of each tile.
   * @returns {Number} the width of each tile
   */
  getTileWidth() {
    return this.isTiled ? this.fileDirectory.TileWidth : this.getWidth();
  }

  /**
   * Returns the height of each tile.
   * @returns {Number} the height of each tile
   */
  getTileHeight() {
    if (this.isTiled) {
      return this.fileDirectory.TileLength;
    }
    if (typeof this.fileDirectory.RowsPerStrip !== 'undefined') {
      return Math.min(this.fileDirectory.RowsPerStrip, this.getHeight());
    }
    return this.fileDirectory.TileLength;
  }

  getBlockWidth() {
    return this.getTileWidth();
  }

  getBlockHeight(y) {
    if (this.isTiled || (y + 1) * this.getTileHeight() <= this.getHeight()) {
      return this.getTileHeight();
    } else {
      return this.getHeight() - (y * this.getTileHeight());
    }
  }

  /**
   * Returns the decoded strip or tile.
   * @param {Number} x the strip or tile x-offset
   * @param {Number} y the tile y-offset (0 for stripped images)
   * @param {AbortSignal} [signal] An AbortSignal that may be signalled if the request is
   *                               to be aborted
   * @returns {Promise.<ArrayBuffer>}
   */
  async getTileOrStrip(x, y, signal) {
    const numTilesPerRow = Math.ceil(this.getWidth() / this.getTileWidth());
    const { tiles } = this;
    let index = (y * numTilesPerRow) + x;

    let offset;
    let byteCount;
    if (this.isTiled) {
      offset = this.fileDirectory.TileOffsets[index];
      byteCount = this.fileDirectory.TileByteCounts[index];
    } else {
      offset = this.fileDirectory.StripOffsets[index];
      byteCount = this.fileDirectory.StripByteCounts[index];
    }
    const slice = (await this.source.fetch([{ offset, length: byteCount }], signal))[0];
    
    let request;
    if (tiles === null || !tiles[index]) {
      request = (async () => {
        let decoder = new JpegDecoder(this.fileDirectory);
        let data = await decoder.decode(this.fileDirectory, slice);
        return data;
      })();

      // set the cache
      if (tiles !== null) {
        tiles[index] = request;
      }
    } else {
      // get from the cache
      request = tiles[index];
    }

    // cache the tile request
    return { x, y, data: await request };
  }

  /**
   * Internal read function.
   * @private
   * @param {Array} imageWindow The image window in pixel coordinates
   * @param {Array} samples The selected samples (0-based indices)
   * @param {TypedArray} valueArray The array to write into
   * @param {number} width the width of window to be read into
   * @param {number} height the height of window to be read into
   * @param {number} resampleMethod the resampling method to be used when interpolating
   * @param {AbortSignal} [signal] An AbortSignal that may be signalled if the request is
   *                               to be aborted
   * @returns {Promise<TypedArray[]>|Promise<TypedArray>}
   */
   async _readRaster(imageWindow, valueArray, width, height, resampleMethod, signal) {
    const tileWidth = this.getTileWidth();
    const tileHeight = this.getTileHeight();

    const minXTile = Math.max(Math.floor(imageWindow[0] / tileWidth), 0);
    const maxXTile = Math.min(
      Math.ceil(imageWindow[2] / tileWidth),
      Math.ceil(this.getWidth() / this.getTileWidth()),
    );
    const minYTile = Math.max(Math.floor(imageWindow[1] / tileHeight), 0);
    const maxYTile = Math.min(
      Math.ceil(imageWindow[3] / tileHeight),
      Math.ceil(this.getHeight() / this.getTileHeight()),
    );
    const windowWidth = imageWindow[2] - imageWindow[0];
    const samplesPerPixel = this.getSamplesPerPixel();
    const promises = [];

    for (let yTile = minYTile; yTile < maxYTile; ++yTile) {
      for (let xTile = minXTile; xTile < maxXTile; ++xTile) {
        for (let sampleIndex = 0; sampleIndex < samplesPerPixel; ++sampleIndex) {
          const si = sampleIndex;
          const promise = this.getTileOrStrip(xTile, yTile, signal);
          promises.push(promise);
          promise.then((tile) => {
            const buffer = tile.data;
            const dataView = new DataView(buffer);
            const blockHeight = this.getBlockHeight(tile.y);
            const firstLine = tile.y * tileHeight;
            const firstCol = tile.x * tileWidth;
            const lastLine = firstLine + blockHeight;
            const lastCol = (tile.x + 1) * tileWidth;

            const ymax = Math.min(blockHeight, blockHeight - (lastLine - imageWindow[3]));
            const xmax = Math.min(tileWidth, tileWidth - (lastCol - imageWindow[2]));

            for (let y = Math.max(0, imageWindow[1] - firstLine); y < ymax; ++y) {
              for (let x = Math.max(0, imageWindow[0] - firstCol); x < xmax; ++x) {
                const pixelOffset = ((y * tileWidth) + x) * samplesPerPixel;
                const value = dataView.getUint8(pixelOffset + si);

                let windowCoordinate = ((y + firstLine - imageWindow[1]) * windowWidth * samplesPerPixel)
                  + ((x + firstCol - imageWindow[0]) * samplesPerPixel)
                  + si;
                valueArray[windowCoordinate] = value;
              }
            }
          });
        }
      }
    }
    await Promise.all(promises);

    if ((width && (imageWindow[2] - imageWindow[0]) !== width)
        || (height && (imageWindow[3] - imageWindow[1]) !== height)) {
      let resampled = resampleInterleaved(
        valueArray,
        imageWindow[2] - imageWindow[0],
        imageWindow[3] - imageWindow[1],
        width, height,
        samplesPerPixel,
        resampleMethod,
      );
      resampled.width = width;
      resampled.height = height;
      return resampled;
    }

    valueArray.width = width || imageWindow[2] - imageWindow[0];
    valueArray.height = height || imageWindow[3] - imageWindow[1];

    return valueArray;
  }

  /**
   * Reads raster data from the image. This function reads all selected samples
   * into a single combined array. When provided, only a subset
   * of the raster is read for each sample.
   *
   * @param {Object} [options={}] optional parameters
   * @param {Array} [options.window=whole image] the subset to read data from.
   * @param {number} [options.width] The desired width of the output. When the width is
   *                                 not the same as the images, resampling will be
   *                                 performed.
   * @param {number} [options.height] The desired height of the output. When the width
   *                                  is not the same as the images, resampling will
   *                                  be performed.
   * @param {string} [options.resampleMethod='nearest'] The desired resampling method.
   * @param {number|number[]} [options.fillValue] The value to use for parts of the image
   *                                              outside of the images extent. When
   *                                              multiple samples are requested, an
   *                                              array of fill values can be passed.
   * @param {AbortSignal} [options.signal] An AbortSignal that may be signalled if the request is
   *                                       to be aborted
   * @returns {Promise.<(TypedArray)>} the decoded array as a promise
   */
  async readRasters({
    window: wnd,
    width, height, resampleMethod, fillValue, signal,
  } = {}) {
    const imageWindow = wnd || [0, 0, this.getWidth(), this.getHeight()];

    // check parameters
    if (imageWindow[0] > imageWindow[2] || imageWindow[1] > imageWindow[3]) {
      throw new Error('Invalid subsets');
    }

    const imageWindowWidth = imageWindow[2] - imageWindow[0];
    const imageWindowHeight = imageWindow[3] - imageWindow[1];
    const numPixels = imageWindowWidth * imageWindowHeight;
    const samplesPerPixel = this.getSamplesPerPixel();

    let valueArray = new Uint8Array(numPixels * samplesPerPixel);
    if (fillValue) {
      valueArray.fill(fillValue);
    }

    return await this._readRaster(
      imageWindow, valueArray, width, height, resampleMethod, signal,
    );
  }

  /**
   * Returns the image origin as a XYZ-vector. When the image has no affine
   * transformation, then an exception is thrown.
   * @returns {Array} The origin as a vector
   */
  getOrigin() {
    const tiePoints = this.fileDirectory.ModelTiepoint;
    const modelTransformation = this.fileDirectory.ModelTransformation;
    if (tiePoints && tiePoints.length === 6) {
      return [
        tiePoints[3],
        tiePoints[4],
        tiePoints[5],
      ];
    }
    if (modelTransformation) {
      return [
        modelTransformation[3],
        modelTransformation[7],
        modelTransformation[11],
      ];
    }
    throw new Error('The image does not have an affine transformation.');
  }

  /**
   * Returns the image resolution as a XYZ-vector. When the image has no affine
   * transformation, then an exception is thrown.
   * @param {TIFFImage} [referenceImage=null] A reference image to calculate the resolution from
   *                                             in cases when the current image does not have the
   *                                             required tags on its own.
   * @returns {Array} The resolution as a vector
   */
  getResolution(referenceImage = null) {
    const modelPixelScale = this.fileDirectory.ModelPixelScale;
    const modelTransformation = this.fileDirectory.ModelTransformation;

    if (modelPixelScale) {
      return [
        modelPixelScale[0],
        -modelPixelScale[1],
        modelPixelScale[2],
      ];
    }
    if (modelTransformation) {
      return [
        modelTransformation[0],
        modelTransformation[5],
        modelTransformation[10],
      ];
    }

    if (referenceImage) {
      const [refResX, refResY, refResZ] = referenceImage.getResolution();
      return [
        refResX * referenceImage.getWidth() / this.getWidth(),
        refResY * referenceImage.getHeight() / this.getHeight(),
        refResZ * referenceImage.getWidth() / this.getWidth(),
      ];
    }

    throw new Error('The image does not have an affine transformation.');
  }

  /**
   * Returns the image bounding box as an array of 4 values: min-x, min-y,
   * max-x and max-y. When the image has no affine transformation, then an
   * exception is thrown.
   * @returns {Array} The bounding box
   */
  getBoundingBox() {
    const origin = this.getOrigin();
    const resolution = this.getResolution();

    const x1 = origin[0];
    const y1 = origin[1];

    const x2 = x1 + (resolution[0] * this.getWidth());
    const y2 = y1 + (resolution[1] * this.getHeight());

    return [
      Math.min(x1, x2),
      Math.min(y1, y2),
      Math.max(x1, x2),
      Math.max(y1, y2),
    ];
  }
}

export default TIFFImage;
