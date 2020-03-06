## RHCS4.0 Tier Transition for scheduled data movement

## Introduction 
As we have talked in the previous post, a new major version of Ceph was released containing a handful of new features placing Ceph as the suitable SDS solution for Big Data and Machine Learning/AI workloads. The feature we are going to talk about is called "Tier Transition" which provides us the ability of creating Storage Classes (just like in AWS), for 'hot' (fast media, such as SSD/NVMe used for io sensitive workloads) and 'cold' (slow, magnetic media such as SAS/SATA used for archiving) areas relying on bucket lifecycle process for data movement. To be more specific, we could create a scheduled data movement between storage classes where data is written to the 'hot' storage class, moved to the 'cold' storage class (after a configured amount of time) and then expires and deleted for good. 
This feature is the de-facto standard in AWS nowadays, and now it's available in Ceph as well. 
For starter, let's move on some acronyms so we could understand the demo better: 
Zone Group - a collection of zones located mainly on the same geographic location, AKA Region. 
Zone - an instance contains cloud services and takes a part in a zone group, AKA Zone. 
Placement - Logical separation of data placement within the same zone. 

## Prerequisites  
To do this demo, you should have a running Red Hat Ceph Storage 4.0 cluster. 

## Configuration 
By default, we get default zonegroup, zone and placement, there is the ability of creating new ones, but this is out of this article's scope. 

```bash 
radosgw-admin zonegroup placement add \
      --rgw-zonegroup default \
      --placement-id testie

radosgw-admin zone placement add \
      --rgw-zone default \
      --placement-id testie \
      --data-pool default.rgw.testie.data \
      --index-pool default.rgw.testie.index \
      --data-extra-pool default.rgw.testie.non-ec
```

Let's look at our zonegroup configuration, so we could see which placements do we have, we should see one placement with 'default-placement' placement id. Please ssh to the RGW node, and run: 

```bash
radosgw-admin zonegroup get  

    "placement_targets": [
        {
            "name": "default-placement",
            "tags": [],
            "storage_classes": [
                "STANDARD"
            ]
        }
    ]
```

We can see we have a placement with default placement id, containing the STANDARD storage class. 

Now, we'll verify which storage classes we have in the current zone configuration, we should see a STANDARD storage class which is created by default. This storage class is the default storage class, which means all buckets and objects created are written to it, you could see this storage class contains it's own pools. 

```bash
radosgw-admin zone get

    "placement_pools": [
        {
            "key": "default-placement",
            "val": {
                "index_pool": "default.rgw.buckets.index",
                "storage_classes": {
                    "STANDARD": {
                        "data_pool": "default.rgw.buckets.data"
                    }
                },
                "data_extra_pool": "default.rgw.buckets.non-ec",
                "index_type": 0
            }
        }
    ]
```

Here we can see we have a data pool specifically for STANDARD storage class, let's create a new storage class containing it's own data pool.
Data on the new storage class will be compressed with lz4 compression algorythm. We'll create a new storage class called STANDARD_IA:

```bash 
radosgw-admin zonegroup placement add \
      --rgw-zonegroup default \
      --placement-id default-placement \
      --storage-class STANDARD_IA

radosgw-admin zone placement add \
      --rgw-zone default \
      --placement-id default-placement \
      --storage-class STANDARD_IA \
      --data-pool default.rgw.STANDARD_IA.data \
      --compression lz4

```

In the output, we can see a new storage class was added, and there is a new data pool under STANDARD_IA storage class: 
```bash
"storage_classes": {
                    "STANDARD": {
                        "data_pool": "default.rgw.buckets.data"
                    },
                    "STANDARD_IA": {
                        "data_pool": "default.rgw.STANDARD_IA.data",
                        "compression_type": "lz4"
                    }
                }

```
Now, let's create a user 'testie' so we could start uploading objects: 
```bash
radosgw-admin user create --uid=testie --display-name=testie --access-key=testie --secret=testie
```

Configure aws credentials by exporting the following values (we have hard-coded the crednetials in the user creation process): 
```bash 
export AWS_ACCESS_KEY_ID=testie
export AWS_SECRET_ACCESS_KEY=testie
```

Let's create a bucket under default-placement placement and verify it was created under the right placement ID: 

```bash 
aws s3api create-bucket --bucket testie --create-bucket-configuration LocationConstraint=default:default-placement --endpoint-url http://192.168.42.10:8080

radosgw-admin bucket stats --bucket=testie
{
    "bucket": "testie",
    "tenant": "",
    "zonegroup": "0a827883-1d31-4e68-9553-8076ec28cd63",
    "placement_rule": "default-placement",
}
```

Now, add the following value to your ceph.conf, to enable debug interval for the lifecycle process (each day in the bucket lifecycle configuration equals 60 sec, so 3 days expiration is actually 3 minutes). After adding the value please restart rgw process to reload configuration: 

```bash
rgw lc debug interval = 60
systemctl restart ceph-radosgw@rgw.$HOSTNAME.service
```

Let's upload some objects and see what happens. According the our bucket lifecycle configurarion, each object we upload should move to our STANDARD_IA storage class after 1 day (AKA 60 seconds), and expire after 3 days (AKA 180 seconds, 3 minutes). We'll use aws boto3 library to configure all of the following, please change to your RGW address: 

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
                            'http://<RGW_URL',
                            'testie',
                            'testie',
                            {"addressing_style": "path"}
    )

    # configures path style for s3 connectivity
    s3client_instance.configure_path_style()

    # creates connection to s3 resource, in this case Ceph RGW
    s3_connection = s3client_instance.create_connection()

    # creates bucket with the specified name
    bucket_name = 'testie'
    
    # configures lifecycle configuration for the bucket
    # creates a rule that moves all WMV objects after 1 day, and deletes them after 3 days 
    s3_connection.put_bucket_lifecycle_configuration(
        Bucket=bucket_name,
        LifecycleConfiguration=
        {
          "Rules": [
            {
              "Filter": { 
                  "Prefix": ""
              },
              "Expiration": {
                "Days": 3,
              },
              "ID": "string",
              "Status": "Enabled",
              "Transitions": [
                {
                  "Days": 1,
                  "StorageClass": "STANDARD_IA"
                }
              ]
            }
          ]
        }
    )         
    # uploads 100 objects and tag them in the needed tags for expiration
    for i in range(100):
        object_key = 'WMV' + str(i)
        s3_connection.upload_file('/etc/hosts', bucket_name, object_key)
        s3_connection.put_object_tagging(
                                            Bucket=bucket_name,
                                            Key=object_key,
                                            Tagging={'TagSet': [{'Key': 'suffix', 'Value': 'WMV'}]}
                                        )
        print("object: {0} uploaded".format(object_key))

if __name__ == "__main__":
    main()

```
After all objects were uploaded, let's verify all objects were written to the pool contained by the 'STANDARD' storage class:

```bash
rados ls -p default.rgw.buckets.data
39664c5a-2b23-4a46-85c1-5bbfeeadfece.4179.1_WMV37
39664c5a-2b23-4a46-85c1-5bbfeeadfece.4179.1_WMV34
39664c5a-2b23-4a46-85c1-5bbfeeadfece.4179.1_WMV29
39664c5a-2b23-4a46-85c1-5bbfeeadfece.4179.1_WMV80
39664c5a-2b23-4a46-85c1-5bbfeeadfece.4179.1_WMV96
39664c5a-2b23-4a46-85c1-5bbfeeadfece.4179.1_WMV0
```

We can verify when the object gets it's target storage class by performing http HEAD operation infront of our rgw: 

```bash
aws s3api head-object --bucket testie --key WMV50 --endpoint-url http://<RGW_URL>
{
    "AcceptRanges": "bytes",
    "Expiration": "expiry-date=\"Mon, 09 Mar 2020 15:34:17 GMT\", rule
-id=\"string\"",
    "LastModified": "Fri, 06 Mar 2020 15:34:17 GMT",
    "ContentLength": 227,
    "ETag": "\"d9f12a3992e69b1bf6087ab5c3dda072\"",
    "ContentType": "binary/octet-stream",
    "Metadata": {},
    "StorageClass": "STANDARD_IA"
}
```

Let's verify all objects moved to the target data pool contained by 'STANDARD_IA' storage class: 

```bash
rados ls -p default.rgw.STANDARD_IA.data
39664c5a-2b23-4a46-85c1-5bbfeeadfece.4179.1_WMV37
39664c5a-2b23-4a46-85c1-5bbfeeadfece.4179.1_WMV34
39664c5a-2b23-4a46-85c1-5bbfeeadfece.4179.1_WMV29
39664c5a-2b23-4a46-85c1-5bbfeeadfece.4179.1_WMV80
39664c5a-2b23-4a46-85c1-5bbfeeadfece.4179.1_WMV96
39664c5a-2b23-4a46-85c1-5bbfeeadfece.4179.1_WMV0
```

Now, lets verify objects wew deleted constantly by performing the same commands again: 

```bash 
rados ls -p default.rgw.buckets.data | wc -l 
0 

rados ls -p default.rgw.STANDARD_IA.data | wc -l
0
``` 

## Conclusion
We have been through RHCS4.0 Tier transtion feature, as we saw this feature provides the ability of controlling our data movement according to a pre-defined policy created by the end user. This flexability could ease the data management process in our organization, offloading archiving/deletions from the end user by exposing a declerative scriptable policy-based interface. 


