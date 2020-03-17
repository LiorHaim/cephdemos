## Run your S3 object storage service on Openshift using rook-ceph

With the new version of Openshift(4.3), we can use rook-ceph orchestrator to deploy a Ceph cluster in minutes. Rook is a container based orchestrator for Kubernetes/Openshift environments which simplifies storage manamgent. It can deploy and manage serveral products besides Ceph such as Noobaa, EdgeFS, Minio, Cassandra and more. Rook-ceph is actually an extention of the Kubernetes API (made by CRDs), allowing Kubernetes to "speak" Ceph's language, Each CRD is eventually translated to Kubernetes objectives making the whole process possible. Rook-ceph Day-1 and Day-2 operations are managed by the rook-ceph operator that "watches" the Ceph cluster and waiting to take action whenever needed. With rook-ceph, we can provide a unified storage solution for Kubernetes/Opeshift environments, handeling block storage (for io intensive workloads), file storage (for file sharing between pods) and object storage (for big data applications) in one deployment. 

Common CRDs in the rook-ceph project: 
* cephclusters
* cephobjectstores
* cephobjectstoreuers
* cephfilesystems
* cephblockpools

In this demo, we will talk specifically about rook-ceph's object storage interface (for Openshift), other storage strategies are out of this demo's scope. We will watch the CRDs addition, the operator deployment, and ceph deployment of the cluster itself. 

## Prerequisits 
To run this demo, you should have a running Openshift cluster in 4.3 version. 

## Installation 

Let's first clone rook's git repository so we could use the latest version of rook: 

```bash 
git clone --single-branch -b release-1.2 https://github.com/rook/rook.git && cd rook/cluster/examples/kubernetes/ceph/
``` 

After we are in he current directory, we'll start creating the CRDs to extend the Openshift API:
 
```bash 
oc create -f common.yaml 
namespace/rook-ceph created
customresourcedefinition.apiextensions.k8s.io/cephclusters.ceph.rook.io created
customresourcedefinition.apiextensions.k8s.io/cephclients.ceph.rook.io created
customresourcedefinition.apiextensions.k8s.io/cephfilesystems.ceph.rook.io created
customresourcedefinition.apiextensions.k8s.io/cephnfses.ceph.rook.io created
customresourcedefinition.apiextensions.k8s.io/cephobjectstores.ceph.rook.io created
customresourcedefinition.apiextensions.k8s.io/cephobjectstoreusers.ceph.rook.io created
customresourcedefinition.apiextensions.k8s.io/cephblockpools.ceph.rook.io created
customresourcedefinition.apiextensions.k8s.io/volumes.rook.io created
customresourcedefinition.apiextensions.k8s.io/objectbuckets.objectbucket.io created
customresourcedefinition.apiextensions.k8s.io/objectbucketclaims.objectbucket.io created
.
.
.
.
```

After extending Openshift's API, we can see the new api resources added to out cluster: 

```bash 
oc api-resources  | grep ceph
cephblockpools                                          ceph.rook.io                          true         CephBlockPool
cephclients                                             ceph.rook.io                          true         CephClient
cephclusters                                            ceph.rook.io                          true         CephCluster
cephfilesystems                                         ceph.rook.io                          true         CephFilesystem
cephnfses                             nfs               ceph.rook.io                          true         CephNFS
cephobjectstores                                        ceph.rook.io                          true         CephObjectStore
cephobjectstoreusers                  rcou,objectuser   ceph.rook.io                          true         CephObjectStoreUser
``` 

Now, after creating the needed api resources, let's move on and create the operator's deployment so it could start watching for further actions (operator will be created in a namespace called rook-ceph, you could type `oc project rook-ceph` and you won't need to specify --namespace flag each time): 

```bash 
oc project rook-ceph; oc create -f operator-openshift.yaml; sleep 120; oc get pods

securitycontextconstraints.security.openshift.io/rook-ceph created
securitycontextconstraints.security.openshift.io/rook-ceph-csi created
configmap/rook-ceph-operator-config created

deployment.apps/rook-ceph-operator created
NAME                                  READY   STATUS    RESTARTS   AGE
rook-ceph-operator-85ccdb9ffd-qfxpl   1/1     Running   0          2m29s
rook-discover-f44rd                   1/1     Running   0          98s
```

As you see, we have two pods created, one is the operator pod itself, and the other one is the discover pod responsible for collecting data about the nodes it is running on (for example, disk number and name collection).
Let's look at the cephcluster deployment yaml: 

```bash 
apiVersion: ceph.rook.io/v1
kind: CephCluster
metadata:
  name: rook-ceph
  namespace: rook-ceph
spec:
  cephVersion:
    image: ceph/ceph:v14.2.8
    allowUnsupported: true
  dataDirHostPath: /var/lib/rook
  skipUpgradeChecks: false
  continueUpgradeAfterChecksEvenIfNotHealthy: false
  mon:
    count: 1
    allowMultiplePerNode: true
  dashboard:
    enabled: true
    ssl: true
  monitoring:
    enabled: false  # requires Prometheus to be pre-installed
    rulesNamespace: rook-ceph
  network:
    hostNetwork: false
  rbdMirroring:
    workers: 0
  crashCollector:
    disable: false
  mgr:
    modules:
    # the pg_autoscaler is only available on nautilus or newer. remove this if testing mimic.
    - name: pg_autoscaler
      enabled: true
  storage:
    useAllNodes: true
    useAllDevices: false
    config:
      databaseSizeMB: "1024" # this value can be removed for environments with normal sized disks (100 GB or larger)
      journalSizeMB: "1024"  # this value can be removed for environments with normal sized disks (20 GB or larger)
      osdsPerDevice: "1" # this value can be overridden at the node or device level
    directories:
    - path: /var/lib/rook
``` 

Here we can configure values such as the mon number, which modules of the mgr will be enabled, which container image will be used when deploying the cluster etc. These configs will eventually be translated to Ceph command the operator runs against the pods created. Let's deploy the ceph cluster: 

```bash 
oc create -f cluster-test.yaml; sleep 300; oc get pods 
cephcluster.ceph.rook.io/rook-ceph created

NAME                                                           READY   STATUS        RESTARTS   AGE
csi-cephfsplugin-2n2kv                                         3/3     Running       0          4m6s
csi-cephfsplugin-provisioner-7b8fbf88b4-6mn4s                  4/4     Running       0          4m6s
csi-cephfsplugin-provisioner-7b8fbf88b4-mwnml                  4/4     Running       0          4m6s
csi-rbdplugin-5tw9d                                            3/3     Running       0          4m6s
csi-rbdplugin-provisioner-6b8b4d558c-4pf8m                     5/5     Running       0          4m6s
csi-rbdplugin-provisioner-6b8b4d558c-jv4tn                     5/5     Running       0          4m6s
rook-ceph-crashcollector-crc-w6th5-master-0-656cd7f7bd-rzxbh   0/1     Terminating   0          97s
rook-ceph-crashcollector-crc-w6th5-master-0-6d65cf5674-pg9b4   1/1     Running       0          48s
rook-ceph-mgr-a-76866c9f77-96g9s                               1/1     Running       0          97s
rook-ceph-mon-a-76bc8d997-8zrk9                                1/1     Running       0          116s
rook-ceph-operator-85ccdb9ffd-qfxpl                            1/1     Running       0          21m
rook-ceph-osd-0-64d6c74949-zj7sg                               1/1     Running       0          48s
rook-ceph-osd-prepare-crc-w6th5-master-0-9w6vd                 0/1     Completed     0          63s
rook-discover-f44rd                                            1/1     Running       0          20m
``` 

We can see we have the CSI plugins, used when dealing with block and file storage, the crash collector responsible for notifying the operator every time a crash happens, waiting for it to take action and deploy more of what got crashed. We have all the ceph cluster daemons such as mon, mgr, osd etc. Let's connect to our cluster by using the toolbox pod: 

```bash 
oc create -f toolbox.yaml 
deployment.apps/rook-ceph-tools created

oc exec -it <toolbox_pod_id> -- ceph -s
  cluster:
    id:     da9b732c-a7b0-4c03-903f-48b4f05b7073
    health: HEALTH_OK
 
  services:
    mon: 1 daemons, quorum a (age 9m)
    mgr: a(active, since 8m)
    osd: 1 osds: 1 up (since 8m), 1 in (since 8m)
 
  data:
    pools:   0 pools, 0 pgs
    objects: 0 objects, 0 B
    usage:   13 GiB used, 18 GiB / 30 GiB avail
    pgs:     
``` 

As you can see, we have a running ceph cluster created using rook. We have no pools, so in the following steps we will be creating object storage pools and an object storage user to access the S3 service. Let's take a look of the cephobjectsotre configuration: 

```bash 
cat object-test.yaml

apiVersion: ceph.rook.io/v1
kind: CephObjectStore
metadata:
  name: my-store
  namespace: rook-ceph
spec:
  metadataPool:
    replicated:
      size: 1
  dataPool:
    replicated:
      size: 1
  preservePoolsOnDelete: false
  gateway:
    type: s3
    port: 80
    securePort:
    instances: 1
``` 

We can control the data protection policy for our data and metadata pools using replica/erasure coding. In addition, we can control the number of rgw instances we will have after deployment, these instances will by load balanced by a service: 

```bash 
oc create -f object-test.yaml; sleep 120; oc get pods; oc get svc
cephobjectstore.ceph.rook.io/my-store created
NAME                                                           READY   STATUS      RESTARTS   AGE
csi-cephfsplugin-2n2kv                                         3/3     Running     0          18m
csi-cephfsplugin-provisioner-7b8fbf88b4-6mn4s                  4/4     Running     0          18m
csi-cephfsplugin-provisioner-7b8fbf88b4-mwnml                  4/4     Running     0          18m
csi-rbdplugin-5tw9d                                            3/3     Running     0          18m
csi-rbdplugin-provisioner-6b8b4d558c-4pf8m                     5/5     Running     0          18m
csi-rbdplugin-provisioner-6b8b4d558c-jv4tn                     5/5     Running     0          18m
rook-ceph-crashcollector-crc-w6th5-master-0-656cd7f7bd-dp4zq   1/1     Running     0          77s
rook-ceph-mgr-a-76866c9f77-96g9s                               1/1     Running     0          16m
rook-ceph-mon-a-76bc8d997-8zrk9                                1/1     Running     0          16m
rook-ceph-operator-85ccdb9ffd-qfxpl                            1/1     Running     0          36m
rook-ceph-osd-0-64d6c74949-zj7sg                               1/1     Running     0          15m
rook-ceph-osd-prepare-crc-w6th5-master-0-9w6vd                 0/1     Completed   0          15m
rook-ceph-rgw-my-store-a-5cfd4b88cd-vnwk6                      1/1     Running     0          77s
rook-ceph-tools-7d764c8647-lk87g                               1/1     Running     0          8m27s
rook-discover-f44rd                                            1/1     Running     0          35m
NAME                       TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)             AGE
csi-cephfsplugin-metrics   ClusterIP   172.30.141.80    <none>        8080/TCP,8081/TCP   18m
csi-rbdplugin-metrics      ClusterIP   172.30.100.213   <none>        8080/TCP,8081/TCP   18m
rook-ceph-mgr              ClusterIP   172.30.138.45    <none>        9283/TCP            15m
rook-ceph-mgr-dashboard    ClusterIP   172.30.39.164    <none>        8443/TCP            16m
rook-ceph-mon-a            ClusterIP   172.30.177.45    <none>        6789/TCP,3300/TCP   16m
rook-ceph-rgw-my-store     ClusterIP   172.30.107.125   <none>        80/TCP              2m
``` 
Here we see we have a rgw pod that was created, and a service routing traffic to the rgw pods, now let's expose the rgw service to enable outbound traffic to the relavant pods: 

```bash 
oc expose svc/rook-ceph-rgw-my-store 
route.route.openshift.io/rook-ceph-rgw-my-store exposed

oc get route
NAME                     HOST/PORT                                           PATH   SERVICES                 PORT   TERMINATION   WILDCARD
rook-ceph-rgw-my-store   rook-ceph-rgw-my-store-rook-ceph.apps-crc.testing          rook-ceph-rgw-my-store   http                 None
```

Now let's curl the hostname we have, to see if we get the rgw's url: 

```bash 
curl rook-ceph-rgw-my-store-rook-ceph.apps-crc.testing
<?xml version="1.0" encoding="UTF-8"?><ListAllMyBucketsResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Owner><ID>anonymous</ID><DisplayName></DisplayName></Owner><Buckets></Buckets></ListAllMyBucketsResult>
``` 

Now, let's create an objectstoreusre, and collect it's access and secret key. After getting the needed information we could start uploading objects to our s3 service: 

```bash 
oc create -f object-user.yaml
cephobjectstoreuser.ceph.rook.io/my-user created

export AWS_ACCESS_KEY_ID=`oc get secret rook-ceph-object-user-my-store-my-user -o 'jsonpath={.data.AccessKey}' | base64 --decode;echo`
export AWS_SECRET_ACCESS_KEY=`oc get secret rook-ceph-object-user-my-store-my-user -o 'jsonpath={.data.SecretKey}' | base64 --decode;echo`
```

After configuering credentials, let's try creating a bucket and upload few objects to it: 

```bash
aws s3 mb s3://test-s3 --endpoint-url http://rook-ceph-rgw-my-store-rook-ceph.apps-crc.testing
make_bucket: test-s3

for i in {1..10};do aws s3 cp /etc/hosts s3://test-s3/$i --endpoint-url http://rook-ceph-rgw-my-store-rook-ceph.apps-crc.testing;done
upload: ../../../../../../../etc/hosts to s3://test-s3/1          
upload: ../../../../../../../etc/hosts to s3://test-s3/2          
upload: ../../../../../../../etc/hosts to s3://test-s3/3          
upload: ../../../../../../../etc/hosts to s3://test-s3/4          
upload: ../../../../../../../etc/hosts to s3://test-s3/5          
upload: ../../../../../../../etc/hosts to s3://test-s3/6          
upload: ../../../../../../../etc/hosts to s3://test-s3/7          
upload: ../../../../../../../etc/hosts to s3://test-s3/8          
upload: ../../../../../../../etc/hosts to s3://test-s3/9          
upload: ../../../../../../../etc/hosts to s3://test-s3/10
``` 

As you see we have uploaded the objects into our bucket, Let's verify objects are really there: 

```bash 
aws s3 ls s3://test-s3 --endpoint-url http://rook-ceph-rgw-my-store-rook-ceph.apps-crc.testing
2020-03-17 13:10:38        136 1
2020-03-17 13:10:45        136 10
2020-03-17 13:10:39        136 2
2020-03-17 13:10:40        136 3
2020-03-17 13:10:40        136 4
2020-03-17 13:10:41        136 5
2020-03-17 13:10:42        136 6
2020-03-17 13:10:42        136 7
2020-03-17 13:10:43        136 8
2020-03-17 13:10:44        136 9
``` 

Now, Let's see how easy it is the scale out our service, please edit object-test.yaml file and replace 1 instances to 3:

```bash
oc apply -f object-test.yaml
cephobjectstore.ceph.rook.io/my-store configured

NAME                                                           READY   STATUS      RESTARTS   AGE
csi-cephfsplugin-2n2kv                                         3/3     Running     0          36m
csi-cephfsplugin-provisioner-7b8fbf88b4-6mn4s                  4/4     Running     0          36m
csi-cephfsplugin-provisioner-7b8fbf88b4-mwnml                  4/4     Running     0          36m
csi-rbdplugin-5tw9d                                            3/3     Running     0          36m
csi-rbdplugin-provisioner-6b8b4d558c-4pf8m                     5/5     Running     0          36m
csi-rbdplugin-provisioner-6b8b4d558c-jv4tn                     5/5     Running     0          36m
rook-ceph-crashcollector-crc-w6th5-master-0-656cd7f7bd-dp4zq   1/1     Running     0          18m
rook-ceph-mgr-a-76866c9f77-96g9s                               1/1     Running     0          33m
rook-ceph-mon-a-76bc8d997-8zrk9                                1/1     Running     0          34m
rook-ceph-operator-85ccdb9ffd-qfxpl                            1/1     Running     0          53m
rook-ceph-osd-0-64d6c74949-zj7sg                               1/1     Running     0          33m
rook-ceph-osd-prepare-crc-w6th5-master-0-9w6vd                 0/1     Completed   0          33m
rook-ceph-rgw-my-store-a-5cfd4b88cd-vnwk6                      1/1     Running     0          18m
rook-ceph-rgw-my-store-b-78897d8d58-q7b4l                      1/1     Running     0          31s
rook-ceph-rgw-my-store-c-6f69f948f4-5zwrt                      1/1     Running     0          26s
rook-ceph-tools-7d764c8647-lk87g                               1/1     Running     0          26m
rook-discover-f44rd                                            1/1     Running     0          52m
```
As you see we have now 3 rgw pods, let's verifiy the service routes to each one of them: 

```bash 
oc describe svc rook-ceph-rgw-my-store
Name:              rook-ceph-rgw-my-store
Namespace:         rook-ceph
Labels:            app=rook-ceph-rgw
                   ceph_daemon_id=my-store
                   rgw=my-store
                   rook_cluster=rook-ceph
                   rook_object_store=my-store
Annotations:       <none>
Selector:          app=rook-ceph-rgw,ceph_daemon_id=my-store,rgw=my-store,rook_cluster=rook-ceph,rook_object_store=my-store
Type:              ClusterIP
IP:                172.30.107.125
Port:              http  80/TCP
TargetPort:        80/TCP
Endpoints:         10.128.0.150:80,10.128.0.151:80,10.128.0.152:80
Session Affinity:  None
Events:            <none>
``` 

As you see, the service routs traffic to 3 different pods under Endpoints value, now we'll upload more objects and verify upload process wors well: 

```bash 
for i in {11..20};do aws s3 cp /etc/hosts s3://test-s3/$i --endpoint-url http://rook-ceph-rgw-my-store-rook-ceph.apps-crc.testing;done
upload: ../../../../../../../etc/hosts to s3://test-s3/11         
upload: ../../../../../../../etc/hosts to s3://test-s3/12         
upload: ../../../../../../../etc/hosts to s3://test-s3/13         
upload: ../../../../../../../etc/hosts to s3://test-s3/14         
upload: ../../../../../../../etc/hosts to s3://test-s3/15         
upload: ../../../../../../../etc/hosts to s3://test-s3/16         
upload: ../../../../../../../etc/hosts to s3://test-s3/17          
upload: ../../../../../../../etc/hosts to s3://test-s3/18          
upload: ../../../../../../../etc/hosts to s3://test-s3/19         
upload: ../../../../../../../etc/hosts to s3://test-s3/20
``` 
Now let's verify objects are really there: 

```bash 
aws s3 ls s3://test-s3 --endpoint-url http://rook-ceph-rgw-my-store-rook-ceph.apps-crc.testing
2020-03-17 13:10:38        136 1
2020-03-17 13:10:45        136 10
2020-03-17 13:17:44        136 11
2020-03-17 13:17:44        136 12
2020-03-17 13:17:45        136 13
2020-03-17 13:17:46        136 14
2020-03-17 13:17:47        136 15
2020-03-17 13:17:47        136 16
2020-03-17 13:17:48        136 17
2020-03-17 13:17:49        136 18
2020-03-17 13:17:49        136 19
2020-03-17 13:10:39        136 2
2020-03-17 13:17:50        136 20
2020-03-17 13:10:40        136 3
2020-03-17 13:10:40        136 4
2020-03-17 13:10:41        136 5
2020-03-17 13:10:42        136 6
2020-03-17 13:10:42        136 7
2020-03-17 13:10:43        136 8
2020-03-17 13:10:44        136 9
```

## Conclusion 

We saw how we can provide a containerized S3 object storage service running on container orchestration environments such as Openshift and Kubernetes. The ability of managing cephclusters as openshift objectives makes ceph deloyments very easy and intuitive, It helps Devops/Software engineers to speak in the same language and prevents the extra knowledge preservation. We also saw how wasy it is to scale our S3 frontends which makes our infrastructure far more flexible. Later on, we will talk about other features with the new version of Openshift4.X such as Bucket Provisioning, Noobaa management and more. 

