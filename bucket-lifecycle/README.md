## Creating the intelligent object storage system with Ceph's Object Lifecycle Management 

In the previous chapters we have talked about RHCS4.0 tier transition feature. This feature is one of two abiliies we have in Object Lifecycle Management, where the second one is used for object exipration. 
As in Amazon, we can use a declarative policy to expire the objects we have in our cluster. We have few possibilities when it comes to expiration:

1. Expiring objects with no dedicated rule, all object are deleted after a certain amount of time.
2. Expiring objects with one or more rules by tagging the objects with custom metadata, which will be used in the expiration policy.
3. Expiring objects with one or more rules by indicating a prefix, and all objects will expire recursivly under that prefix. 

In ceph, lc (AKA Lifecycle) scans the objects for their metadata, checking if there are any objects to delete. Every object holds it's expiration date, and lc just compares the expiration date with the current date. lc process runs periodically with a pre-defined and configurable schedule, every object lc marks as deleted is then transferred to Ceph's garbage collector (AKA gc) which deletes the expired objects.

In this demo we will test only one the previous mentioned expiration methods (expiration with tags) to get a clue of how things work. 

## Prerequisites
To run this demo, you should have a running Ceph cluster (minimum version of luminous) and tools such as boto3 python library and awscli installed. 

Let's use the following python script, to emphasize the upload of 20 flower images (could be pre-recognized by machine learning image recogniztion algorythm for example), where 10 images contain red flowers, and the other ten contain blue flowers. The bucket name is `flowers`, and we will configure a bucket lifecycle policy that deletes all red flowers after 1 week, and all the blue flowers after 1 month. In our demo we will be using `rgw lc debug interval = 10` in the ceph.conf so every day will be counted as 10 seconds (don't forget to restart the rgw service to inject the configuration).


## Installation 

```bash 
# import modules
import boto3
import botocore
import datetime


# S3client class defines all needed attributes to ease s3 client connection via boto3 module.
# The class uses boto3 module as base reference.

class S3client:

    # this method initiates all needed s3 attributes for connection
    def __init__(self, endpoint_url, aws_access_key_id, aws_secret_access_key, path_style):
        self.endpoint_url = endpoint_url
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.path_style = path_style

    # this method configures path style for s3 connection
    def configure_path_style(self):
        botocore.config.Config(s3=self.path_style)

    # this method creates connectivity to a s3 resource such as Ceph RGW
    def create_connection(self):
        connection = boto3.client(
                            's3',
                            endpoint_url=self.endpoint_url,
                            aws_access_key_id=self.aws_access_key_id,
                            aws_secret_access_key=self.aws_secret_access_key
        )
        return connection


def main():

    # creates s3 client instance of S3client class
    s3client_instance = S3client(
                            '<YOUR_ENDPOINT_URL_GOES_HERE',
                            '<YOUR_ACCESS_KEY_GOES_HERE>',
                            '<YOUR_SECRET_KEY_GOES_HERE>',
                            {"addressing_style": "path"}
    )

    # configures path style for s3 connectivity
    s3client_instance.configure_path_style()

    # creates connection to s3 resource, in this case Ceph RGW
    s3_connection = s3client_instance.create_connection()

    # creates bucket with the specified name
    bucket_name = 'flowers'
    s3_connection.create_bucket(Bucket=bucket_name)

    # configures lifecycle configuration for the bucket
    # creates a rule that deletes flowers by their color 
    s3_connection.put_bucket_lifecycle_configuration(
        Bucket=bucket_name,
        LifecycleConfiguration=
        {
    "Rules": [
        {
            "Expiration": {
                "Days": 7
            },
            "ID": "7-days-expiration",
            "Filter": {
                "Tag": {
                    "Key": "color",
                    "Value": "red"
                }
            },
            "Status": "Enabled"
        },
        {
            "Expiration": {
                "Days": 30
            },
            "ID": "1-month-expiration",
            "Filter": {
                "Tag": {
                    "Key": "color",
                    "Value": "blue"
                }
            },
            "Status": "Enabled"
        }
    ]
}
)

    # uploads 10 objects and tag them in the needed tags for expiration
    for i in range(10):
        object_key = 'redflower' + str(i) + '.jpg'
        s3_connection.upload_file('/etc/hosts', bucket_name, object_key)
        s3_connection.put_object_tagging(
                                            Bucket=bucket_name,
                                            Key=object_key,
                                            Tagging={'TagSet': [{'Key': 'color', 'Value': 'red'}]}
                                        )
        print("object: {0} uploaded".format(object_key))
        
    # uploads 10 objects and tag them in the needed tags for expiration
    for i in range(10):
        object_key = 'blueflower' + str(i) + '.jpg'
        s3_connection.upload_file('/etc/hosts', bucket_name, object_key)
        s3_connection.put_object_tagging(
                                            Bucket=bucket_name,
                                            Key=object_key,
                                            Tagging={'TagSet': [{'Key': 'color', 'Value': 'blue'}]}
                                        )

        print("object: {0} uploaded".format(object_key))

if __name__ == "__main__":
    main()
``` 

After running the script, we'll run a list operation towards our bucket to see all objects are fully uploaded: 

```bash 
aws s3 ls s3://flowers --endpoint-url http://10.35.206.202:8000
2020-03-16 13:13:34        136 blueflower0.jpg
2020-03-16 13:13:34        136 blueflower1.jpg
2020-03-16 13:13:34        136 blueflower2.jpg
2020-03-16 13:13:34        136 blueflower3.jpg
2020-03-16 13:13:34        136 blueflower4.jpg
2020-03-16 13:13:34        136 blueflower5.jpg
2020-03-16 13:13:34        136 blueflower6.jpg
2020-03-16 13:13:34        136 blueflower7.jpg
2020-03-16 13:13:34        136 blueflower8.jpg
2020-03-16 13:13:34        136 blueflower9.jpg
2020-03-16 13:13:33        136 redflower0.jpg
2020-03-16 13:13:34        136 redflower1.jpg
2020-03-16 13:13:34        136 redflower2.jpg
2020-03-16 13:13:34        136 redflower3.jpg
2020-03-16 13:13:34        136 redflower4.jpg
2020-03-16 13:13:34        136 redflower5.jpg
2020-03-16 13:13:34        136 redflower6.jpg
2020-03-16 13:13:34        136 redflower7.jpg
2020-03-16 13:13:34        136 redflower8.jpg
2020-03-16 13:13:34        136 redflower9.jpg
```

Let's use aswcli to head each group's object, so we could get it's metadata, which contains the expiration header for that objects: 

```bash
aws s3api head-object --bucket flowers --key blueflower0.jpg --endpoint-url http://10.35.206.202:8000
{
    "AcceptRanges": "bytes",
    "Expiration": "expiry-date=\"Wed, 15 Apr 2020 11:44:59 GMT\", rule-id=\"1-months-expiration\"",
    "LastModified": "Mon, 16 Mar 2020 11:44:59 GMT",
    "ContentLength": 136,
    "ETag": "\"cc324dd0035e79fe5f0d0aa095769499\"",
    "ContentType": "binary/octet-stream",
    "Metadata": {}
}

aws s3api head-object --bucket flowers --key redflower0.jpg --endpoint-url http://10.35.206.202:8000
{
    "AcceptRanges": "bytes",
    "Expiration": "expiry-date=\"Mon, 23 Mar 2020 11:44:59 GMT\", rule-id=\"7-days-expiration\"",
    "LastModified": "Mon, 16 Mar 2020 11:44:59 GMT",
    "ContentLength": 136,
    "ETag": "\"cc324dd0035e79fe5f0d0aa095769499\"",
    "ContentType": "binary/octet-stream",
    "Metadata": {}
}

```

So we have queried the object's metadata and as you see, a red flower will be deleted in a week (23/03/20), and a blue flower will be deleted in one month (15/04/21). Let's verify radosgw got our bucket configuration: 

```bash
radosgw-admin lc list
[
    {
        "bucket": ":flowers:6949b583-fb9f-4d12-974e-41a59276f7e5.14103.1",
        "status": "UNINITIAL"
    }
]
```

Now we'll wait for the process to run, hypotheticaly the red flowers will be deleted after 70 seconds, while blue flowers will br deleted after 300 seconds which is about 5 minutes. Let's verify lc process has finished for the first 10 red flowers: 
 
```bash
radosgw-admin lc list
[
    {
        "bucket": ":flowers:6949b583-fb9f-4d12-974e-41a59276f7e5.14103.1",
        "status": "COMPLETE"
    }
]
```

As you see, lc process has finished. now let's see if objects were deleted from our flowers bucket: 

```bash
rados ls -p default.rgw.buckets.data
ce45d8ff-b551-46aa-868b-cf6e50ef021a.14103.1_blueflower2.jpg
ce45d8ff-b551-46aa-868b-cf6e50ef021a.14103.1_blueflower9.jpg
ce45d8ff-b551-46aa-868b-cf6e50ef021a.14103.1_blueflower5.jpg
ce45d8ff-b551-46aa-868b-cf6e50ef021a.14103.1_blueflower0.jpg
ce45d8ff-b551-46aa-868b-cf6e50ef021a.14103.1_blueflower6.jpg
ce45d8ff-b551-46aa-868b-cf6e50ef021a.14103.1_blueflower7.jpg
ce45d8ff-b551-46aa-868b-cf6e50ef021a.14103.1_blueflower1.jpg
ce45d8ff-b551-46aa-868b-cf6e50ef021a.14103.1_blueflower3.jpg
ce45d8ff-b551-46aa-868b-cf6e50ef021a.14103.1_blueflower8.jpg
ce45d8ff-b551-46aa-868b-cf6e50ef021a.14103.1_blueflower4.jpg
```

Objects indeed wer deleted. After 5 minutes, we can see that if we do the same command we can see we have no objects in the pool which means all objects were deleted: 

```bash 
rados ls -p default.rgw.buckets.data | wc -l
0
``` 

## Conclusion 

As we saw, we have multiple policies for expiring objects when it comes to Object Lifecycle Management. With this feature, we can provide an intelligent object storage system, which can ventually offload the objets expiration management from the developers, and can be managed as declarative self-service policy in our private cloud environment. 




