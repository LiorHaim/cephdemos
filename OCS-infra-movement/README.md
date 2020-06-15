# Persist you Openshift infrastructure using OCS

As the world adopts the data-centric approach and people get more familiar with Kubernetes as an end-to-end platform for their application lifecycle, the need for persistenct arises. By default containers are stateless, which means that they don't save any state and treat the data as ephemeral. To solve this problem in Kuberenets, storage classes are being used. With storage classes, we have a storage provider (whether it's block, file or object storage) that Kubernetes can access to save the information that is being used by the containers in a volume. This volume is being attached to the container at runtime and ensures that the container will get the written data even if it fails, this volume is used dynamically and is being refered as a Kubernetes object called PersistentVolume (PV). To use a PV we should create a PersistentVolumeCliam (PVC) which tells Kuberenetes what storage class we want to use and what is the volume's capacity and refer to it when creating the application's deployment. 

When running Openshift on premise or in the cloud, we might have legacy applications using file storage, databases using block storage and archival applications using object storage. This requires using some complex architectures when being on premise that contain dedicated storage solutions. We can solve this issue by using the cloud's storage services, but most of them are not persistent when it comes to multi-region deployments and will require some extra application replication mechanism when using persistent volumes. 

To solve those problems, we could use Openshift Container Storage to provide a unified storage solution to our Openshift cluster which is also topology agnostic. OCS is part of the Openshift cluster (mostly dedicated storage nodes beinf use as worker nodes to schedule OCS's pods) and we can treat it as we treat any Openshift application, and deploy it with the OCS Operator. 

Now that we have understood how OCS can help use reaching our business goals, let's see how we could move our entire Openshift infrastrcutre (that of course requires storage) to OCS. 

## Prerequisites

* A running Openshift cluster 
* 32vCPU, 32GRAM worker machines with 10GB, 100GB disks attached
* 8vCPU, 16GRAM master machines 


First let's take a look on our nodes: 

```bash 
$ oc get nodes 
                                                                                                                           
NAME                                                     STATUS   ROLES    AGE   VERSION
ocp4-dfr7m-m-0.us-east1-b.c.shon-267911.internal         Ready    master   32m   v1.17.1
ocp4-dfr7m-m-1.us-east1-c.c.shon-267911.internal         Ready    master   32m   v1.17.1
ocp4-dfr7m-m-2.us-east1-d.c.shon-267911.internal         Ready    master   32m   v1.17.1
ocp4-dfr7m-w-b-8skcr.us-east1-b.c.shon-267911.internal   Ready    worker   17m   v1.17.1
ocp4-dfr7m-w-c-78ckk.us-east1-c.c.shon-267911.internal   Ready    worker   16m   v1.17.1
ocp4-dfr7m-w-d-tdt2t.us-east1-d.c.shon-267911.internal   Ready    worker   16m   v1.17.1
```

To start using OCS, we will use the Local Storage Operator to expose the attached disks as PVs so that OCS could use them for the Ceph cluster being deployed when we create the OCS cluster. 
To do so, let's debug the RHCOS node to enter the shell: 

```bash 
$ oc debug node/ocp4-dfr7m-w-d-tdt2t.us-east1-d.c.shon-267911.internal
```

It is important to do so for every node to make sure we don't have misalignment with the disk labels when using different nodes: 

```bash
$ lsblk -l 

NAME MAJ:MIN RM   SIZE RO TYPE MOUNTPOINT
sdb    8:16   0   100G  0 disk 
sdc    8:32   0    10G  0 disk
```
We see that we have 2 disks, one in 100GB size (will be used as block for the Ceph cluster OSDSs) and the other is 10GB size (will bw used as filesystem for the mon shared folder).
Let's start using the LSO (Local Storage Operator), we'll create a new project:

```bash
$ oc new-project local-storage
```

########################3 Install the LSO PIC 


After we have installed the LSO, we can create a CR that will eventually create two local StorageClasses from out attached disks. The LSO will take all the 100GB disks and will create a `localblock` storage class for the Ceph cluster OSDs. In addition, it will take the 10GB disks and will create a localfile storage class for the mons shared folder:

```bash
$ oc create -f - <<EOF
apiVersion: local.storage.openshift.io/v1
kind: LocalVolume
metadata:
  name: block
  namespace: local-storage
spec:
  storageClassDevices:
    - devicePaths:
        - /dev/sdb
      storageClassName: localblock
      volumeMode: Block
---
apiVersion: local.storage.openshift.io/v1
kind: LocalVolume
metadata:
  name: file
  namespace: local-storage
spec:
  storageClassDevices:
    - devicePaths:
        - /dev/sdc
      fsType: ext4
      storageClassName: localfile
      volumeMode: Filesystem
EOF
```

Let's verify that after creating the CR those PVs were indeed created: 

```bash 
$ oc get pv 
                                                                                                                               
NAME                CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS      CLAIM   STORAGECLASS   REASON   AGE
local-pv-16b6c950   10Gi       RWO            Delete           Available           localfile               21s
local-pv-6b4479d1   10Gi       RWO            Delete           Available           localfile               5s
local-pv-7762888c   100Gi      RWO            Delete           Available           localblock              21s
local-pv-95131a3a   10Gi       RWO            Delete           Available           localfile               10s
local-pv-e3b0abcb   100Gi      RWO            Delete           Available           localblock              5s
local-pv-f760eea2   100Gi      RWO            Delete           Available           localblock              10s
```

And let's verify that the StorageClasses were created using those PVs: 

```bash
$ oc get sc
                                                                                                                                 
NAME                 PROVISIONER                    RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
localblock           kubernetes.io/no-provisioner   Delete          WaitForFirstConsumer   false                  66s
localfile            kubernetes.io/no-provisioner   Delete          WaitForFirstConsumer   false                  63s
```

Now after we have the LSO StorageClasses ready for the OCS cluster deployment, let's label our nodes to mark them as storage nodes so that the OCS operator will know that it should use them only when scheduling the OCS cluster pods: 

```bash 
$ for i in `oc get nodes | grep worker | awk '{print $1}'`;do oc label node $i cluster.ocs.openshift.io/openshift-storage=;done
```
########################## Install OCS Operator PIC

After we have installed the OCS operator, let's change our project to see that all the needed pods were created successfully: 

```bash
$ oc project openshift-storage
```
To get the pods: 

```bash
$ oc get pods
                                                                                                                              
NAME                                      READY   STATUS    RESTARTS   AGE
lib-bucket-provisioner-8477b8b86f-mgtn8   1/1     Running   0          108s
noobaa-operator-846d74bc9c-jdvcx          1/1     Running   0          93s
ocs-operator-595dbb7469-sngk6             1/1     Running   0          93s
rook-ceph-operator-548b74ccf8-vn54t       1/1     Running   0          93s
```

Now that we have our operator running, let's create our OCS cluster. To do so, we will create a CR that will describe which StorageClasses OCS should use when creating the Ceph cluster: 

```bash 
$ oc create -f - <<EOF
apiVersion: ocs.openshift.io/v1
kind: StorageCluster
metadata:
  name: ocs-storagecluster
  namespace: openshift-storage
spec:
  manageNodes: false
  monPVCTemplate:
    spec:
      accessModes:
      - ReadWriteOnce
      resources:
        requests:
          storage: 10Gi
      storageClassName: localfile
      volumeMode: Filesystem
  storageDeviceSets:
  - count: 1
    dataPVCTemplate:
      spec:
        accessModes:
        - ReadWriteOnce
        resources:
          requests:
            storage: 1
        storageClassName: localblock
        volumeMode: Block
    name: ocs-deviceset
    placement: {}
    portable: false
    replica: 3
    resources: {}
EOF
```

As you see we tell OCS to use the 10GB disks for the mons, and the 100Gb disks for the OSD data. OCS will search for those StorageClasses and will consume the data that is actually taken from our attached disks behind the scenes.
Let's verify that all our pods were created successfully: 

```bash 
$ oc get pods
                                                                                                                            
NAME                                                              READY   STATUS      RESTARTS   AGE
csi-cephfsplugin-2clqn                                            3/3     Running     0          16m
csi-cephfsplugin-7ntnr                                            3/3     Running     0          16m
csi-cephfsplugin-nrxvt                                            3/3     Running     0          16m
csi-cephfsplugin-provisioner-d8cf4499f-jtx57                      5/5     Running     0          16m
csi-cephfsplugin-provisioner-d8cf4499f-sf7jl                      5/5     Running     0          16m
csi-rbdplugin-84669                                               3/3     Running     0          16m
csi-rbdplugin-89gms                                               3/3     Running     0          16m
csi-rbdplugin-8p2n7                                               3/3     Running     0          16m
csi-rbdplugin-provisioner-66bdc74b4-bqsks                         5/5     Running     0          16m
csi-rbdplugin-provisioner-66bdc74b4-r945p                         5/5     Running     0          16m
lib-bucket-provisioner-8477b8b86f-mgtn8                           1/1     Running     0          18m
noobaa-core-0                                                     1/1     Running     0          11m
noobaa-db-0                                                       1/1     Running     0          11m
noobaa-endpoint-6bb4557c85-hpdnl                                  1/1     Running     0          10m
noobaa-operator-846d74bc9c-jdvcx                                  1/1     Running     0          18m
ocs-operator-595dbb7469-sngk6                                     1/1     Running     0          18m
rook-ceph-crashcollector-04d1d4916d1a4bfddbf181e23a6d4351-vglqb   1/1     Running     0          14m
rook-ceph-crashcollector-8919344c9d7e83d5c1ca0340889749e2-nsjz9   1/1     Running     0          15m
rook-ceph-crashcollector-bf97b9f9d94b5a90d86af7d056162c57-4l8tn   1/1     Running     0          14m
rook-ceph-drain-canary-04d1d4916d1a4bfddbf181e23a6d4351-54j8cn6   1/1     Running     0          11m
rook-ceph-drain-canary-8919344c9d7e83d5c1ca0340889749e2-75g8cpx   1/1     Running     0          11m
rook-ceph-drain-canary-bf97b9f9d94b5a90d86af7d056162c57-5blr5xg   1/1     Running     0          11m
rook-ceph-mds-ocs-storagecluster-cephfilesystem-a-d9d65cfc5bjrv   1/1     Running     0          11m
rook-ceph-mds-ocs-storagecluster-cephfilesystem-b-54566dc48prnc   1/1     Running     0          11m
rook-ceph-mgr-a-79c956f9d4-spk5k                                  1/1     Running     0          12m
rook-ceph-mon-a-6b96d7d9f7-x9xf6                                  1/1     Running     0          15m
rook-ceph-mon-b-5774b466f8-r55f7                                  1/1     Running     0          14m
rook-ceph-mon-c-b7f694cfc-f8nmw                                   1/1     Running     0          14m
rook-ceph-operator-548b74ccf8-vn54t                               1/1     Running     0          18m
rook-ceph-osd-0-74579568bf-cq466                                  1/1     Running     0          11m
rook-ceph-osd-1-55fd755b7d-zz8jw                                  1/1     Running     0          11m
rook-ceph-osd-2-66cf4cc457-sdj6s                                  1/1     Running     0          11m
rook-ceph-osd-prepare-ocs-deviceset-0-0-wnjhr-pgj9w               0/1     Completed   0          12m
rook-ceph-osd-prepare-ocs-deviceset-1-0-kq4l7-njmjw               0/1     Completed   0          12m
rook-ceph-osd-prepare-ocs-deviceset-2-0-mqxdn-mbkz5               0/1     Completed   0          12m
rook-ceph-rgw-ocs-storagecluster-cephobjectstore-a-6f85586z6whs   1/1     Running     0          11m
```

As you see the OCS operator has deployed the Ceph cluster pods, the noobaa pods and all the CSI pods required for the OCS cluster to function. 
Let's verify that the OCS StroageClasses were created that are coming from our Ceph cluster: 

```bash 
$ oc get sc
                                                                                                                                
NAME                          PROVISIONER                             RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
localblock                    kubernetes.io/no-provisioner            Delete          WaitForFirstConsumer   false                  21m
localfile                     kubernetes.io/no-provisioner            Delete          WaitForFirstConsumer   false                  21m
ocs-storagecluster-ceph-rbd   openshift-storage.rbd.csi.ceph.com      Delete          Immediate              false                  16m
ocs-storagecluster-cephfs     openshift-storage.cephfs.csi.ceph.com   Delete          Immediate              false                  16m
openshift-storage.noobaa.io   openshift-storage.noobaa.io/obc         Delete          Immediate              false                  11m
```

Great! we have all of out storage classes - RBD for block, CephFS for filesystem and Noobaa for object storage. Now we can start migrating our infrastrcture to OCS!

First, we'll migrate the image registry that is being used locally by Openshift to save the container images (for faster build and deployments), for this component we'll use file storage (we could use object storage too, but this is out of scope). 
Let's change the project to the registry project: 

```bash 
$ oc project openshift-image-registry
```

Let's create a PVC for the image registry volume: 

```bash 
$ oc create -f - <<EOF
apiVersion: "v1"
kind: "PersistentVolumeClaim"
metadata:
  name: "registry-pvc"
spec:
  accessModes:
    - "ReadWriteMany"
  resources:
    requests:
      storage: "20Gi"
  storageClassName: "ocs-storagecluster-cephfs"
EOF
``` 

As you see this volume will come from `ocs-storagecluster-cephfs` which is actually the file storage class from our OCS cluster. 
Let;'s verify that the PVC is valid and bounded:

```bash
$ oc get pvc | grep registry
  
NAME           STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS                AGE
registry-pvc   Bound    pvc-45fb864d-ec02-4714-8c82-9241760f1f71   20Gi       RWX            ocs-storagecluster-cephfs   5s
```

Now let's edit the deployment to change the emptyDir that is being used by the registry to a persistent volume that is coming from our OCS cluster: 

``` bash
$ oc edit configs.imageregistry.operator.openshift.io

storage:
  pvc:
    claim: registry-pvc 
```

Now let's verify that the registry is indeed using the created volume: 

``` bash
oc get pv | grep image                                                                                                                  
pvc-45fb864d-ec02-4714-8c82-9241760f1f71   20Gi       RWX            Delete           Bound       openshift-image-registry/registry-pvc       ocs-storagecluster-cephfs              8m9s
```

Great, next we will create a cluster logging instance that will create an entire EFK stack with one CR, to do so we'll use the Cluster Logging Operator: 

######### Install ES 
######## Install CLO 

Now that we have our operators installed, let's create our cluster logging instance, the Elasticsearch pods will use block storage volumes that are being taken from the OCS cluster:

```bash 
$ oc create -f - <<EOF
apiVersion: logging.openshift.io/v1
kind: ClusterLogging
metadata:
  name: instance
  namespace: openshift-logging
spec:
  managementState: Managed
  logStore:
    type: elasticsearch
    elasticsearch:
      nodeCount: 3
      resources: 
        limits: 
          memory: 4Gi
        requests: 
          memory: 4Gi
          cpu: 500m 
      redundancyPolicy: SingleRedundancy
      storage:
        storageClassName: ocs-storagecluster-ceph-rbd
        size: 30G
  visualization:
    type: kibana
    kibana:
      replicas: 1
  curation:
    type: curator
    curator:
      schedule: 30 3 * * *
  collection:
    logs:
      type: fluentd
      fluentd: {}
EOF
```

Now let's verify that our pods are running and healthy: 

```bash 
$ oc get pods -n openshift-logging
                                                                                                         
NAME                                           READY   STATUS    RESTARTS   AGE
cluster-logging-operator-5b785cb476-ph4r5      1/1     Running   0          3m59s
elasticsearch-cdm-e14pdhqk-1-8dffcdff7-w2sx5   2/2     Running   0          93s
elasticsearch-cdm-e14pdhqk-2-58847f6b8-fngfz   2/2     Running   0          88s
elasticsearch-cdm-e14pdhqk-3-5f5b59748-fp5kr   2/2     Running   0          56s
fluentd-9k8lg                                  1/1     Running   0          90s
fluentd-b7t7n                                  1/1     Running   0          90s
fluentd-q9j5f                                  1/1     Running   0          90s
fluentd-qkl65                                  1/1     Running   0          90s
fluentd-sbk2s                                  1/1     Running   0          90s
fluentd-zpr5r                                  1/1     Running   0          90s
kibana-79644d9484-dstd5                        2/2     Running   0          92s
```

Let's verify Elasticsearch is indeed using the created volumes: 

```bash 

$ oc get pv | grep elastic
                                                                                                                 
pvc-16a95703-e26d-40b9-b837-c7352ec2ae9b   28Gi       RWO            Delete           Bound       openshift-logging/elasticsearch-elasticsearch-cdm-e14pdhqk-2   ocs-storagecluster-ceph-rbd            4m
pvc-5742d026-0e01-4feb-afef-a2872e3e4441   28Gi       RWO            Delete           Bound       openshift-logging/elasticsearch-elasticsearch-cdm-e14pdhqk-3   ocs-storagecluster-ceph-rbd            4m
pvc-6f22d8ca-3c92-4115-8aae-885d005634d2   28Gi       RWO            Delete           Bound       openshift-logging/elasticsearch-elasticsearch-cdm-e14pdhqk-1   ocs-storagecluster-ceph-rbd
```

################## ES PIC 

Great, now that we have our EFK using OCS let's move to our last component, the cluster monitoring. Here we will tell the Prometheus and Alertmanager databases to use ceph RBD as a persistenct backing volume. 
To do so, we will create a configMap object that will re-deploy our pods to use the created RBD volumes:

```bash 
$ oc create -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-monitoring-config
  namespace: openshift-monitoring
data:
  config.yaml: |
    prometheusK8s:
      volumeClaimTemplate:
        metadata:
          name: prometheusdb
        spec:
          storageClassName: ocs-storagecluster-ceph-rbd
          resources:
            requests:
              storage: 20Gi
    alertmanagerMain:
      volumeClaimTemplate:
        metadata:
          name: alertmanager
        spec:
          storageClassName: ocs-storagecluster-ceph-rbd
          resources:
            requests:
              storage: 20Gi
EOF
```

Noe let's verify that our pods are indeed using the created volumes: 

```bash 
$ oc get pvc -n openshift-monitoring

NAME                                       STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS                  AGE
alertmanager-main-db-alertmanager-main-0   Bound    pvc-13cc4a26-66b9-41cf-a210-0574ae9eb9d0   20Gi       RWO            ocs-storagecluster-ceph-rbd   40s
alertmanager-main-db-alertmanager-main-1   Bound    pvc-8b118f46-4ab2-464a-8b2a-c0f0405dc9e6   20Gi       RWO            ocs-storagecluster-ceph-rbd   40s
alertmanager-main-db-alertmanager-main-2   Bound    pvc-4d44f938-53cf-491e-9178-5cac1fa78bf9   20Gi       RWO            ocs-storagecluster-ceph-rbd   40s
prometheus-k8s-db-prometheus-k8s-0         Bound    pvc-c2256ef6-2e85-4a70-8590-b408270abbdc   20Gi       RWO            ocs-storagecluster-ceph-rbd   30s
prometheus-k8s-db-prometheus-k8s-1         Bound    pvc-9c8a3bd7-7feb-400f-9f1a-aaee391af44c   20Gi       RWO            ocs-storagecluster-ceph-rbd   30s
```

############# Grafana PIC 

## Conclusion 

We saw how we could use the OCS cluster to move our entire infrastructure to consume storage capacity from our OCS cluster, OCS is very easy to deploy and does not require any additional knowledge preserving and takes the advantege of operators to deploy the data layer. 
Due to it's simplicity, OCS can help you reaching your business goals as a all-in-one storage solution for your containerized applications, more on the next chapters of OCS. 
Hope you have enjoyed this Demo, until the next time :) 

