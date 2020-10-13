import os
import boto3
import traceback as tb

IMAGES_PATH = os.environ['IMAGES_PATH']
IMAGES_BUCKET = os.environ['IMAGES_BUCKET']

def lambda_handler(event, context):
    svs_file = event['pathParameters']['svsFile']
    print(IMAGES_PATH)
    print(IMAGES_BUCKET)
    print(svs_file)
    try:
        s3 = boto3.resource('s3')
        s3.Object(IMAGES_BUCKET, svs_file).download_file(os.path.join(IMAGES_PATH, svs_file))
    except Exception as e:
        return {
            'statusCode': 500,
            'body': ''.join(tb.format_exception(type(e), e, e.__traceback__))
        }