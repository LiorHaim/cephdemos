# Running Data Pipelines Locally Using Containerized Ceph S3, Kafka & NiFI

![](images/00-opening.jpg)

As data world becomes more and more similar to the development world with data sets being used as git repostories, the evolvment of treating data as it was a product, and having a complete MDLC (Machine Learning Development Lifecycle), Data Engineers might want to test their data pipelines locally, on a small scale to see the nothing breaks, versions are completely aligned and that those data pipelines can be pushed to production. 

With the help of the open source world and containerization, Data Engineers are able to test pipelines locally, on their own computers, using containers - and later integrate it with the work of other data engineers. 

In this demo, I'd like to share with you how you can spin up such a stack, that includes `Red Hat Ceph Storage` for S3 capabailities, `NiFI` for data flow & transformation, and `Kafka` as the event streaming engine, In order to create a data pipline that transforms a given CSV file to Avro format, and sends it to Kafka. 

A sample of the data set (30 rows total):

```csv
YearsExperience,Salary
1.1,39343.00
1.3,46205.00
1.5,37731.00
.
.
.
```

Let get started! 

## Prerequisites
* A computer running Podman/Docker
* In case of using `Podman`, Install the `podman-docker` package 

## Setting Up The Infrastructure 

To run this demo, We'll have to run three different containerized components, which are `Red Hat Ceph Storage`, `Kafka` and `NiFi`. 

Before diving into each on of the components, let's create a network so that all containers will be able to share subnets, DNS records, etc: 

```bash
$ docker network create data-pipeline  
```

For the sake of this demo, we won't run those infrastructure services in their full form, but will use single-node containers, as it more lightwight and less overkill to use and implement locally. 

### Running A Single-Node Ceph Cluster For S3

In order to use `S3` in our demo, we'll need to run a single-node `Red Hat Ceph Storage` implementation, that will expose the `Ceph RGW` S3 interface to other containers in the shared network.

Let's first create local directories that will be used for the `Ceph` container to preserve configurations: 

```bash
$ mkdir -p /data/etc/ceph/ 
$ mkdir -p /data/var/lib/ceph/
```

Now let's run the `Ceph` cluster itself.
This command creates a `Ceph` cluster, with hardened credentails (access-key and secret-key, both are `nifi`). 

```bash
$ docker run -d --privileged --name ceph --net data-pipeline -e NETWORK_AUTO_DETECT=4 -v /data/var/lib/ceph:/var/lib/ceph:rw -v /data/etc/ceph:/etc/ceph:rw -e CEPH_DEMO_UID=nifi -e CEPH_DEMO_ACCESS_KEY=nifi -e CEPH_DEMO_SECRET_KEY=nifi -p 8080:8080 registry.redhat.io/rhceph-alpha/rhceph-5-rhel8@sha256:9aaea414e2c263216f3cdcb7a096f57c3adf6125ec9f4b0f5f65fa8c43987155 demo
```

**Note:** Make sure you have valid credentials to pull the `Red Hat Ceph Storage` container image. If you don't have it, you can use upstream `Ceph` images coming from the `Ceph/Daemon` repository. 

Now, let's install the `awscli` tool to interact with our `S3` service: 

```bash
$ pip3 install awscli
```

Now let's configure our `S3` client to use our created credentials: 

```bash
aws configure
AWS Access Key ID [****************nifi]: 
AWS Secret Access Key [****************nifi]: 
Default region name [None]: 
Default output format [None]: 
```

Make sure you insert `nifi` to both `AWS Access Key ID` and `AWS Secret Access Key`. Press `Enter` continously for completion. 

Let's create our `S3` bucket that will be used by `NiFi`: 

```bash
$ aws s3 mb s3://nifi --endpoint-url http://127.0.0.1:8080

make_bucket: nifi
```

And now let's upload the CSV file that is part of this git repo folder: 

```bash
$ aws s3 cp paychecks.csv s3://nifi/ --endpoint-url http://127.0.0.1:8080

upload: ./paychecks.csv to s3://nifi/paychecks.csv      
``` 

### Running A Single-Node Kafka Cluster 

Now, we'll run both `Zookeeper` and `Broker` as single-node containers. 

Let's start with `Zookeeper`:

```bash
$ docker run -d --name zookeeper --net data-pipeline -e ZOOKEEPER_CLIENT_PORT=2181 -e ZOOKEEPER_TICK_TIME=2000 -p 22181:2181 confluentinc/cp-zookeeper:latest
```

Now that we have it running, let's spin up our `Kafka` broker: 

```bash
$ docker run -d --name kafka --net data-pipeline -e KAFKA_BROKER_ID=1 -e KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181 -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092,PLAINTEXT_HOST://localhost:29092 -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT -e KAFKA_INTER_BROKER_LISTENER_NAME=PLAINTEXT -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 -p 29092:29092 confluentinc/cp-kafka:latest
```

Great! We have our cluster up and running, now let's create a topic that `NiFi` will use to write the transformed `Avro` file: 

```bash
$ docker exec -it kafka kafka-topics --create --topic data-pipeline --replication-factor 1 --partitions 1 -bootstrap-server kafka:9092

Created topic data-pipeline.
```

### Running A Single-Node NiFi 

To run our `NiFi` instance, we'll use the following command: 

```bash
docker run -d --net data-pipeline --name nifi -d -p 8443:8443 apache/nifi:latest
```

Make sure that you see `NiFi`'s login screen once the container is up (it takes a few seconds). 

In order to login to `NiFi`, search for the following in the logs: 

```bash
docker logs nifi | grep -i generated

Generated Username [xxxxxx]
Generated Password [xxxxxx]
```

Login to `NiFi` and see the following screen: 

![](images/01-nifi-login-screen.png)


## Configuring The Data Pipeline 

In order to run our data pipeline, I've created a `NiFi Template` that was pre-created for you to use. You'll have minimal changes and then you'll be able to run your own pipeline locally. 

Let's start by uploading our template, press righ-click then `Upload Template`:

![](images/02-nifi-upload-template.png)

Choose the `CSV_--__Avro_Transformer.xml` template that is being attached to the git repository and upload it. 

Now, let's import our template and start dealing with the configuration: 

![](images/03-nifi-choose-uploaded-template.png)

you'll see the following screen when importing it: 

![](images/04-nifi-imported-template.png)

Next step, we'll have to configure the created controllers for our data flow. To do so, make sure to right-click then hit `Configure`:

![](images/05-nifi-configure-controller.png)

Once it was opened, make sure to enable all contrllers for our flow (the lightning button on the right of each controller): 

![](images/06-nifi-enable-controller.png)

Once we have all enabled, we'll have to change our `S3 Endpoint URL`, `Access Key` and `Secret Key` as `NiFi` doesn't saved those as part of the template configuration. 

To do so, press twice on both (one each time) `ListS3` component, so as the `FetchS3Object` and navigate to the `Properties` tab: 

![](images/07-nifi-change-s3-url.png)

Change both the access-key and secret-key to `nifi`as was created in previous stages, and change the `Endpoint Override URL` to your `Ceph'`s container IP address. 

In order to find out what it is, you can use the following command: 

```bash
$ docker inspect ceph | grep IPAddress
            "IPAddress": "",
                    "IPAddress": "10.89.3.5",
```

Once you have changed those configs for both `ListS3` and `FetchS3Object` processors, we can start our flow! 

## Running Our Data Flow 

In order to run our Flow, make sure to hit right-click and press the `Start` button: 

![](images/08-nifi-start-flow.png)

The flow will start reading data from our `Ceph` cluster, trasform it and write it to our `Kafka` cluster. Verify that the flow has finished successfully: 

![](images/09-nifi-successfull-flow.png)

We can see that there is a `424 Bytes` file that has moved through all queues and reaches our `Kafka` cluster. 

## Validating Our Transformation 

Now let's verify that data is indeed in our `Kafka` cluster, and that it was transformed to `Avro` format. To do so, we'll use `kcat` tool to read our `Kafka` cluster's content: 

```bash
kcat -b localhost:29092 -t data-pipeline
```

And the result is: 

![](images/10-kafka-avro-events.png)

Great! we have the transformed data in our `Kafka` topic. 

## Testing Our Flow's Consistency 

Let's upload our second CSV file, which is called `paychecks2.csv` to our bucket. 

As our flow should run every 60 seconds searching for new data, we should be able to see it after 60 seconds, in our `Kafka` topic. 

Let's upload the second file to our `S3` bucket: 

```bash
$ aws s3 cp paychecks2.csv s3://nifi/ --endpoint-url http://127.0.0.1:8080

upload: ./paychecks2.csv to s3://nifi/paychecks2.csv  
```

And wait 60 seconds until we see data in our `Kafka` topic: 

![](images/10-kafka-avro-events-second-run.png)

As you can see, now the message we get from `kcat` is `Reached end of topic at offset 60`, which means another flow was run automatically. 

## Conclusion 

As you can see, you can use containers locally on your computer to run automated data pipelines. This can make the life of a data engineer very easy for functional testing. 

Hope you've enjoyed this demo, See ya next time :) 

