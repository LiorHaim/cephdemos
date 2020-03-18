Benchmark your Ceph based S3 service with s3bench and ELK, using Openshift platform objectives: 

## Introduction
In the previous chapters we have talked a lot about Ceph and it's S3 interface. We saw how we can manage our data via declarative movement policies, exipre our data priodically etc. Those features are very important and they help us in making our data pipeline fully automated, but let us not forget these features aren't that relavant unless our S3 service can perform as expected. As the responsible for your S3 service, you should have the proper tools that will help you analyze and unserstand whether your S3 service performs as you would expect, and if not will allow you to find the RCA (root cause analysis) for the problem. There are plenty of benchmark tools intergrating with the S3 API but most of them are kind of old and messy and the way the world goes, we should make our life easy as possible especially when dealing with performance tests. This is why i wanted to talk about s3bench, a containerzied tool written in python that will help you creating various workloads in front of your S3 service. This tool integrates with every S3 API (aws, minio, Ceph etc) and can help you analyze youre S3 service's behaviour using ELK stack for visualizations and dashboards. s3bench is supported as a single container, composed service or K8S/Openshift job. For this demo, i am running rook-ceph cluster exposing the S3 service (deployment process is documented in the previous chapters) and a running ELK stack all acting on my Openshift cluster. We will see how we can use Openshift's objetives to make our life easier when dealing with a benchmark. 

## Prerequisites 
To run this demo, you should have a S3 interface and running ELK stack (version 7.X minimum). 

## Installation 

So we'll start with verifying we have access to our s3 service, and although rook-ceph created it's services as ClusterIP services, we will port-forward the S3 service to test the output: 

```bash 
oc port-forward svc/rook-ceph-rgw-my-store 8000:80 

curl 127.0.0.1:8000
<?xml version="1.0" encoding="UTF-8"?><ListAllMyBucketsResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Owner><ID>anonymous</ID><DisplayName></DisplayName></Owner><Buckets></Buckets></ListAllMyBucketsResult>
``` 
So we see our S3 service is wirking fine, now let's test out ELK stack is working as well: 

```bash 
oc get elasticsearch 
NAME         HEALTH   NODES   VERSION   PHASE   AGE
quickstart   yellow   1       7.6.1     Ready   100m

oc get kibana 
NAME         HEALTH   NODES   VERSION   AGE
quickstart   green    1       7.6.1     100m
``` 

We see both elastic and kibana are in green state, which means our cluster is running as expected. I recommend using ECK operator to create you ELK stack, it's very easy to deploy and ideal when using Openshift. 
Now that have out requirements met, let's move on to the main show, s3bench. To use s3bench, please clone the following git repository and change to openshift directory: 

```bash 
git clone https://github.com/shonpaz123/s3bench.git && cd s3bench/openshift
```

Now that we are in the proper directory, let's have a little background of how s3bench works. s3bench gets all his needed information from arguments. These arguments are parsed using argparse python library and this is when s3bench starts doing it's workload. To ease the process, we will be using Openshift templates for parsing those arguments into our s3bench deployment. s3bench then runs as Openshift job, in parallel according to our replica factor, simulating the workload of multi-client workloads. 
All we need to do is edit the `s3bench.env` file, and this parameters file will be processed by Openshift creating our s3bench jobs. 

Example for s3bench.env file: 

```bash 
ACCESS_KEY=*********************
SECRET_KEY=***************************
ENDPOINT_URL=http://YOUR_RGW_FQDN
ELASTIC_URL=https://elastic:<YOUR_ELASTIC_PASSWORD>@<YOUR_ELASTIC_FQDN>:9200
WORKLOAD=write
OBJECT_SIZE=2MiB
NUM_OBJECTS=100
BUCKET_NAME=s3bench 
REPLICAS=5
```

According to our configuration, there will be 5 different pods writing 100 objects in 2MiB object size to a bucket called s3bench. 
As you see we have all the needed parameters, notice you access key, secret key, and elastic password can be fetched from Openshift (saved as secrets) with the following commands: 

```bash 
oc get secret quickstart-es-elastic-user -o=jsonpath='{.data.elastic}' | base64 --decode;echo
oc get secret rook-ceph-object-user-my-store-my-user -n rook-ceph -o 'jsonpath={.data.AccessKey}' | base64 --decode;echo
oc get secret rook-ceph-object-user-my-store-my-user -n rook-ceph -o 'jsonpath={.data.SecretKey}' | base64 --decode;echo
``` 

These commands will print to STDOUT the needed keys for you to put in `s3bench.env` file. Now please edit your file so it suits your environemnt and let's move on to the next step. After we have edited the file with the right parameters, let's create out job: 

```bash 
oc process -f s3bench.yaml --param-file s3bench.env | oc create -f -; sleep 120; oc get pods
job.batch/s3bench created

NAME                                                           READY   STATUS      RESTARTS   AGE
s3bench-959j7                                                  0/1     Completed   0          2m
s3bench-fdfgg                                                  0/1     Completed   0          2m
s3bench-fr68b                                                  0/1     Completed   0          2m
s3bench-kg5km                                                  0/1     Completed   0          2m
s3bench-mgpcr                                                  0/1     Completed   0          2m
``` 

As you see, we have all our pods in a completed state, which means they all finished writing to the out S3 service. Let's verify we have the right amount of files in kibana, but first let's port-forward to the kibana service: 

```bash 
oc port-forward svc/quickstart-kb-http 5601
```

Let's open our browser in http://127.0.0.1:5601 and access the Discover tab, there we should see 500 hits (5 Jobs * 100 Objects). s3bench will document the Latency and the Throughput each operation infront of the S3 service took. Now let's try the same but for a read. Change the workload to read in the s3bench.env file and run the job again: 

```bash 
oc process -f s3bench.yaml --param-file s3bench.env | oc create -f -; sleep 120; oc get pods
job.batch/s3bench created

NAME                                                           READY   STATUS      RESTARTS   AGE
s3bench-2vq75                                                  0/1     Completed   0          2m
s3bench-6pxg6                                                  0/1     Completed   0          2m
s3bench-bnxjt                                                  0/1     Completed   0          2m
s3bench-jxg4h                                                  0/1     Completed   0          2m
s3bench-xtb8l                                                  0/1     Completed   0          2m
```

So the jobs has finished and we can repeat the same process to verify we have 1000 hits in the kibana. So, this is great, we write objects to our S3 service, we have all our data stored in elasticsearch but what about the actual visualizations? 
To import the needed dashboard we will use another openshift template that will curl to the kibana's url and POST the ndjson file that contains all the dashboard's data:

```bash 
oc process -f dashboard.yaml -p KIBANA_URL=https://elastic:<YOUR_ELASTIC_PASSWORD@<YOUR_KIBANA_FQDN>:5601 | oc create -f -; sleep 45; oc get pods 
job.batch/dashboard created

```

As we see our dashbaord job is done and now we can finally reach our the kibana and hopefully we will have all the needed information already imported: 

```bash 
oc process -f dashboard.yaml -p KIBANA_URL=https://elastic:8d7ptk7sr79hs5cj5dhzsmr9@10.128.0.120:5601 | oc create -f - 
job.batch/dashboard created

oc get pods | grep dashboard 

NAME                                                           READY   STATUS      RESTARTS   AGE
dashboard-5z6xq                                                  0/1     Completed   0          2m
``` 

We see out dashboard import is completed, so now let's browse to the kibana and see if we have a new dashbaord "Demo" created: 
Pic


Now, let's click that dashboard and see what are out results: 
Pic 

Let's talk about what we see in the following dashboard: 

* Latency graph - Aggregates the response time of all the clients with a date histogram giving us the ability of tracking each client's latency over time. 
* Throughput graph - Aggregates the througput of all clients with a date histogram giving us the ability of tracking the throughput metric over time. 
* Percentiles Data Table - Sorts all data to Percentiles so that we could watch for latency outlayers (calculating the average is not always the best choice, it's important to see the distribution of the response times among percentiles to verify there is no outlayer that has ruined your average value).
* Max Latency Object - Sometimes, we want to debug what happaned with a specifc object, when having a benchmark running for few hours, it's hard to find out who is the devil object that runied you results, so in this dashboard s3bench finds it for you. 

## Conclution 

Ofcourse benchmarking is a whole other scope, and we will have an article about that also, but it is important to see how we could benchmark our S3 service quite easily using Openshift objectives with s3bench. 
This tool can be used with different workloads, unlimited number of clients, and mixed object sizes for making your life easier when having to test you S3 service. Feel free to contribute to this tool, ask for feature requests or even open issues ;) 
   

