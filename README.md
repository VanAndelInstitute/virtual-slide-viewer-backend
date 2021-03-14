# Backend for Virtual Slide Viewer
The VSV backend is implemented as an AWS Serverless application. It mounts an EFS share with SVS files into a Lambda function and handles API Gateway requests
for DeepZoom tiles by using [OpenSlide Python](https://openslide.org/api/python/) to fetch TIFF tiles and [Pillow-SIMD](https://github.com/uploadcare/pillow-simd) to shrink tiles as needed.

## Build and deploy
The infrastructure code is currently a [SAM app](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-getting-started.html). You'll need to [install Docker to build](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-using-build.html) the OpenSlide and libdmtx Lambda layers.

### Prerequisites
- [ ] Create a SAM deployment bucket.
- [ ] Validate the email address used for the user pool in Amazon SES (region us-east-1).
- [ ] [Create/activate](README_DATASYNC.md) the AWS DataSync agent and create a source location for the ScanScope workstation.

### Build and package function resources:
```
$ sam build -u -t func.template.yaml
$ sam package --s3-bucket $DEPLOYBUCKET --s3-prefix $S3PREFIX --output-template-file template.yaml
```
### Deploy all infrastructure except CloudFront (in any region):
Create the AWS SAM configuration file (samconfig.toml). You can create separate sets of deploy parameters for 'main' and 'web' templates.
```
$ sam deploy -t main.template.yaml --config-env $MAINCONFIG --stack-name $STACKNAME
```
Insert the value of the ParameterOverrides output value into the CloudFront deploy parameters in samlconfig.toml. Also, edit the config.js files in the frontend to use the GraphQL API URL and key from the corresponding output parameters.
### Deploy CloudFront infrastructure (in us-east-1 region only):
_Note:_ You'll need to help CloudFormation create the ViewerCertificate resource by logging into AWS Certificate Manager and clicking the button to create a CNAME entry in Route 53 so it can validate the certificate.
```
$ sam deploy -t web.template.yaml --config-env $WEBCONFIG --stack-name $STACKNAME
```
### Manual steps
- [ ] Upload [the frontend](https://github.com/VanAndelInstitute/virtual-slide-viewer) build to the S3 bucket. Be sure to edit the appropriate keys in the config files first.
- [ ] Update the expiration date on the AppSync API key.
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
