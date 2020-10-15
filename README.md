# Backend for Virtual Slide Viewer
The VSV backend is implemented as an AWS Serverless application. It mounts an EFS share with SVS files into a Lambda function and handles API Gateway requests
for DeepZoom tiles by using [OpenSeadragon](https://openseadragon.github.io/) to fetch TIFF tiles and [Pillow-SIMD](https://github.com/uploadcare/pillow-simd) to shrink tiles as needed.

## Build and deploy
The infrastructure code is currently a SAM template.

`$ sam build -u`

`$ sam deploy`


## General workflow for Virtual Slide Viewer deployments
1. Scanner dumps files onto ScanScope Workstation into a locally-mounted EFS share
2.	**Scanner technician reviews images for scanning errors**
    - searches for new (unsent) slides
    - deletes and rescans failed slide scans
    - fixes slide/case IDs, if incorrect or missing
    - marks slides to send (metadata) to CDR
3.	**Pathologist reviews slides**

## Related projects
- [Virtual Slide Viewer frontend](https://github.com/VanAndelInstitute/virtual-slide-viewer)

## Performance testing
| Configuration                               | Python 3.8 | Pillow-SIMD | OpenSlide | Lambda | EFS | Is it fast? | Link to code     | Resource format                 |
|---------------------------------------------|------------|-------------|-----------|--------|-----|-------------|------------------|---------------------------------|
| Lambda+Python+SVS images on EFS             | x          | x           | x         | x      | x   | No          | VSV              | /images/170782.dzi              |
| Lambda+Python+S3 DeepZoom pyramid files     | x          |             |           | x      |     | Yes         | VSV              | /images/170782/DeepZoom.dzi     |
| Lambda+Python+DeepZoom pyramid files on EFS | x          |             |           | x      | x   | Yes         |                  | /images/170782/DeepZoom.dzi     |
| EC2+Python+SVS images on EFS                | x          | x           | x         |        | x   | No          | openslide-python | /slide.dzi                      |
| EC2+Python+DeepZoom pyramid files on EFS    | x          |             |           |        | x   | Yes         | VSV              | /170782/DeepZoom.dzi            |
| EC2+Python+SVS images on EBS                | x          | x           | x         |        |     | No          | openslide-python | /slide.dzi                      |