# Aggregate Openshift logs using the Cluster Logging Operator and EFK stack

Today, when running Kubernetes in production, we are sometimes having a hard time in collecting the logs from our cluster components. eventually it ends up with using custom made solutions that doesn't provide the wanted user experience. To solve this problem, we can use the Cluster Logging Operator provided by Red Hat as out of the box solution for Openshift Container Platform. The CLO, will deploy a whole Elastisearch->Fluentd->Kibana stack that will collect logs from our cluster components automatically. The logs will be stored in a logStore (in our case Elasticsearch), collected by Fluend (in our case is the log shipper) and visualized by Kibana (in our case the visualizer). 

Each one of the Fluend pods will run as a DaemonSet (which means will run on each node in the cluster) and each Daemon will collect the logs relevant to the host it was deployed on. Logs will be sent to Elasticsearch through a secure connection and will eventually be visualized in Kibana. The CLO will also provide a Curator that will run as a Job and will perform deletion of the indexes, so that we won't have performance problems when the index gets too beefy, all are configurable through a Custom Resource called `ClusterLogging` CR. 

When Deploying EFK, we will sometimes want to use local storage (DAS) from performance prespective instead of using central storage systems over the network. Let's move on the steps of using the CLO with local storage in Openshift: 


For the sake of this demo, we will use the `Local Storage Operator` which is actually an operator responsbile for creating a local StorageClass so that pods will be able to use the host's local capacity. 

Let's create a project for the cluster operator: 

```bash
$ oc new-project local-storage
```

After we have created the project, let's login to the Openshift UI and install the LSO from the `Operator Hub`: 

## Install LSO  

I have attached 50Gi disks for each one of my worker nodes, I've used `oc debug node/<node>` to verify what device name the attached disk got. Each node has the attached disk as `/dev/sdb`.
So after the installation, we can create the LocalVolume which automatically create 3 PVs (one for each disk) and will aggregate those PVs into one StorageClass called local. 

```bash
apiVersion: local.storage.openshift.io/v1
kind: LocalVolume
metadata:
  name: lv
  namespace: local-storage
spec:
  storageClassDevices:
    - devicePaths:
        - /dev/sdb
      fsType: ext4
      storageClassName: local
      volumeMode: Filesystem
```

Let's verify the PVs were created: 

```bash
$ oc get pv
                                                                                                                                
NAME                CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS      CLAIM   STORAGECLASS   REASON   AGE
local-pv-2fa7c312   50Gi       RWO            Delete           Available           localblock              15s
local-pv-66304f00   50Gi       RWO            Delete           Available           localblock              15s
local-pv-9a6f7b5c   50Gi       RWO            Delete           Available           localblock              16s
```

Now let's see that the StorageClass was created too: 

```bash
$ oc get sc
                                                                                                                                 
NAME                 PROVISIONER                    RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
local                kubernetes.io/no-provisioner   Delete          WaitForFirstConsumer   false                  38s
standard (default)   kubernetes.io/gce-pd           Delete          WaitForFirstConsumer   true                   117m
```

Now we'll turn the local StorageClass into the default one, to do so: 

```bash 
$ oc patch storageclass local -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
$ oc patch storageclass standard -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}'
```

We'll run the command again to verify that this is indeed the default one: 

```bash
$ oc get sc
                                                                                                                                 
NAME                   PROVISIONER                    RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
local (default)        kubernetes.io/no-provisioner   Delete          WaitForFirstConsumer   false                  3m6s
standard               kubernetes.io/gce-pd           Delete          WaitForFirstConsumer   true                   119m
```

Now let's install the CLO, by getting into the Openshift UI and routing to the `Operator Hub` section. Pay Attention! the CLO uses Elasticsearch CR so for that you will have to install the Elasticsearch Operator that is provided by Red Hat too. After installing those two operators you should see something like this: 

################ Installing CLO and Elastic Operator

After having our operators installed, let's create a Custom Resource that will create our EFK stack: 
 
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
        storageClassName: local
        size: 50G
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
As you see, we have 3 Elasticsearch nodes, with custom resources provided, each one of those nodes will attach a 50Gi PV from the previously created local StorageClass. In addition, we have one Kibana instance for visualization, a curation Job and a collection that is actually the Fluentd Deamonset. 

Let's verify the pods were successfuly created: 

```bash 
$ oc get pods
                                                                                                                           
NAME                                            READY   STATUS    RESTARTS   AGE
cluster-logging-operator-6c44699c49-hhrj9       1/1     Running   0          19m
elasticsearch-cdm-crsry7s5-1-6cf769d6c9-2r2n8   2/2     Running   0          2m5s
elasticsearch-cdm-crsry7s5-2-75df4cb955-st4zs   2/2     Running   0          2m1s
elasticsearch-cdm-crsry7s5-3-6788bd9749-qtfq9   2/2     Running   0          118s
fluentd-5r5s6                                   1/1     Running   0          2m1s
fluentd-6dwpl                                   1/1     Running   2          2m1s
fluentd-blkpk                                   1/1     Running   2          2m1s
fluentd-hj9hn                                   1/1     Running   2          2m1s
fluentd-tqsq9                                   1/1     Running   2          2m1s
fluentd-xc2zm                                   1/1     Running   2          2m1s
kibana-77d4f978db-m2cvl                         2/2     Running   0          2m2s
```

So now we have our EFK stack up and running, As you see we have 6 Fluentd instances (3 masters + 3 workers), 3 elastic nodes and 1 Kibana. 

Let's verify the Elasticsearch PVs were indeed attached to the elastic nodes: 

```bash
$ oc get pv    
                                                                                                                             
NAME                CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM                                                          STORAGECLASS   REASON   AGE
local-pv-9c46cb95   50Gi       RWO            Delete           Bound    openshift-logging/elasticsearch-elasticsearch-cdm-crsry7s5-2   local                   15m
local-pv-f032d5a3   50Gi       RWO            Delete           Bound    openshift-logging/elasticsearch-elasticsearch-cdm-crsry7s5-1   local                   15m
local-pv-ff7cb16f   50Gi       RWO            Delete           Bound    openshift-logging/elasticsearch-elasticsearch-cdm-crsry7s5-3   local                   15m
```

Now, after collecting the Kibana route that was created under the `openshift-logging` project we should see the Kibana dashboard: 

### Kibana 


## Conclusion

We saw how we can control the entire lifecycle of our EFK stack with a simple CR called ClusterLogging. We have used local storage as the storage backend for the Elasticsearch nodes to save the persistency.
Hope you have enjoyed this demo, see ya next time :)

