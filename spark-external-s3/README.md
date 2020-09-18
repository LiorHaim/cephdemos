# Run you Spark data processing workloads using OpenDataHub, OCS and an external Ceph cluster

Kubernetes has become the de facto-standard container orchestration platform. With this approach, organizations are trying to gather up all their applications and platforms around Kubernetes to take adventage of its stability, agility and simplicity. Running your whole stack in Kubernetes will allow you to have a single API and a common language whether it's for an application, a database, or a storage engine needs to be deployed. 

A few years ago, people believed that in order to gain more performance for big data workloads, your application needs to have performant local disks mostly based on flash media. Collocating compute and storage together brought its own challenges, mostly when having failures, upgrades as organizations had to treat them both as a one unit. 

Today we see a lot of data processing engines such as Spark, Presto, etc using S3 as a storage backend. There are various reasons to use S3 for you big data workloads: 
* S3 is a Throughput oriented storage system, that can support tremendous amounts of data being transfered back and forth 
* S3 is HTTP based, which can be very portable when having to develop a connector to access it 
* S3 has it's own intelligent data management features such as Bucket Lifecycle, Storage Classes, Versioning, etc that offloads the data management tax from the end user 

Today I would like to focus with you on how you can run your data processing engine, running on Kubernetes using an S3 storage backend. To do so, let's have a short brief on the platforms we are going to use: 

* Ceph - will be used as a S3 gateway, external to the Openshift cluster 
* Openshift Container Storage - Will provide us the Kubernetes-like features to treat our S3, will be dicussed later on 
* Open Data Hub - Will be used as the data processing provisioner for our spark cluster, and jupyter notebooks to run our Spark workloads 

## Prerequisites 

* A running Openshift 4.5 cluster 
* A running RHCS 4.1 cluster 
* Network connectivity between those two 

The first component we are going to deploy will be OCS (Openshift Container Storage), which will be the Kubernetes management plain for out S3 storage backend. With OCS 4.5, that was released yesterday, you could connect you external Ceph cluster to your OCS management plane to make use of its resources. This deployment method is called "independent mode", and mostly used when the workloads and volumes being processed are bigger than the OCS inernal mode could handle. (Internal mode will run your Ceph cluster on Openshift, useful for small-medium data workloads). 

Let's connect to our Openshift cluster, get into the `Operator Hub` tab and install the OCS operator. This Operator will deploy our OCS management plain, and will be connected the external Ceph cluster: 

================= Installing OCS 

After we have our Operator installed, Let's create an independent cluster, to do so we hit the `Create Storage Cluster` and hit `independent mode`. This will ask as to run a script on our Ceph cluster, which will gather all the needed information to connect OCS to our external Ceph cluster. The script will throw a json file to STDOUT, please take it and paste it in the snippet. 

======================= OCS create cluster 

After we create the cluster, we should have it in a `Ready` state:

========================== OCS cluster ready 

Now that we have our S3 backend ready, Let's create an `Object Bucket Claim` so that our Spark application could use it for processing the data. An OBC (Object Bucket Claim), is a way of treating a bucket as its was a Kubernetes Persistent Volume Claim. This object is unique to OCS and offloads the developer's need to track after it's credentials, bucket name and endpoint URL. To create a bucket claim, just go to `Object Bucket Claims` (under the stroage tab) in the Openshift console, create an OBC and choose the RGW storage class as target. 

This automation will create a user and a bucket in our external Ceph cluster, and will store all the information in ConfigMaps and Secrets in our Openshift cluster. Credentials will be stored as a secret, while bucket name, bucket port and endpoint url will be stored as ConfigMap. 

To verify the bucket wes indeed created, let's access our Ceph cluster and list the buckets we have using the `radosgw-admin` command: 

```bash 
$ radosgw-admin bucket list | grep spark
    "spark-bucket-1143d1c8-e321-496a-821c-9c1b89297685"
```

We see that we have the bucket created by OBC, and now let's try to get more information on our created bucket: 

```bash
$ radosgw-admin bucket stats --bucket spark-bucket-1143d1c8-e321-496a-821c-9c1b89297685
{
    "bucket": "spark-bucket-1143d1c8-e321-496a-821c-9c1b89297685",
    "num_shards": 11,
    "tenant": "",
    "zonegroup": "c6f894d0-256a-425f-92ec-b5c41366c1cb",
    "placement_rule": "default-placement",
    "explicit_placement": {
        "data_pool": "",
        "data_extra_pool": "",
        "index_pool": ""
    },
    "id": "9cdf5d28-ceb4-4629-b507-13509f8c99ab.84164.2",
    "marker": "9cdf5d28-ceb4-4629-b507-13509f8c99ab.84164.2",
    "index_type": "Normal",
    "owner": "ceph-user-bbX0Qdrn",
    "ver": "0#1,1#1,2#1,3#1,4#1,5#1,6#1,7#1,8#1,9#1,10#1",
    "master_ver": "0#0,1#0,2#0,3#0,4#0,5#0,6#0,7#0,8#0,9#0,10#0",
    "mtime": "2020-09-17 14:15:12.993277Z",
    "max_marker": "0#,1#,2#,3#,4#,5#,6#,7#,8#,9#,10#",
    "usage": {},
    "bucket_quota": {
        "enabled": false,
        "check_on_raw": false,
        "max_size": -1,
        "max_size_kb": 0,
        "max_objects": -1
    }
}
```

We see that a new user was created as well (under the `Owner` section). Now let's verify we have our information located in our Openshift cluster as guaranteed. Let's describe our OBC object called `spark-bucket`:

```bash
$ oc describe secret spark-bucket
                                                                                                               
Name:         spark-bucket
Namespace:    amq-streams
Labels:       bucket-provisioner=openshift-storage.ceph.rook.io-bucket
Annotations:  <none>

Type:  Opaque

Data
====
AWS_ACCESS_KEY_ID:      20 bytes
AWS_SECRET_ACCESS_KEY:  40 bytes
```

We see that we have the Access Key and Secret Key stored as secret in Openshift cluster. Now let's do the same and decribe the config map to see if we have the rest of the information:

```bash
$ oc describe cm spark-bucket                                                                                                                

Name:         spark-bucket
Namespace:    amq-streams
Labels:       bucket-provisioner=openshift-storage.ceph.rook.io-bucket
Annotations:  <none>

Data
====
BUCKET_NAME:
----
spark-bucket-1143d1c8-e321-496a-821c-9c1b89297685
BUCKET_PORT:
----
8080
BUCKET_REGION:
----
us-east-1
BUCKET_SUBREGION:
----

BUCKET_HOST:
----
10.32.0.3
Events:  <none>
``` 

Great! We have the information we need so that our Spark application could reach our S3 backend. Let's create a new project called `odh` that will store the `Open Data Hub` workloads. 

```bash
$ oc new-project odh 
```

After that, we'll install the Open Data Hub operator so that we can start and provision our Spark cluster: 

====================== Install ODH 

After we have successfully installed our ODH operator, we'll create an `Open Data Hub` custom resource that will provision all the needed objects for us to use.
After creating the CR, a route will be created for you `Jupyter Hub` notebook, create a new notebook from the `s2i-spark-minimal-notebook:3.6` image. 

======================= Spark notebook 

Creating this notebook, will create a spark cluster, which each one of the pods are acting as a Spark executer. This will also create a notebook Database that will store all the information being saved in the notebook. This is 1:1 relation with your user, so the next time you'll be logged in you'll see the same notebook. 

Now let's see if pods were indeed created: 

```bash 
$ oc get pods                                                                                                                  

NAME                                    READY   STATUS      RESTARTS   AGE
jupyterhub-1-2bglz                      1/1     Running     0          17m
jupyterhub-1-deploy                     0/1     Completed   0          17m
jupyterhub-db-1-72fbr                   1/1     Running     0          17m
jupyterhub-db-1-deploy                  0/1     Completed   0          17m
jupyterhub-nb-kube-3aadmin              2/2     Running     0          14m
opendatahub-operator-6c96795b8b-kmhhh   1/1     Running     0          19m
spark-cluster-kube-admin-m-9w69r        1/1     Running     0          14m
spark-cluster-kube-admin-w-wb54g        1/1     Running     0          14m
spark-cluster-kube-admin-w-x5zn9        1/1     Running     0          14m
spark-operator-74cfdf544b-mrdzf         1/1     Running     0          17m
```

Great! we have out infrastructure. Now let's verify our `Jupyter Notebook` is persisted: 

```bash 
$ oc get pv                                                                                                                          
NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM                                STORAGECLASS                              REASON   AGE
pvc-6ec75973-a17a-44d6-b308-42cc4c4664fd   1Gi        RWO            Delete           Bound    odh/jupyterhub-db                    ocs-independent-storagecluster-ceph-rbd            43m
pvc-b3064182-ef7c-434f-a3f3-10c8f198a7d8   2Gi        RWO            Delete           Bound    odh/jupyterhub-nb-kube-3aadmin-pvc   ocs-independent-storagecluster-ceph-rbd            39m
```

For a Bonus, ODH operator will attach a PVC for out notebook DB, that is taken from the RBD pool being stored in our external Ceph cluster, we get two storage protocols in one system, what an excitement!

Let's have a short brief on our Spark workload. In this workload, we will be uploading a CSV file to our S3 bucket, that contains students' grades. This CSV file contains the names of the students, and their score in 4 grades, so as the final grade. Our target is to collect to frequency for each grade using Spark processing. 

Let's take a look at our Jupyter notebook: 

========================= Notebook 


A little explanation on what we are seeing here: 

* In the first stage, we check the connectivity in our Spark cluster, where the output being printed is the names of our spark executers, can be correlated with the pods running. 
* Later, we use `wget` to download the CSV file to our notebook locally, will be saved in our DB 
* We use `boto` library in order to upload the CSV file into our S3 bucket using the information gathered from our bucket claim 
* Then, we use the same vaiables to set the configuration being used by our Spark `s3a` connector 
* We read the CSV file from our S3 bucket, and print the grades. Pay attention! we have a flase value, which is "A" in our 9th cell that can affect the reliability of our data 
* We clean this value and finally build a grade frequency plot 


## Conclusion 

We saw how can make use of Openshift's platforms in order to run our Spark processing workload in a simple, accessible way. Using OCS's adventages, we have gained simplicity with the way we treat our S3 storage backend, and earned a two-storage-protocol storage engine solution to store both our data set and our notebook's DB. Hope you've enjoyed this demo, see ya in the next one :)







