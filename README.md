# Backend for Virtual Slide Viewer
The VSV backend is implemented as an AWS Serverless application. It mounts an EFS share with SVS files into a Lambda function and handles API Gateway requests
for DeepZoom tiles by using [OpenSlide Python](https://openslide.org/api/python/) to fetch TIFF tiles and [Pillow-SIMD](https://github.com/uploadcare/pillow-simd) to shrink tiles as needed.

## Build and deploy

### Prerequisites
The infrastructure code is currently a [SAM app](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html). You'll need to install the [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html) and create a deployment bucket for the `sam package` command. You'll also need to [install Docker](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install-mac.html#serverless-sam-cli-install-mac-docker) for the [`--use-container` flag](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-using-build.html#build-zip-archive) to build the native Linux binaries for the OpenSlide and libdmtx Lambda layers.

You'll also need:
- [ ] A validated email address used for the user pool in Amazon SES ([in region us-east-1 or us-west-2](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-email.html#user-pool-email-developer)).
- [ ] An [AWS DataSync agent](README_DATASYNC.md) and a source location for the ScanScope workstation. These resources will be shared among multiple deployments.
- [ ] An SSL certificate for `DomainName` in region us-east-1. You can request a public certificate from AWS Certificate Manager.
### Build and package function resources:
```
$ sam build -u -t func.template.yaml [--cached]
$ sam package --s3-bucket $DEPLOYBUCKET --s3-prefix $S3PREFIX --output-template-file template.yaml
```

### Deploy:
You can use the `--guided` argument to prompt for deployment parameters, or you can create a AWS SAM configuration file (samconfig.toml) with all the necessary parameters to facilitate deployment.
```
$ sam deploy -t main.template.yaml --config-env $MAINCONFIG --stack-name $STACKNAME
```

### Manual steps
- [ ] Edit the aws-exports.js files in the frontend to use the Cognito User Pool and AppSync GraphQL API output parameters.
- [ ] Upload [the frontend](https://github.com/VanAndelInstitute/virtual-slide-viewer) build to the S3 bucket.
- [ ] Fix the permissions on EFS from an EC2 instance with the fs mounted and in the fs VPC:
```
$ sudo chown -R ec2-user .
$ sudo chgrp -R ec2-user .
```

## General workflow for Virtual Slide Viewer deployments
1. Aperio scanner dumps SVS images onto local ScanScope workstation storage
1. A scheduled task script on the ScanScope workstation watches for new files and calls the AWS Lambda-backed `/ImportSlide` API method while there are still new files
    - If there are multiple deployments (e.g., for test and prod envs), you can configure the script to sync to one deployment and then manually [copy the files to the other](https://docs.aws.amazon.com/efs/latest/ug/manage-fs-access-vpc-peering.html) from an EC2 instance.
1. The `ImportSlide` AWS Lambda function:
    - triggers an AWS DataSync task to transfer SVS files to Amazon EFS
    - extracts label and thumbnail images from SVS file
    - extracts image metadata from TIFF tags and reads barcode from label image
    - uploads metadata to Amazon DynamoDB table
    - extracts DeepZoom tiles from SVS file and stores them as JPEGs in EFS
1.	**Scanner technician reviews images for scanning errors**
    - searches for new (unsent) slides
    - deletes and rescans failed slide scans
    - fixes slide/case IDs, if incorrect or missing
    - marks slides to send (metadata) to CDR
1.	**Pathologist reviews slides**

## Related projects
- [Virtual Slide Viewer frontend](https://github.com/VanAndelInstitute/virtual-slide-viewer)
