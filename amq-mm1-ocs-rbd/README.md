# Trace you Replicated cross-region data using AMQ Streams Mirror Maker and Jaeger operators

with the massive adoption of Apache Kafka, enteprises are looking for a way of replicating data across different sites. Kafka by itself, has its own internal replicaion and self-healing mechanism which are only relevant to the local cluster and cannot tolerate a whole site failure. The solution for that, is the "Mirror Maker" feature, with this capability, your local Kafka cluster can be replicated asynchronously to a different external/central Kafka cluster that is located on a whole different location in order to persist your data pipelines, log collection, and metrics gathering processes. 

The "Mirror Maker" connects between two clusters, as one of them is the consumer cluster and the other is the producer. Topics are being replicated as a logic entity with all that they have in store into the target cluster where an application can consume the data that is being transferred. The Mirror Maker can be horizontally scalable, which means that it can be scaled out when being the bottleneck.

In this article, we will use the AMQ Streams operator to deploy Kafka on a streched Openshift cluster (where the nodes are located on different sites), and we'll mirror all the messages that are being written to the source cluster into the target cluster using the "Mirror Maker" feature. In addition, we'll use OCS RBD to save the Kafka logDirs, to see that OCS is topology agnostic and can serve nodes from different zones in the same cluster. 

In the end, we'll trace the response time of the whole pipline using Jaeger, where we sould see the response time for each component in the replication pipeline.

Game On! 

## Prerequisites 

* A streached Openshift 4.4.6 cluster 
* An OCS 4.4 cluster serving as the storage platform 
* OCS RBD as default storage class 

 
Let's start by creating a new project for this demo: 

```bash
$ oc new-project amq-streams 
```

After we have the project set up, let's install the AMQ operator in the `amq-streams` project and the Jaeger operator to watch all of the cluster namespaces:

### Install AMQ Operator 
### Install Jaeger 

Now that we have our operators installed, we can start in creating some custom resources that will deploy our environment. First, let's create our two clusters, where the `europe-cluster` is the source cluster and the `us-cluster` is the target one. Each one of the clusters will use OCS RBD to persist it's written data. 

```bash 
$ oc create -f - <<EOF
apiVersion: kafka.strimzi.io/v1beta1
kind: Kafka
metadata:
  name: europe-cluster
spec:
  kafka:
    version: 2.4.0
    replicas: 3
    listeners:
      plain: {}
      tls: {}
    config:
      offsets.topic.replication.factor: 3
      transaction.state.log.replication.factor: 3
      transaction.state.log.min.isr: 2
      log.message.format.version: "2.4"
    storage:
      type: persistent-claim
      size: 20Gi
      deleteClaim: true
  zookeeper:
    replicas: 3
    storage:
      type: persistent-claim
      size: 10Gi
      deleteClaim: true
  entityOperator:
    topicOperator: {}
    userOperator: {}
---
apiVersion: kafka.strimzi.io/v1beta1
kind: Kafka
metadata:
  name: us-cluster
spec:
  kafka:
    version: 2.4.0
    replicas: 3
    listeners:
      plain: {}
      tls: {}
    config:
      offsets.topic.replication.factor: 3
      transaction.state.log.replication.factor: 3
      transaction.state.log.min.isr: 2
      log.message.format.version: "2.4"
    storage:
      type: persistent-claim
      size: 20Gi
      deleteClaim: true
  zookeeper:
    replicas: 3
    storage:
      type: persistent-claim
      size: 10Gi
      deleteClaim: true
  entityOperator:
    topicOperator: {}
    userOperator: {}
EOF
``` 

Now let's verift that our clusters were indeed created and that they have claimed for the wanted storage from our OCS cluster: 

```bash 
$ oc get pods
                                                                                                                        
NAME                                                  READY   STATUS    RESTARTS   AGE
amq-streams-cluster-operator-v1.5.0-f9dc58f75-bqbm8   1/1     Running   0          3m23s
europe-cluster-entity-operator-5b5f7d44f7-57dbj       3/3     Running   0          37s
europe-cluster-kafka-0                                2/2     Running   0          87s
europe-cluster-kafka-1                                2/2     Running   0          87s
europe-cluster-kafka-2                                2/2     Running   0          87s
europe-cluster-zookeeper-0                            1/1     Running   0          2m29s
europe-cluster-zookeeper-1                            1/1     Running   0          2m29s
europe-cluster-zookeeper-2                            1/1     Running   0          2m29s
us-cluster-entity-operator-84fbbf445f-k5kjz           3/3     Running   0          35s
us-cluster-kafka-0                                    2/2     Running   0          95s
us-cluster-kafka-1                                    2/2     Running   0          95s
us-cluster-kafka-2                                    2/2     Running   0          95s
us-cluster-zookeeper-0                                1/1     Running   0          2m29s
us-cluster-zookeeper-1                                1/1     Running   0          2m29s
us-cluster-zookeeper-2                                1/1     Running   0          2m29s
```

```bash
 
$ oc get pvc                                                                                                                         
NAME                              STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS                  AGE
data-europe-cluster-kafka-0       Bound    pvc-c8a7da6c-ca61-4a4f-b26b-d2a3e6ec5f37   20Gi       RWO            ocs-storagecluster-ceph-rbd   2m8s
data-europe-cluster-kafka-1       Bound    pvc-80ecaf91-cfbf-48d6-a37a-86c0737d2f06   20Gi       RWO            ocs-storagecluster-ceph-rbd   2m8s
data-europe-cluster-kafka-2       Bound    pvc-6cb0e5ec-1362-40be-8dbc-b9e1c5265804   20Gi       RWO            ocs-storagecluster-ceph-rbd   2m8s
data-europe-cluster-zookeeper-0   Bound    pvc-7993c0e1-1e2c-4c8f-ad34-51aaa104e6a8   10Gi       RWO            ocs-storagecluster-ceph-rbd   3m11s
data-europe-cluster-zookeeper-1   Bound    pvc-ac0aab81-9f54-45d2-b88d-ff9fcaf9f9d9   10Gi       RWO            ocs-storagecluster-ceph-rbd   3m10s
data-europe-cluster-zookeeper-2   Bound    pvc-5eb69362-a9c5-4248-bb15-253c0fa00c81   10Gi       RWO            ocs-storagecluster-ceph-rbd   3m10s
data-us-cluster-kafka-0           Bound    pvc-2b854633-b6f9-48ac-84d5-487e439f44d9   20Gi       RWO            ocs-storagecluster-ceph-rbd   2m16s
data-us-cluster-kafka-1           Bound    pvc-a1f62aa1-5718-47e9-831a-8a87515dcd0e   20Gi       RWO            ocs-storagecluster-ceph-rbd   2m16s
data-us-cluster-kafka-2           Bound    pvc-deb520d1-e822-4954-80f9-126fd95f09d2   20Gi       RWO            ocs-storagecluster-ceph-rbd   2m16s
data-us-cluster-zookeeper-0       Bound    pvc-6ca9d388-a037-471b-9e24-2d98d9125b33   10Gi       RWO            ocs-storagecluster-ceph-rbd   3m11s
data-us-cluster-zookeeper-1       Bound    pvc-56c7cb8e-ac06-4da2-8378-56c3057863fc   10Gi       RWO            ocs-storagecluster-ceph-rbd   3m10s
data-us-cluster-zookeeper-2       Bound    pvc-a99755a8-a3c5-44f2-b9fe-74d0c0a4bd0b   10Gi       RWO            ocs-storagecluster-ceph-rbd   3m10s
```

Now that we have our two clusters ready, let's create a topic for the source cluster that will be replicated in the future: 

```bash
$ oc create -f - <<EOF
apiVersion: kafka.strimzi.io/v1beta1
kind: KafkaTopic
metadata:
  name: my-topic
  labels:
    strimzi.io/cluster: europe-cluster
spec:
  partitions: 12
  replicas: 3
  config:
    retention.ms: 7200000
    segment.bytes: 1073741824
EOF
```

This topic has the `strimzi.io/cluster` label that points to the source cluster. Now let's check if the topic was indeed created: 

``bash 
$ oc get kt  
                                                                                                                        
NAME       PARTITIONS   REPLICATION FACTOR
my-topic   12           3
```

This topic has 12 paritions with replication 3 factor, which means that each Kafka node will be the primary of 4 partitions and the secondary of 8 other partitions. 

```bash
$ oc create -f - <<EOF 
apiVersion: kafka.strimzi.io/v1beta1
kind: KafkaUser
metadata:
  name: my-us-user
  labels:
    strimzi.io/cluster: us-cluster
spec:
  authentication:
    type: tls
  authorization:
    type: simple
    acls:
      - resource:
          type: topic
          name: my-topic
          patternType: literal
        operation: Read
        host: "*"
      - resource:
          type: topic
          name: my-topic
          patternType: literal
        operation: Describe
        host: "*"
      - resource:
          type: group
          name: my-group
          patternType: literal
        operation: Read
        host: "*"
      - resource:
          type: topic
          name: my-topic
          patternType: literal
        operation: Write
        host: "*"
      - resource:
          type: topic
          name: my-topic
          patternType: literal
        operation: Create
        host: "*"
      - resource:
          type: topic
          name: my-topic
          patternType: literal
        operation: Describe
        host: "*"
---
apiVersion: kafka.strimzi.io/v1beta1
kind: KafkaUser
metadata:
  name: my-europe-user
  labels:
    strimzi.io/cluster: europe-cluster
spec:
  authentication:
    type: tls
  authorization:
    type: simple
    acls:
      - resource:
          type: topic
          name: my-topic
          patternType: literal
        operation: Read
        host: "*"
      - resource:
          type: topic
          name: my-topic
          patternType: literal
        operation: Describe
        host: "*"
      - resource:
          type: group
          name: my-group
          patternType: literal
        operation: Read
        host: "*"
      - resource:
          type: topic
          name: my-topic
          patternType: literal
        operation: Write
        host: "*"
      - resource:
          type: topic
          name: my-topic
          patternType: literal
        operation: Create
        host: "*"
      - resource:
          type: topic
          name: my-topic
          patternType: literal
        operation: Describe
        host: "*"
EOF
```

Now let's verify we have our users created using the `KafkaUser` custom resource:

```bash
$ oc get ku   

NAME             AUTHENTICATION   AUTHORIZATION
my-europe-user   tls              simple
my-us-user       tls              simple
```

We see that we have 2 users that were created and will be used by the application later on. 
After creating the users for authentication and authorization, let's create the Jaeger instance. Jaeger is a distributed tracing tool that will help us in tracing our response time across the replication pipeline. We'll create a `Jaeger CR`, that will watch our namespace, within our deployments (of Mirror Maker and Producer/Consumer) we'll add the requires env vars so that JAeger could trace those services.
Let's create the Jaeger instance: 

```bash
$ oc apply -f - <<EOF 
apiVersion: jaegertracing.io/v1
kind: Jaeger
metadata:
  name: my-jaeger
spec:
  strategy: allInOne
  allInOne:
    image: jaegertracing/all-in-one:latest
    options:
      log-level: debug
  storage:
    type: memory
    options:
      memory:
        max-traces: 100000
  ingress:
    enabled: true
  agent:
    strategy: DaemonSet
  annotations:
    scheduler.alpha.kubernetes.io/critical-pod: ""
EOF
```

This CR will also create a route for the Jaeger UI, where we could find the needed information. This deployment should deploy one pod with two containers, where one container is for the Jaeger instance and the other is for OAuth. 

Now let's create the Mirror Maker CR, once we will deploy the consumer and producer and the cluster will have some data, data will be replicated to the target cluster (in our case, the `us-cluster`):

```bash
$ oc create -f - <<EOF
apiVersion: kafka.strimzi.io/v1beta1
kind: KafkaMirrorMaker
metadata:
  name: my-mirror-maker
spec:
  replicas: 1
  consumer:
    authentication:
      certificateAndKey:
        certificate: user.crt
        key: user.key
        secretName: my-europe-user
      type: tls
    bootstrapServers: europe-cluster-kafka-bootstrap:9093
    tls:
      trustedCertificates:
      - certificate: ca.crt
        secretName: "europe-cluster-cluster-ca-cert"
    groupId: my-group
  producer:
    authentication:
      certificateAndKey:
        certificate: user.crt
        key: user.key
        secretName: my-us-user
      type: tls
    bootstrapServers: us-cluster-kafka-bootstrap:9093
    tls:
      trustedCertificates:
      - certificate: ca.crt
        secretName: "us-cluster-cluster-ca-cert"
  whitelist: ".*"
  tracing:
    type: jaeger
  template:
    mirrorMakerContainer:
      env:
        - name: JAEGER_SERVICE_NAME
          value: my-mirror-maker
        - name: JAEGER_AGENT_HOST
          value: my-jaeger-agent
        - name: JAEGER_SAMPLER_TYPE
          value: const
        - name: JAEGER_SAMPLER_PARAM
          value: "1"
EOF
```

As you see we tell the Mirror Maker which cluster is the source one, and which is the target cluster. We use TLS to secure our data across the whole pipeline using the created certificates. In the bottom, you can see that we have given the Jaeger paramemters so Jaeger could create the tracing for the mirror maker. 

Let's write some data to the cluster: 

```bash
$ oc create -f - <<EOF                                                                                                                
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: hello-world-producer
  name: hello-world-producer
spec:
  replicas: 1
  selector:
    matchLabels:
      app: hello-world-producer
  template:
    metadata:
      labels:
        app: hello-world-producer
    spec:
      containers:
      - name: hello-world-producer
        image: strimzi/hello-world-producer:latest
        env:
          - name: CA_CRT
            valueFrom:
              secretKeyRef:
                name: europe-cluster-cluster-ca-cert
                key: ca.crt
          - name: USER_CRT
            valueFrom:
              secretKeyRef:
                name: my-europe-user
                key: user.crt
          - name: USER_KEY
            valueFrom:
              secretKeyRef:
                name: my-europe-user
                key: user.key
          - name: BOOTSTRAP_SERVERS
            value: europe-cluster-kafka-bootstrap:9093
          - name: TOPIC
            value: my-topic
          - name: DELAY_MS
            value: "1000"
          - name: LOG_LEVEL
            value: "INFO"
          - name: MESSAGE_COUNT
            value: "1000000"
          - name: JAEGER_SERVICE_NAME
            value: hello-world-producer
          - name: JAEGER_AGENT_HOST
            value: my-jaeger-agent
          - name: JAEGER_SAMPLER_TYPE
            value: const
          - name: JAEGER_SAMPLER_PARAM
            value: "1"
EOF
```

We create a producer that writes data to `my-topic` that is located in the `europe-cluster`. The producer uses the created user to secure data ingestion using TLS, and we have the Jaeger parameters so that Jaeger can stat tracing the producer as well. 

After the pod is running, check it's logs to verify that it indeed writes messages to the `europe-cluster`: 

```bash 
oc logs $(oc get pod -l app=hello-world-producer -o=jsonpath='{.items[0].metadata.name}') -f

2020-07-06 15:15:55 INFO  KafkaProducerExample:35 - Sending messages "Hello world - 1"
2020-07-06 15:15:56 INFO  KafkaProducerExample:35 - Sending messages "Hello world - 2"
2020-07-06 15:15:57 INFO  KafkaProducerExample:35 - Sending messages "Hello world - 3"
2020-07-06 15:15:58 INFO  KafkaProducerExample:35 - Sending messages "Hello world - 4"
2020-07-06 15:15:59 INFO  KafkaProducerExample:35 - Sending messages "Hello world - 5"
2020-07-06 15:16:00 INFO  KafkaProducerExample:35 - Sending messages "Hello world - 6"
```

We see that the source cluster gets the messages. Now let's do the same with the consumer which will consume those messages from the `us-cluster` which is the target one. 
Let's create the consumer deployment: 

```bash 
$ oc create -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: hello-world-consumer
  name: hello-world-consumer
spec:
  replicas: 1
  selector:
    matchLabels:
      app: hello-world-consumer
  template:
    metadata:
      labels:
        app: hello-world-consumer
    spec:
      containers:
      - name: hello-world-consumer
        image: strimzi/hello-world-consumer:latest
        env:
          - name: CA_CRT
            valueFrom:
              secretKeyRef:
                name: us-cluster-cluster-ca-cert
                key: ca.crt
          - name: USER_CRT
            valueFrom:
              secretKeyRef:
                name: my-us-user
                key: user.crt
          - name: USER_KEY
            valueFrom:
              secretKeyRef:
                name: my-us-user
                key: user.key
          - name: BOOTSTRAP_SERVERS
            value: us-cluster-kafka-bootstrap:9093
          - name: TOPIC
            value: my-topic
          - name: GROUP_ID
            value: my-group
          - name: LOG_LEVEL
            value: "INFO"
          - name: MESSAGE_COUNT
            value: "1000000"
          - name: JAEGER_SERVICE_NAME
            value: hello-world-consumer
          - name: JAEGER_AGENT_HOST
            value: my-jaeger-agent
          - name: JAEGER_SAMPLER_TYPE
            value: const
          - name: JAEGER_SAMPLER_PARAM
            value: "1"
EOF	
``` 

As for the producer, the consumer as well uses TLS, consumes from the `us-cluster` and uses the Jaeger parameters so that Jaeger could trace its response times. 
Let's check its logs to see if the mirroring works: 


```bash
$ oc logs $(oc get pod -l app=hello-world-consumer -o=jsonpath='{.items[0].metadata.name}') -f

2020-07-06 15:17:42 INFO  KafkaConsumerExample:43 - Received message:
2020-07-06 15:17:42 INFO  KafkaConsumerExample:44 - 	partition: 0
2020-07-06 15:17:42 INFO  KafkaConsumerExample:45 - 	offset: 99
2020-07-06 15:17:42 INFO  KafkaConsumerExample:46 - 	value: "Hello world - 99"
2020-07-06 15:17:42 INFO  KafkaConsumerExample:43 - Received message:
2020-07-06 15:17:42 INFO  KafkaConsumerExample:44 - 	partition: 0
2020-07-06 15:17:42 INFO  KafkaConsumerExample:45 - 	offset: 100
2020-07-06 15:17:42 INFO  KafkaConsumerExample:46 - 	value: "Hello world - 100"
2020-07-06 15:17:42 INFO  KafkaConsumerExample:43 - Received message:
2020-07-06 15:17:42 INFO  KafkaConsumerExample:44 - 	partition: 0
2020-07-06 15:17:42 INFO  KafkaConsumerExample:45 - 	offset: 101
2020-07-06 15:17:42 INFO  KafkaConsumerExample:46 - 	value: "Hello world - 101"
```

Yes! We have our messages in the target cluster, that means that the Mirror Maker does its job :)

Now let's start tracing the response times to see if we have any performance issues, use the route in your browser to opwn the Jaeger UI:

```bash 
$ oc get route
                                                                                                           
NAME        HOST/PORT                                    PATH   SERVICES          PORT    TERMINATION   WILDCARD
my-jaeger   my-jaeger-amq-streams.apps.ocp4.ocppaz.com          my-jaeger-query   <all>   reencrypt     None
```

In the main page we can see the query, which traces the response times for the consumer service. These results can be sorted to view which is the response that took the longest time: 




We can click on the highest dot to get an architectual view with response times, here we can see the whole pipeline functioning: 




## Conclusion

We saw how we can use Kafka "Mirror Maker" to replicate data across sites, where the mirroring process replicated the topics that have been created in the source cluster to the target cluster. 
Thanks to OCS, we have attaches PVs for the Kafka logDirs to persist our data locally with OCS RBD block storage. In the end, we have traced the response times for the replication pipeline from the producer that writes messages to the source cluster to the consumer that consumes the written messages from the target cluster, all made with AMQ Streams operator on Openshift Container Platform. 

Hope you have enjoyed this demo, see ya next time :)
