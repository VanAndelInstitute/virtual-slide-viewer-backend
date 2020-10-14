import os
import boto3
import traceback as tb

IMAGES_PATH = os.environ['IMAGES_PATH']
s3 = boto3.resource('s3')

def download_object(bucket, object_key):
    target = os.path.join(IMAGES_PATH, object_key)
    if not os.path.exists(os.path.dirname(target)):
        os.makedirs(os.path.dirname(target))
    bucket.download_file(object_key, target)
    
"""
def transfer_s3_object(event, context):
    # path = '/transfer_s3_object/{bucket}/{object_key}
    bucket_name = event['pathParameters']['bucket']
    object_key = event['pathParameters']['object_key']
    print(IMAGES_PATH)
    print(bucket_name)
    print(object_key)
    bucket = s3.Bucket(bucket_name)
    try:
        download_object(bucket, object_key)
    except Exception as e:
        return {
            'statusCode': 500,
            'body': ''.join(tb.format_exception(type(e), e, e.__traceback__))
        }
"""

def transfer_s3_objects(event, context):
    # path = '/transfer_s3_objects/{bucket}/{prefix}
    bucket_name = event['pathParameters']['bucket']
    prefix = event['pathParameters']['prefix']
    print(IMAGES_PATH)
    print(prefix)
    bucket = s3.Bucket(bucket_name)
    try:
        for obj in bucket.objects.filter(Prefix = prefix):
            download_object(bucket, obj.key)
    except Exception as e:
        return {
            'statusCode': 500,
            'body': ''.join(tb.format_exception(type(e), e, e.__traceback__))
        }