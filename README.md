# Backend for Virtual Slide Viewer
The VSV backend is implemented as an AWS Serverless application. It mounts an EFS share with SVS files into a Lambda function and handles API Gateway requests
for DeepZoom tiles by using [OpenSeadragon](https://openseadragon.github.io/) to fetch TIFF tiles and [Pillow-SIMD](https://github.com/uploadcare/pillow-simd) to shrink tiles as needed.

## Build and deploy
The infrastructure code is currently a SAM template.

`$ sam build -u`

`$ sam deploy`


## General workflow for Virtual Slide Viewer deployments
1. Aperio scanner dumps SVS images onto local ScanScope workstation storage
1. AWS DataSync agent transfers SVS files to Amazon EFS
1. Amazon EventBridge rule forwards file transfer event to AWS Lambda
1. AWS Lambda:
    - extracts label and thumbnail images from SVS file
    - extracts image metadata from TIFF tags and reads barcode from label image
    - uploads metadata to Amazon DynamoDB table
    - extracts DeepZoom tiles from SVS file and stores them as JPEGs in EFS
5.	**Scanner technician reviews images for scanning errors**
    - searches for new (unsent) slides
    - deletes and rescans failed slide scans
    - fixes slide/case IDs, if incorrect or missing
    - marks slides to send (metadata) to CDR
6.	**Pathologist reviews slides**

## Related projects
- [Virtual Slide Viewer frontend](https://github.com/VanAndelInstitute/virtual-slide-viewer)
