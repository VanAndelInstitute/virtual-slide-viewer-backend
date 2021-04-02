import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";

const REGION = "us-east-2";

/**
 * Parse a 'Content-Range' header value to its start, end, and total parts
 * @param {String} rawContentRange the raw string to parse from
 * @returns {Object} the parsed parts
 */
function parseContentRange(rawContentRange) {
  const [, start, end, total] = rawContentRange.match(/bytes (\d+)-(\d+)\/(\d+)/);
  return {
    start: parseInt(start, 10),
    end: parseInt(end, 10),
    total: parseInt(total, 10),
  };
}

class RemoteSource {
  /**
   *
   * @param {string} url
   * @param {object} headers
   * @param {object} credentials
   */
  constructor(url, headers, credentials) {
    this.url = url;
    this.headers = headers;
    this.credentials = credentials;
    this._fileSize = null;
    this.s3 = new S3Client({ region: REGION });
  }

  /**
   *
   * @param {Slice[]} slices
   */
  async fetch(slices, signal) {
    // make a single request for each slice
    return await Promise.all(
      slices.map((slice) => this.fetchSlice(slice, signal)),
    );
  }

  async fetchSlice(slice, signal) {
    let request_call = new Promise(async (resolve, reject) => {
      const { offset, length } = slice;
      const response = await this.s3.send(
        new GetObjectCommand({
          Bucket: 'vsv-svs-s3-test',
          Key: '1001611.svs',
          Range: `bytes=${offset}-${offset + length}`
        })
      );
      let chunks_of_data = [];
      response.Body.on('data', (fragments) => {
        chunks_of_data.push(fragments);
      });
  
      response.Body.on('end', () => {
        let response_body = Buffer.concat(chunks_of_data);
        // promise resolved on success
        resolve(response_body);
      });
  
      response.Body.on('error', (error) => {
        // promise rejected on error
        reject(error);
      });
    });
    try {
      return await request_call;
    } catch (error) {
      // error handling.
      console.error(error);
    }
  }

  get fileSize() {
    return this._fileSize;
  }

  async close() {
    // no-op by default
  }
}

/**
 *
 * @param {string} url
 * @param {object} options
 */
export function makeRemoteSource(url, { headers = {}, credentials } = {}) {
  return new RemoteSource(url, headers, credentials);
}
