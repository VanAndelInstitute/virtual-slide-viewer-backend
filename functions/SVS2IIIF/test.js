import { fromUrl } from './tiff.js';
import fs from 'fs';

fromUrl('http://vsv-svs-s3-test.s3-website.us-east-2.amazonaws.com/1001611.svs')
  .then(async (tiff) => {
    let img = await tiff.getImage(1);
    let ifd = img.getFileDirectory();
    console.log(ifd);
    let data = await img.readRasters();
    console.log(typeof data);
    console.log(`Dimensions: ${data.width} x ${data.height}`)
    //fs.writeFileSync("thumbnail.jpg", jpg, "binary");
  });