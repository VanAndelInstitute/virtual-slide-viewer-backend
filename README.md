**This repository is now obsolete. See https://github.com/VanAndelInstitute/s3vs**

# Backend for Virtual Slide Viewer
The VSV backend is implemented as an AWS Serverless application. It mounts an EFS share with SVS files into a Lambda function and handles API Gateway requests for [IIIF](https://iiif.io/api/image/3.0/) tiles by using [OpenSlide Python](https://openslide.org/api/python/) to fetch TIFF tiles and [Pillow-SIMD](https://github.com/uploadcare/pillow-simd) to shrink tiles as needed.

## Build and deploy

### Prerequisites
The infrastructure code is currently a [SAM app](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html). You'll need to install the [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html) and create a deployment bucket for the `sam package` command. You'll also need to [install Docker](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install-mac.html#serverless-sam-cli-install-mac-docker) for the [`--use-container` flag](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-using-build.html#build-zip-archive) to build the native Linux binaries for the OpenSlide and libdmtx Lambda layers.

You'll also need:
- [ ] One SSL certificate for `DomainName` (in region us-east-1) and one for `ApiCustomDomain`. You can request public certificates from AWS Certificate Manager.
- [ ] Two S3 buckets for images, one for upload purposes and another for publishing/sharing for downstream research.
### Build and package function resources:
```
$ sam build -u -t func.template.yaml [--cached]
$ sam package --s3-bucket $DEPLOYBUCKET --s3-prefix $S3PREFIX --output-template-file template.yaml
```

### Deploy:
You can use the `--guided` argument to prompt for deployment parameters, or you can create a AWS SAM configuration file (samconfig.toml) with all the necessary parameters to facilitate deployment.
```
$ sam deploy -t main.template.yaml --config-env $ENVTYPE --stack-name $STACKNAME
```

### Manual steps
- [ ] Edit the config.js file in the frontend to use the API custom-domain URL.
- [ ] Upload the frontend static resources to the S3 bucket.
- [ ] Fix the permissions on EFS from an EC2 instance with the fs mounted and in the fs VPC:
```
$ sudo chown -R ec2-user .
$ sudo chgrp -R ec2-user .
```

## General workflow for Virtual Slide Viewer deployments
1. Aperio eSlide Manager picks up slides from the Aperio scanner.
1. Scanner technician reviews slides for scanning errors:
    - deletes and rescans failed slide scans
    - fixes slide/case IDs, if incorrect or missing
    - moves slides to to CDR folder
1. A scheduled task script on the eSlide Manager server periodically runs `aws s3 sync` on the CPTAC folder, which uploads new slides to the CPTAC S3 bucket.
1. The CPTAC S3 bucket triggers the `ImportSlide` AWS Lambda function:
    - downloads the new SVS file from the CPTAC S3 bucket to EFS
    - reads the barcode from the label image in the SVS file
    - extracts slide metadata from the SVS file
    - uploads metadata to CDR
1.	**Pathologist reviews slides**

## Related projects
- [s3vs frontend](https://github.com/rmontroy/s3vs)
