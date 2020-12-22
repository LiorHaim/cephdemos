# Run your Business Intelligence using Presto & Superset, Backed by OpenDataHub and OCS Openshift operators 

The Big Data world is making it's way towards Kubernetes and we already see many Data Processing and AI/ML products building their solution around Kubernetes to assure stability, scalability and availability. 

Until now, most of the solutions were VM based, with no orchestration, automation or config management layers above, which caused those solutions to be less scalable and a little bit of a pain. 
With Kubernetes we can provide far more scalable solutions, that are fully automated and will preserve their state after failures. 

With the will to run Big Data workloads on Kubernetes, comes the need for a simple solution what will cover most of the organizations' use cases in order to create a common language, save the man power, and base the engineers' skills around one component.

To do so, Many organizations are looking at Presto, A distributed SQL query engine that can retrieve data from multiple sources such as Elasticseaerch, Cassandra, SQL, and S3. With the help of presto, you could build your knowledge across SQL with no need to create your own scripts and coverters which eventually create organization silos, and stop you from reaching your business goals. 

Presto's abillity to query S3 solves a lot of difficulties coming from the Big Data world. Organizations are mainlyfocusing on throwing all their data to a *Data Lake*, to store both structured,  unstructured and semi-structured data coming from IoT devices, Social media, internal systems, etc. 
With the integration of the two, you could base your organization across Presto, whether it's for *BI* or for training your *AI/ML* algorithms. 

In this Demo, I'll show you how you could use *Openshift Container Platform* to run a Presto cluster using *Stratbust's Presto Operator* that will manage our cluster's entire lifecycle. In addition, We'll use *Openshift Container Storage* for both Object and Block Storage to store our queried data. To analyze our data, we'll use *Open Data Hub* operator that will provide us the abillity the connect Superset to presto in order to perform some BI analysis. 

Let's get started!

## Prerequisistes 
* A running Openshift 4.6.3 cluster 
* An available S3 service (Mine is provided with OCS4.6)
* A running OpenDataHub cluster 

## Installation 

### S3 Service Preparation
To start the demo, first Let's take a look at our installed operators under the `openshift-storage` project, to verify we have the `Openshift Container Storage` operator fully installed: 

######### OCS picture ############ 

Now that we have our operator Installed and the `StorageCluster` fully up and running, let's verify that the Ceph cluster backing up our storage solution is fully operational. To do so, we'll enable the *tools* pod, which will allow us running Ceph commands: 

```bash
oc rsh -n openshift-storage $(oc get pods -n openshift-storage | grep rook-ceph-tools | grep Running | awk '{print $1}')
```

Now We'll run `ceph -s` to make sure our cluster is in a healthy state: 

```bash
$ ceph -s

  cluster:
    id:     571a7398-d050-429f-83b0-f758e42e024b
    health: HEALTH_OK
 
  services:
    mon: 3 daemons, quorum a,b,c (age 13m)
    mgr: a(active, since 13m)
    mds: ocs-storagecluster-cephfilesystem:1 {0=ocs-storagecluster-cephfilesystem-b=up:active} 1 up:standby-replay
    osd: 3 osds: 3 up (since 13m), 3 in (since 13m)
    rgw: 1 daemon active (s3a.a)
 
  task status:
    scrub status:
        mds.ocs-storagecluster-cephfilesystem-a: idle
        mds.ocs-storagecluster-cephfilesystem-b: idle
 
  data:
    pools:   10 pools, 176 pgs
    objects: 305 objects, 87 MiB
    usage:   3.1 GiB used, 1.5 TiB / 1.5 TiB avail
    pgs:     176 active+clean
 
  io:
    client:   938 B/s rd, 45 KiB/s wr, 1 op/s rd, 2 op/s wr
```

We see that our cluster is fully operational, we can create an S3 user that we'll give presto to interact with our OCS S3 service: 

```bash 
$ radosgw-admin user create --display-name="odh" --uid=odh      
{
    "user_id": "odh",
    "display_name": "odh",
    "email": "",
    "suspended": 0,
    "max_buckets": 1000,
    "subusers": [],
    "keys": [
        {
            "user": "odh",

            "access_key": "HC8V2PT7HX8ZFS8NQ37R",
            "secret_key": "Y6CENKXozDDikJHQgkbLFM38muKBnmWBsAA1DXyU"
        }
    ],
```

Great! now we have our S3 service ready for us to interact with. 

### Upload Data to our S3 bucket 

In this section, we'll upload a pre-created JSON to a S3 bucket so that Presto will be able to query it. Let's create some configuration for `awscli`: 

```
$ export AWS_ACCESS_KEY_ID=HC8V2PT7HX8ZFS8NQ37R 
$ export AWS_SECRET_ACCESS_KEY=Y6CENKXozDDikJHQgkbLFM38muKBnmWBsAA1DXyU 
```

Important! use the same credentials that you have created in the previous section so that Presto will be able to see the created bucket. 

Now let's create a bucket and upload our JSON file to the S3 bucket:

```
$ aws s3 mb s3://processed-data --endpoint-url http://rgw-openshift-storage.apps.cluster-b601.b601.example.opentlc.com
$ aws s3 cp accounts.json s3://processed-data/accounts.json/ --endpoint-url http://rgw-openshift-storage.apps.cluster-b601.b601.example.opentlc.com
```

*Important!* for Presto to create a schema the object should be places inside a S3 prefix (folder). 
In the real world, this phase is handled automatically, as your ETL pipelines will probably process data (Bronze-Silver-Gold) and will throw all the processed objects to the Gold bucket, in our case, it's the processed-data bucket. 

### Deploying our Presto cluster 

In order for Presto to save metadata, we use Hive. As Hive needs a place to save all the information about schemas and tables, a PostGreSQL cluster should be deployed in advance. 

To do so, we'll use the `oc` command to create our deployment:

```bash
oc create -f 01-presto-pg-deployment.yml 
```

Let's verify the PostgreSQL database is fully operational: 

```
$ oc get pods                                                                                                               
NAME                        READY   STATUS    RESTARTS   AGE
postgres-68d5445b7c-fpp8x   1/1     Running   0          46s
```

Now let's see our PostgreSQL cluster bounded a PVC coming from our RBD storage class: 

```bash 
$ oc get pvc                                                                                                              
NAME                STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS                  AGE
postgres-pv-claim   Bound    pvc-452121cc-c46f-4444-9424-113f00587e6e   5Gi        RWO            ocs-storagecluster-ceph-rbd   14m
``` 

Great ! our PostgreSQL cluster is ready consuming data from OCS!
Now let's create our presto cluster, before we do so, we'll install the Presto Operator coming from the Operator Hub: 

########################## Presto Operator ############################

First, we'll create a secret that Presto will use to access our S3 service, this secret will contain our S3 access and secret key: 

```bash 
oc create secret generic aws-secret --from-literal=AWS_ACCESS_KEY_ID="HC8V2PT7HX8ZFS8NQ37R" --from-literal=AWS_SECRET_ACCESS_KEY="Y6CENKXozDDikJHQgkbLFM38muKBnmWBsAA1DXyU"
```

Ww'll point Presto to pull the credentials from this secret. 

Great, now we can create our cluster, to do so, we'll use the `oc` command to create a Presto CR to the Presto Operator, which will eventually create our cluster with all the needed config: 

```
$ oc create -f 02-presto-deployment.yml      
```

*Important!* make sure you modify both `hive.s3.endpoint` and `s3Endpoint` to point to your S3 service. If your S3 service is located within the Openshift cluster itself, you should the S3 ClusterIP service ip address to work with `path_style`, for example: 

```
$ oc get svc -n openshift-storage | grep rgw                                                                                  
rook-ceph-rgw                                  ClusterIP      172.30.255.77    <none>            
```

Now that we have the S3 ip address, we can put it in the Presto CR so that Presto could use it. 
Let's verify our Presto cluster is fully operational: 

```bash 
$ oc get pods                                                                                                                 
NAME                                             READY   STATUS    RESTARTS   AGE
hive-metastore-presto-odh-5fd66d5848-w84cw       1/1     Running   0          6m46s
postgres-68d5445b7c-fpp8x                        1/1     Running   0          13m
presto-coordinator-presto-odh-84cf47f6f9-22wx2   2/2     Running   0          6m46s
presto-operator-877cb866b-7fmkd                  1/1     Running   0          10m
presto-worker-presto-odh-7864984fc5-m4jjg        1/1     Running   0          6m46s
presto-worker-presto-odh-7864984fc5-rp85m        1/1     Running   0          6m46s
```

Great! we have all the needed resources to start querying our S3 service! 
To do so, let's connect to our `coordinator` pod: 

```bash
$ oc rsh $(oc get pods | grep coordinator | grep Running | awk '{print $1}')
``` 
Now we'll connect to the `presto-cli` shell to start running some queries: 

```bash 
sh-4.4$ presto-cli --catalog hive 
presto> CREATE SCHEMA hive.accounts WITH (location='s3a://processed-data/accounts.json/');
CREATE SCHEMA
```

We are telling Presto that we want to create a schema that will be located on a specific prefic (folder) in our S3 bucket. 
Now let's create a Table that will be mapped to the JSON we've uploaded earlier: 

```bash 
presto> USE hive.accounts;
presto:accounts> CREATE TABLE accounts (name varchar, age int, country varchar) WITH (format = 'json', external_location = 's3a://processed-data/accounts.json/');
CREATE TABLE
```

We've switched our context to use the created schema, then created a table that maps all the columnar fields to the JSON keys we have in our S3 bucket, finally told Presto that the file sitting in the bucket is in JSON format. 

Tam Tam Tam! our moment has arrived :)
Now let's query our table: 

```bash 
presto:accounts> SELECT * from accounts;
  name   | age  | country 
---------+------+---------
 Michael | NULL | NULL    
 Shimon  |   30 | Israel  
 Melissa |   12 | Spain   
 Shon    |   24 | Spain   
 Jake    |   28 | US      
 Kate    |   50 | Hungary 
 Aaron   |   35 | Africa  
 Aaron   |   35 | Africa  
(8 rows)
``` 

Jackpot! we've just SQL queried a JSON located in our S3 bucket! 

In a real production environment, you'll definitely won't work with the `presto-cli` and you'll need a more intelligent solution, to do so' we'll use `Superset` to start doing some BI work. 

To do so, We'll use the `Open Data Hub` operator that will provide us with a full deployment of superset: 

###################################3 Install Open Data Hub 

Now that we have Superset installed, let's login to it to integrate Presto with it. To do so we'll search for it's route so we can access it externally: 

```bash
oc get route 
NAME                                HOST/PORT                                                                 PATH   SERVICES   PORT       TERMINATION   WILDCARD
route.route.openshift.io/superset   superset-openshift-operators.apps.cluster-b601.b601.example.opentlc.com          superset   8088-tcp                 None
```

Now login to the Superset UI, with the `admin:admin` credentials, unless mentioned otherwise. 
Go to DataBases --> Add Database and add our accounts database, located on Presto as our database (you should use your Presto ClusterIP service to connect Suprtset with it). Finally hit the *Test Connection* button to verify all is good:

################################## test connection ##########################3

Now navigate to SQL LAb --> SQL Editor and start querying our accounts database: 

################################## Superset query 

Great! We've just created our first BI work on Openshift! 

## Conclusion 

We saw how we can run SQL queries against S3 service, where all located on Openshift and provided by fully-managed operators as part of the Openshift Operator Hub. This will allow a lower TTM and faster buisness goals as all is handled under one single platform - BI, Data Processing, Storage products under one umbrella. 

Hope you found this interseting, see ya next time :) 

