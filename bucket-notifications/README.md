## RHCS4.0 Bucket Notifications 

This repository contains a demo for Red Hat Ceph Storage 4.0 bucket notifications feature. This feature provides the ability of getting a notification each time an object is created/removed. The MQ endpoints can be RabbitMQ (AMQP), Kafka, and HTTP. 

### Prerequisites

To run this demo, you should have running RHCS4.0 and kafka clusters. 

## Getting Started

In the following demo we will be bootstraping a dockerized kafka cluster, which will get all the notifications for objects creation and removal. to start youre kafka cluster please clone the following repository: 

```
git clone https://github.com/wurstmeister/kafka-docker.git
cd kafka-docker 
```

## Installation 

We have the ability of pre-creating a kafka topic which will listen to our bucket notifications, to do so, please edit docker-compose-single-broker.yaml and change KAFKA_CREATE_TOPICS value, 'test' is where you change the topic name. Change to topic name to storage just for the demo, then run: 

```
docker-compose -f docker-compose-single-broker.yml up -d

docker-compose ps 
          Name                        Command               State                         Ports                       
----------------------------------------------------------------------------------------------------------------------
kafka-docker_kafka_1       start-kafka.sh                   Up      0.0.0.0:9092->9092/tcp                            
kafka-docker_zookeeper_1   /bin/sh -c /usr/sbin/sshd  ...   Up      0.0.0.0:2181->2181/tcp, 22/tcp, 2888/tcp, 3888/tcp

netstat -ntlp | egrep -e "9092|2181"
tcp6       0      0 :::9092                 :::*                    LISTEN      13911/docker-proxy  
tcp6       0      0 :::2181                 :::*                    LISTEN      13931/docker-proxy  
```

Lets verify RGW is listening and we can access it on the right address and port: 

```
curl <RGW_ADDRESS>:<RGW_PORT>
<?xml version="1.0" encoding="UTF-8"?><ListAllMyBucketsResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Owner><ID>anonymous</ID><DisplayName></DisplayName></Owner><Buckets></Buckets></ListAllMyBucketsResult>
```

We need to create a user which will have permissions for uploading. removing objects and configuering the bucket notifications: 

```
radosgw-admin user create --uid=test-notifications splay-name=test-notifications --access-key=test-notifications --secret=test-notifications
```

## Running tests

Now that the kafka cluster is set up, lets validate topic was created and start listening to any new notifications: 

```
docker exec -it kafka-docker_kafka_1 bash -c "/opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092"
storage

docker exec -it kafka-docker_kafka_1 bash -c "/opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic storage --from-beginning"
```

If you don't see any messages it's OK, we havent sent any notification yet. To configure bucket notifications, we could use a tool called notify, which handles all to REST configuration towards our ceph cluster. To do so: 

``` 
docker pull shonpaz123/notify

docker run shonpaz123/notify -h
usage: notify.py [-h] -e ENDPOINT_URL -a ACCESS_KEY -s SECRET_KEY -b
                 BUCKET_NAME [-k KAFKA_ENDPOINT] [-r RABBITMQ_ENDPOINT] -t
                 TOPIC

optional arguments:
  -h, --help            show this help message and exit
  -e ENDPOINT_URL, --endpoint-url ENDPOINT_URL
                        endpoint url for s3 object storage
  -a ACCESS_KEY, --access-key ACCESS_KEY
                        access key for s3 object storage
  -s SECRET_KEY, --secret-key SECRET_KEY
                        secret key for s3 object storage
  -b BUCKET_NAME, --bucket-name BUCKET_NAME
                        s3 bucket name
  -k KAFKA_ENDPOINT, --kafka-endpoint KAFKA_ENDPOINT
                        kafka endpoint in which rgw will send notifications to
  -r RABBITMQ_ENDPOINT, --rabbitmq-endpoint RABBITMQ_ENDPOINT
                        rabbitmq topic in which rgw will send notifications to
  -t TOPIC, --topic TOPIC
                        kafka topic in which rgw will send notifications to

docker run shonpaz123/notify -a test-notifications -s test-notifications -b test-notifications -k <KAFKA_ADDRESS>:9092 -t storage -e <RGW_ADDRESS>:<RGW_PORT>
```

After configuering the following, lets configure our s3 credentails and create a bucket so we could start uploading objects: 

``` 
export AWS_SECRET_ACCESS_KEY=test-notifications
export AWS_ACCESS_KEY_ID=test-notifications
aws s3 mb s3://test-notifications --endpoint-url http://<RGW_ADDRESS>:<RGW_PORT>
```

Now lets create a random object and upload it to our S3 service, later on we will delete it so we could verify both notification types: 

``` 
truncate -s 10M test-notifications
aws s3 cp test-notifications s3://test-notifications --endpoint-url http://<RGW_ADDRESS>:<RGW_PORT>
aws s3 rm s3://test-notifications/test-notifications --endpoint-url http://<RGW_ADDRESS>:<RGW_PORT>
```

Now if we go to our kafka cluster, where we started consuming out topic's notifications we should see two notifications, one for creation and one for removal: 

``` 
{"eventVersion":"2.1","eventSource":"aws:s3","awsRegion":"","eventTime":"2020-02-24 11:23:51.744652Z","eventName":"s3:ObjectCreated:CompleteMultipartUpload","userIdentity":{"principalId":"test-notifications"},"requestParameters":{"sourceIPAddress":""},"responseElements":{"x-amz-request-id":"6d95e0d4-5f6e-467f-82a2-ad8b8616157c.4177.10","x-amz-id-2":"1051-default-default"},"s3":{"s3SchemaVersion":"1.0","configurationId":"test-configuration","bucket":{"name":"test-notifications","ownerIdentity":{"principalId":"test-notifications"},"arn":"arn:aws:s3:::test-notifications","id":"6d95e0d4-5f6e-467f-82a2-ad8b8616157c.4181.1"},"object":{"key":"test-notifications","size":0,"etag":"669fdad9e309b552f1e9cf7b489c1f73-2","versionId":"","sequencer":"47B2535E2DE4622C","metadata":[{"key":"x-amz-content-sha256","val":"6fc9f44742bb1f04c293d42949652effd5f52a4230d45b1a0f2dcee53cee81e7"},{"key":"x-amz-date","val":"20200224T112351Z"}],"tags":[]}},"eventId":""}

{"eventVersion":"2.1","eventSource":"aws:s3","awsRegion":"","eventTime":"2020-02-24 11:24:57.746365Z","eventName":"s3:ObjectRemoved:Delete","userIdentity":{"principalId":"test-notifications"},"requestParameters":{"sourceIPAddress":""},"responseElements":{"x-amz-request-id":"6d95e0d4-5f6e-467f-82a2-ad8b8616157c.4177.11","x-amz-id-2":"1051-default-default"},"s3":{"s3SchemaVersion":"1.0","configurationId":"test-configuration","bucket":{"name":"test-notifications","ownerIdentity":{"principalId":"test-notifications"},"arn":"arn:aws:s3:::test-notifications","id":"6d95e0d4-5f6e-467f-82a2-ad8b8616157c.4181.1"},"object":{"key":"test-notifications","size":0,"etag":"669fdad9e309b552f1e9cf7b489c1f73-2","versionId":"","sequencer":"89B2535EE6037D2C","metadata":[{"key":"x-amz-content-sha256","val":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},{"key":"x-amz-date","val":"20200224T112457Z"}],"tags":[]}},"eventId":""}
```

We can see there are two notifcations that reached to our kafka topic and under 'eventName' we could see s3:ObjectCreated and s3:ObjectRemoved fields. 

## Versioning

Build versions are handled through docker cloud. 

Supported versions for infrastructure components are: 
- RHCS Cluster  == 4.0
- Kafka Cluster == 2.4.0
- Notify Tool   == latest
- awscli        == latest

## Authors

* **Shon Paz** - *Initial work* - [shonpaz123](https://github.com/shonpaz123)

