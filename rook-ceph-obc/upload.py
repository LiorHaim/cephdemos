import boto3 
import botocore 
import os 

# assign env vars to python ones
bucket_host = os.environ.get('BUCKET_HOST')
bucket_port = os.environ.get('BUCKET_PORT')
bucket_name = os.environ.get('BUCKET_NAME')
access_key = os.environ.get('AWS_ACCESS_KEY_ID')
secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')

# builds the endpoint url 
endpoint_url = 'https://' + str(bucket_host) + ":" + str(bucket_port)

# creates a S3 connection 
connection = boto3.client('s3',
                           endpoint_url=endpoint_url,
                           aws_access_key_id=access_key,
                           aws_secret_access_key=secret_key, verify=False)

# Upload an object to that bucket, will fail if OBC wasn't successful
with open('/etc/hosts', 'rb') as data:
    connection.upload_fileobj(data, bucket_name, 'hosts')

