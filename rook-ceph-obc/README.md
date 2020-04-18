## Ease your S3 based app development using Object Bucket Claims

We live in a world were S3 based application has become very popular due to the fact S3 is a simple way of dealing the application's data layer. In the early days, developers had to deal with a filesystem (whether it's Block or File storage) to maintain the application's file location, in addition having a file system can usually cause a bottleneck (due to large number of inodes, and the fact the the filesystem's metadata structure is based on binary trees). Having S3 provides us the ability of treating files as objects without worrying about the file location, objects can be written to an HTTP endpoint using ordinary CRUD operations (such as PUT,GET,DELETE,POST). S3 by it's nature, supports high loads and massive scale by using highly distributed storage backends (Ceph for example), but there is a disatvantage in S3 mainly when dealing with cloud-native applications based on Kubernetes - the needed configuration for the application to interact with the S3 object storage requires extra work. When an application interacts with S3 object storage system, it needs the endpoint url, the bucket name and the user's credentials which doesn't integrate with Kubernetes's objectives, so if we can consume File and Block storage using PVCs which are Kubernetes objectives, why can't we treat object storage the same way? This is why i wanted to talk about Object Bucket Claims. This feature is part of the rook-ceph orchestrator, and provides us the ability of creating Object Storage Classes. It means that using a CRD, a developer will be able to claim for a bucket on demand, which will eventually create the needed configuration, those values will be taken from the object storage provider (Ceph, AWS etc) and will be stored as Kubernetes ConfigMaps and Secrets the will be injected to the running application as environment variable. So let's see how easy it can be interacting with our object storage using Object Bucket Claims. 

# Prerequisites 
* A running Openshift cluster (version 4.3 minimum) 
* A running rook-ceph cluster (rook: release 1.2, ceph image: 14.2.8)

So we'll start by creating the S3 object storage using the `CephObjectStore` CRD, please create it with the following command: 
```bash 
cat <<EOF | oc create -f -
apiVersion: ceph.rook.io/v1
kind: CephObjectStore
metadata:
  name: my-store
  namespace: rook-ceph
spec:
  metadataPool:
    replicated:
      size: 3
  dataPool:
    replicated:
      size: 3
  preservePoolsOnDelete: false
  gateway:
    type: s3
    port: 8000
    securePort:
    instances: 1
EOF 
```

This CRD will create an S3 object storage service to our running rook-ceph cluster. The metadata and data pools will have 3 replicas, where the frontend API server will be listening in port 8000. 
Now let's verify that the created S3 service works properly, first we'll expose the service then curl to get the XML response: 

```bash 
oc get svc | grep rgw
                                                     
rook-ceph-rgw-my-store     ClusterIP   172.30.63.29     <none>        8000/TCP            22m
```

```bash 
oc port-forward svc/rook-ceph-rgw-my-store 8000                             
Forwarding from 127.0.0.1:8000 -> 8000

curl 127.0.0.1:8000                                                        
<?xml version="1.0" encoding="UTF-8"?><ListAllMyBucketsResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Owner><ID>anonymous</ID><DisplayName></DisplayName></Owner><Buckets></Buckets></ListAllMyBucketsResult>
```
Now after we have verified out S3 service works as expected, let's create an Object Storage Class that will allow us to start claiming for buckets from our rook-ceph cluster:

```bash 
cat <<EOF | oc create -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
   name: rook-ceph-delete-bucket
provisioner: ceph.rook.io/bucket
# set the reclaim policy to delete the bucket and all objects
# when its OBC is deleted.
reclaimPolicy: Delete
parameters:
  objectStoreName: my-store
  objectStoreNamespace: rook-ceph
  region: us-east-1
EOF
```

After creating the storage class, we'll create an Object Bucket Claim that will create a bucket in the existing rook-ceph cluster, in addition will create a Secret and a ConfigMap containing all the needed configuration: 

```bash 
cat <<EOF | oc create -f -
apiVersion: objectbucket.io/v1alpha1
kind: ObjectBucketClaim
metadata:
  name: ceph-delete-bucket
spec:
  generateBucketName: ceph-bkt
  storageClassName: rook-ceph-delete-bucket         
EOF 
```

This CRD will create a bucket with the prefix `ceph-bkt` in our rook-ceph cluster, let's verify that the OBC is in bound state: 

```bash 
oc describe obc ceph-delete-bucket | grep Status -A 1    

Status:
  Phase:  bound
``` 

We see that the OBC is in bound state, which means the bucket was succesfully created in our running rook-ceph cluster. Now let's take a look at the ConfigMap that was created: 

```bash 
oc describe cm ceph-delete-bucket        

Name:         ceph-delete-bucket
Namespace:    rook-ceph
Labels:       <none>
Annotations:  <none>

Data
====
BUCKET_HOST:
----
rook-ceph-rgw-my-store.rook-ceph
BUCKET_NAME:
----
ceph-bkt-93639f54-0a63-4e75-8c79-0b61c822b895
BUCKET_PORT:
----
8000
BUCKET_REGION:
----
us-east-1
BUCKET_SSL:
----
false
BUCKET_SUBREGION:
----

Events:  <none>
```

We see that `ceph-delete-bucket` ConfigMap was created, containing the proper configuration for our application to interact with our S3 service. The only thing that is missing is our credentials, which are stored in a Secret, let's verify that: 

```bash 
oc describe secret ceph-delete-bucket                                  

Name:         ceph-delete-bucket
Namespace:    rook-ceph
Labels:       <none>
Annotations:  <none>

Type:  Opaque

Data
====
AWS_ACCESS_KEY_ID:      20 bytes
AWS_SECRET_ACCESS_KEY:  40 bytes
```

We see the the secret stores our needed credentials. Now let's create a basic pod that will interact with the S3 service: 

```bash 
cat <<EOF | oc create -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: upload
  namespace: rook-ceph
spec:
  parallelism: 1
  template:
    metadata: 
      name: metadata
    spec: 
      containers:
        - image: shonpaz123/simple-upload:latest
          imagePullPolicy: IfNotPresent 
          name: upload
          envFrom: 
          - configMapRef: 
              name: ceph-delete-bucket
          - secretRef:
              name: ceph-delete-bucket 
      restartPolicy: Never
EOF 
```

This pod reacts as a Job, uploads one object into the created OBC storage class, as you see we have taken the env environments from the created Secret and ConfigMap. Let's verify the object was indeed uploaded by checking if the job has reached a complete state: 

```bash 
oc get pods | grep upload 

upload-cw7p7                                                   0/1     Completed   0          3m35s
```

So the Job has completed, let's interact with the toolbox the see if indeed the object was uploaded via radosgw-admin command-line: 

```bash 
oc rsh rook-ceph-tools-...

radosgw-admin bucket list --bucket ceph-bkt-93639f54-0a63-4e75-8c79-0b61c822b895
[
    {
        "name": "hosts",
        "instance": "",
        "ver": {
            "pool": 7,
            "epoch": 1
        },
        "locator": "",
        "exists": "true",
        "meta": {
            "category": 1,
            "size": 208,
            "mtime": "2020-04-18 11:19:14.589093Z",
            "etag": "bfc14cf2fb9d633c84f182630590d021",
            "storage_class": "",
            "owner": "ceph-user-8UCdTbVB",
            "owner_display_name": "ceph-user-8UCdTbVB",
            "content_type": "",
            "accounted_size": 208,
            "user_data": "",
            "appendable": "false"
        },
        "tag": "5e7234df-21fa-4d31-925e-3ea51d6514ac.4502.1565",
        "flags": 0,
        "pending_map": [],
        "versioned_epoch": 0
    }
]
``` 
We see that indeed we have and object created with the wanted prefix, and the hosts file was successfuly uploaded to the created OBC. Now, after we have chosen the Delete reclaim policy, the bucket should be deleted with all his objects after deleting the OBC: 

```bash 
cat <<EOF | oc delete -f -
apiVersion: objectbucket.io/v1alpha1
kind: ObjectBucketClaim
metadata:
  name: ceph-delete-bucket
spec:
  generateBucketName: ceph-bkt
  storageClassName: rook-ceph-delete-bucket
EOF
```

Now let's check if the bucket and it's content was indeed deleted from our rook-ceph cluster: 

```bash 
oc rsh rook-ceph-tools-...

radosgw-admin bucket list
[]
```

We see now we have no buckets at all in our rook-ceph cluster. Now let's delete the storage class and create a new one and an OBC for a retain reclaim policy, which menas that when a user will delete the OBC, the bucket will not be deleted as outcome providing the ability of another user to re-use this bucket in his application: 

```bash 
cat <<EOF | oc delete -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
   name: rook-ceph-delete-bucket
provisioner: ceph.rook.io/bucket
# set the reclaim policy to delete the bucket and all objects
# when its OBC is deleted.
reclaimPolicy: Delete
parameters:
  objectStoreName: my-store
  objectStoreNamespace: rook-ceph
  region: us-east-1
EOF
```

Now let's recreate those objects: 

```bash 
cat <<EOF | oc create -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
   name: rook-ceph-retain-bucket
provisioner: ceph.rook.io/bucket
# set the reclaim policy to retain the bucket when its OBC is deleted
reclaimPolicy: Retain
parameters:
  objectStoreName: my-store 
  objectStoreNamespace: rook-ceph
  region: us-east-1
EOF
```

```bash 
cat <<EOF | oc create -f -
apiVersion: objectbucket.io/v1alpha1
kind: ObjectBucketClaim
metadata:
  name: ceph-retain-bucket
spec:
  generateBucketName: ceph-bkt
  storageClassName: rook-ceph-retain-bucket
EOF
```

We have now a bounded OBC, lets recreate the job with the same ConfigMap and Secret references: 

```bash 
cat <<EOF | oc create -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: upload-retain-1
  namespace: rook-ceph
spec:
  parallelism: 1
  template:
    metadata: 
      name: metadata
    spec: 
      containers:
        - image: shonpaz123/simple-upload:latest
          imagePullPolicy: IfNotPresent 
          name: upload
          envFrom: 
          - configMapRef: 
              name: ceph-retain-bucket
          - secretRef:
              name: ceph-retain-bucket 
      restartPolicy: Never
EOF 
```

Now after the Job has completed, delete the OBC so that we can re-use the existing bucket with other job: 

```bash 
oc delete obc ceph-retain-bucket
```
Now rsh to the tooles pod again and gather the created timestamp of the uploaded object: 

```bash 
oc rsh rook-ceph-tools-...

radosgw-admin bucket list --bucket ceph-bkt-757fd71a-436a-470a-9ab3-7dc645ee40cb -f json | jq .[].meta.mtime
"2020-04-18 11:45:12.882977Z"
``` 

Now we'll recreate the OBC, but now for an existing bucket by specifiying the bucket's name instead of generating it: 

```bash 
cat <<EOF | oc create -f -
apiVersion: objectbucket.io/v1alpha1
kind: ObjectBucketClaim
metadata:
  name: ceph-retain-bucket
spec:
  bucketName: ceph-bkt-757fd71a-436a-470a-9ab3-7dc645ee40cb
  storageClassName: rook-ceph-retain-bucket
EOF
```
Let's re-run the upload Job again and see if the same bucket was used by extracting the objects creation time again: 

```bash 
```bash 
cat <<EOF | oc create -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: upload-retain-2
  namespace: rook-ceph
spec:
  parallelism: 1
  template:
    metadata: 
      name: metadata
    spec: 
      containers:
        - image: shonpaz123/simple-upload:latest
          imagePullPolicy: IfNotPresent 
          name: upload
          envFrom: 
          - configMapRef: 
              name: ceph-retain-bucket
          - secretRef:
              name: ceph-retain-bucket 
      restartPolicy: Never
EOF 
```

```bash 
oc rsh rook-ceph-tools-...

radosgw-admin bucket list --bucket ceph-bkt-757fd71a-436a-470a-9ab3-7dc645ee40cb -f json | jq .[].meta.mtime
"2020-04-18 11:53:28.148781Z"
``` 

As you see the second upload contains a different creation time, which menas the same bucket from our rook-ceph cluster aws used. 

## Conclusion

We saw that we can achieve great flexibility when using OBC feature, this ability will help to ease the development process and will allow Devops/Developers to interact with the data layer abstractly without having to maintain the knowledge about it. 
Thank you very much, hope you have enjoyed this demo, have fun :)
