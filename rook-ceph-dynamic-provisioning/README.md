## Use rook-ceph to create Dynamic Provisioned PVCs using Openshift 

As we all know, Kubernetes offers the ability of running multiple workloads in an available, durable and consistent manner. These workloads are defined as loosly-coupled microservices, which are one or more containers gathered into one single entity called a "Pod". This Pod can act as Stateful or Stateless application, which mainly tell if the Pod needs it's data to be saved or not. In a Stateless approach, handeling failure is quite easy - the Pod is created from a container image and has no state to preserve, so it could be easily re-deployed. The challenge occures when the data beneath the Pod needs to be saved in order for the application to function (for example, database, message broker, storage system etc). This is why Kubernetes offers Persistent Volumes, which will will save the container's data in case the container runtime fails. These PVs are backed up by Persistent Volume Claims that will claim the amount of storage resources the Pod needs. Those PVs will intergrate with various cloud providers and storage systems in order to fulfill the PVC request. PVCs can be accessed via RWO (block storage, for io intensive workloads) or RWX (file storage, for CI/CD, web servers) where in RWX the volume can be shared across a few containers in a Pod (or even a few different pods) and RWO is dedicated to a single Pod. Kuberenetes offers the ability of creating an object called "Storage Class" refers to the created storage system and access type. PVs are attached from the created storage class and mounted into the the pod that has claimed for the storage capacity. In that way, storage capacity can be Dynamically provisioned out of the created storage class. In this publication we will see how we can use rook-ceph to create a Block and a File storage classes, claim PVCs and attach the created PVs into pods. 

# Prerequisites 
* A running Openshift cluster (version 4.3.8) 
* A cloned rook git repository (version 1.2) 
* Switch project context into rook-ceph 

# Installation 

We'll start from the Block storge, let's cd to the wanted directory: 
```bash 
cd rook/cluster/examples/kubernetes/ceph/csi/rbd
```

After getting into the directory, we'll see we have a storageclass.yaml file, let's understand what is means: 
```bash 
oc create -f - <<EOF
apiVersion: ceph.rook.io/v1
kind: CephBlockPool
metadata:
  name: replicapool
  namespace: rook-ceph
spec:
  failureDomain: host
  replicated:
    size: 3
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
   name: rook-ceph-block
provisioner: rook-ceph.rbd.csi.ceph.com
parameters:
    clusterID: rook-ceph

    pool: replicapool

    imageFormat: "2"

    imageFeatures: layering

    csi.storage.k8s.io/provisioner-secret-name: rook-csi-rbd-provisioner
    csi.storage.k8s.io/provisioner-secret-namespace: rook-ceph
    csi.storage.k8s.io/controller-expand-secret-name: rook-csi-rbd-provisioner
    csi.storage.k8s.io/controller-expand-secret-namespace: rook-ceph
    csi.storage.k8s.io/node-stage-secret-name: rook-csi-rbd-node
    csi.storage.k8s.io/node-stage-secret-namespace: rook-ceph
    csi.storage.k8s.io/fstype: ext4
allowVolumeExpansion: true
reclaimPolicy: Delete
EOF
```

So we see we have to CRDs being created, where the first one is from type CephBlockPool which will immediately create an rbd pool in our Ceph cluster. This pool will have 3 replicas in a host failure domains. in our case is will store data across 3 OSD pods. 
The second CRD that is being defined is the Storage Class, which refers to the CephBlockPool we have created in the previous CRD. This storage class will create an ext4 volumes, allow expantion of volumes and will reclaim the space in case an attached PV will be deleted. 

Now let's create those CRDs and veirfy all is set up as expected, first we'll verify the CephBlockPool creation:
```bash 
oc get cephblockpool

NAME          AGE
replicapool   16s
```

Now let's veirfy the storage class has been succesfully created: 
```bash 
oc get sc

NAME              PROVISIONER                  AGE
rook-ceph-block   rook-ceph.rbd.csi.ceph.com   42s
```

After we have both CRDs set up, let's create a PVC that will be taken from the created storage class: 
```bash 
oc create -f - <<EOF
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: rbd-pvc
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: rook-ceph-block
EOF
```

As you see we will create a PVC called rbd-pvc that will claim for a 1GB volume out of our CephBlockPool, let's create it and verify it's in bound state: 
```bash
oc get pvc

NAME      STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS      AGE
rbd-pvc   Bound    pvc-22621777-c30c-43eb-b3e3-501a0b68ef8f   1Gi        RWO            rook-ceph-block   4s
```

As you see the type is in RWO access method.
Now that we have all set up, let's move into the pod creation. The pod will mount the created PV into a fixed mount path given in the deployment defintion: 
```bash 
oc create -f - <<EOF
---
apiVersion: v1
kind: Pod
metadata:
  name: csirbd-demo-pod
spec:
  containers:
   - name: web-server
     image: nginx
     volumeMounts:
       - name: mypvc
         mountPath: /var/lib/www/html
  volumes:
   - name: mypvc
     persistentVolumeClaim:
       claimName: rbd-pvc
       readOnly: false
EOF
```

The pod will be called as csirbd-demo-pod and will use the rbd-pvc created as a volume that will be mounted into /var/lib/www/html path on the container. 
Now let's verify the pod actually mounted the created PV:

```bash
# Verify pod has mounted the correct mount path 
oc rsh csirbd-demo-pod lsblk -l | grep rbd0

rbd0                     251:0    0    1G  0 disk /var/lib/www/html

# Verify the filesystem is ext as excpected 
oc rsh csirbd-demo-pod stat -f /var/lib/www/html

  File: "/var/lib/www/html"
    ID: 34bb1b46e83fe8e2 Namelen: 255     Type: ext2/ext3
Block size: 4096       Fundamental block size: 4096
Blocks: Total: 249830     Free: 249189     Available: 245093
Inodes: Total: 65536      Free: 65525

```

As you see, we have the PV in size 1GB mounted into the wanted directory, which uses ans ext filesystem. 

Now let's move on to the file storage part, change the directory to the right directory:
```bash 
cd ../cephfs
```

In this directory as before, we have the storage class definition located in storageclass.yaml file:
```bash 
oc create -f - <<EOF
apiVersion: ceph.rook.io/v1
kind: CephFilesystem
metadata:
  name: myfs
  namespace: rook-ceph
spec:
  metadataPool:
    failureDomain: host
    replicated:
      size: 3
  dataPools:
    - failureDomain: host
      replicated:
        size: 3
  preservePoolsOnDelete: true
  metadataServer:
    activeCount: 1
    activeStandby: true
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: csi-cephfs
provisioner: rook-ceph.cephfs.csi.ceph.com
parameters:
  clusterID: rook-ceph

  fsName: myfs

  pool: myfs-data0


  csi.storage.k8s.io/provisioner-secret-name: rook-csi-cephfs-provisioner
  csi.storage.k8s.io/provisioner-secret-namespace: rook-ceph
  csi.storage.k8s.io/controller-expand-secret-name: rook-csi-cephfs-provisioner
  csi.storage.k8s.io/controller-expand-secret-namespace: rook-ceph
  csi.storage.k8s.io/node-stage-secret-name: rook-csi-cephfs-node
  csi.storage.k8s.io/node-stage-secret-namespace: rook-ceph

reclaimPolicy: Delete
allowVolumeExpansion: true
mountOptions:
EOF
```

In here also, we have a CephFilesystem CRD that will be deployed with myfs name, that will create a metadata and data pools in our created Ceph cluster. Those pools will be created as before, in replica factor of 3 in a host failure domain. In addition, the deployment will provision 1 MDS server that will handle the file lookups, 
The deployments also contains the StorageClass definition itself which refers to our created CephFilesystem pools. 

Now let's verify we have our pools created in the Ceph cluster **you could create a toolboox with oc create -f toolbox.yaml command**:
```bash 
# use the created toolbox pod to verify cephfilesystem status
oc rsh <tools-...> ceph fs status

myfs - 0 clients
====
+------+----------------+--------+---------------+-------+-------+
| Rank |     State      |  MDS   |    Activity   |  dns  |  inos |
+------+----------------+--------+---------------+-------+-------+
|  0   |     active     | myfs-a | Reqs:    0 /s |   10  |   13  |
| 0-s  | standby-replay | myfs-b | Evts:    0 /s |    0  |    3  |
+------+----------------+--------+---------------+-------+-------+
+---------------+----------+-------+-------+
|      Pool     |   type   |  used | avail |
+---------------+----------+-------+-------+
| myfs-metadata | metadata | 2286  | 13.7G |
|   myfs-data0  |   data   |    0  | 13.7G |
+---------------+----------+-------+-------+
+-------------+
| Standby MDS |
+-------------+
+-------------+

# Check the filesystem out of ocp cluster
oc get cephfilesystem

NAME   ACTIVEMDS   AGE
myfs   1           114s

```
Now we see we have our pools and our CephFilesystem in active state, now Let's verify the storage class end up right: 
```bash 
oc get sc 

NAME              PROVISIONER                     AGE
csi-cephfs        rook-ceph.cephfs.csi.ceph.com   2m11s
rook-ceph-block   rook-ceph.rbd.csi.ceph.com      7m18s
```

We see we have another storage class that has been created, now let's verify the pvc.yaml defintion: 
```bash 
oc create -f - <<EOF 
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: cephfs-pvc
spec:
  accessModes:
  - ReadWriteMany
  resources:
    requests:
      storage: 1Gi
  storageClassName: csi-cephfs
EOF
```

As in the block deployment, we have a PVC called cephfs-pvc in access mode RWO that requests for 1GB from out cephfs pools, let's create it and verify it's in bound state: 
```bash 
oc get pvc

NAME         STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS      AGE
cephfs-pvc   Bound    pvc-2af9d295-27f5-4b54-8054-e658fa8b7303   1Gi        RWX            csi-cephfs        4s
rbd-pvc      Bound    pvc-22621777-c30c-43eb-b3e3-501a0b68ef8f   1Gi        RWO            rook-ceph-block   7m31s
```

After we have all set up, let's create two pods that will share the PV created and mount it to the same mount path in the container:

```bash 
oc create -f - <<EOF 
---
apiVersion: v1
kind: Pod
metadata:
  name: csicephfs-demo-pod-a
spec:
  containers:
   - name: web-server-a
     image: nginx
     volumeMounts:
       - name: mypvc
         mountPath: /var/lib/www/html
  volumes:
   - name: mypvc
     persistentVolumeClaim:
       claimName: cephfs-pvc
       readOnly: false
---
apiVersion: v1
kind: Pod
metadata:
  name: csicephfs-demo-pod-b
spec:
  containers:
   - name: web-server-b
     image: nginx
     volumeMounts:
       - name: mypvc
         mountPath: /var/lib/www/html
  volumes:
   - name: mypvc
     persistentVolumeClaim:
       claimName: cephfs-pvc
       readOnly: false
EOF
``` 
These two pods will use cephfs-pvc and mount the created 1GB PV into /var/lib/www/html, let's verify that: 
```bash 
# Verify both pod-a and pod-b have 1GB volume mapped into /var/lib/www/html
oc rsh csicephfs-demo-pod-a df -h | grep /var/lib/www/html
172.30.13.52:6789:/volumes/csi/csi-vol-366a69db-7dd0-11ea-9dce-0a580a800066  1.0G     0  1.0G   0% /var/lib/www/html

oc rsh csicephfs-demo-pod-b df -h | grep /var/lib/www/html
172.30.13.52:6789:/volumes/csi/csi-vol-366a69db-7dd0-11ea-9dce-0a580a800066  1.0G     0  1.0G   0% /var/lib/www/html

# Create a file called test in the shared volume
oc rsh csicephfs-demo-pod-a touch /var/lib/www/html/test

# Verify the file was created in pod-b too
oc rsh csicephfs-demo-pod-b ls -l /var/lib/www/html
total 0
-rw-r--r-- 1 root root 0 Apr 13 21:50 test
```

As you see, we have both pods sharing the same 1GB size volume which came from our file storage class. 

# Conclustion 

We saw that creating storage classes out of out rook-ceph cluster is quite easy and doesn't require any extra configuration except creating few CRDs. This approach eases the process of storage consumption in Stateful applications, providing us the ability of consuming dynamic data across multiple pods and namespaces. Hope you have enjoyed the demo, have fun :)


