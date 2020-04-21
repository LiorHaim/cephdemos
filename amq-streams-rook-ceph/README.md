# Deploy Kafka with AMQ Streams and rook-ceph's RBD Storage Class 

In these days the world is moving towards a microservices development approach. With that approach, applications are packed into containers running in a highly available cluster, orchestrated and scheduled by the cluster manager. As part of the deployment, those microservices will communicate with each other to create the full lifecycle of the application (for example, a frontend service moving information to the backend service, which writes that information to a database service). The problem with that architecture is that all operations are performed synchronously, and with a large scale will probably cause a resource starvation (due to the fact those services have no transparency of how much their target service is loaded). To solve this problem, a new approach in the developing world was adopted - Asynchronous operations. 
With asynchronous operations, those microservices can talk with each other through a Message Queue which navigates messages and notifications asynchronously across them, and offloads the target services. An example of such an asynchronous message queue is Kafka. Kafka is a product used for streaming, message queuing and asynchronous operations, It's distributed system, strongly consistent and highly available. In Kafka, one or more producers can publish messages into a topic (a login entity) and subscribers who are interested in that content can start consuming those messages. Each topic is sharded into partitions to reach high throughput workloads and replicated among the cluster nodes to keep the data persistent. So how do we bring Kafka into the microservices world? after all, if we run our applications in Kubernetes isn't that obvious that Kafka will be a part of the architecture too? Yes, it is. And that is why we have AMQ Streams, which is a way of running Kafka in the Openshift Container Platform. AMQ Streams will deploy your Kafka cluster and will manage both Day 1 and Day 2 operations using operators. Besides, AMQ Streams will provide a set of features used today in Kafka (such as Kafka Mirror Maker, Kafka Connect, etc). Today we will deploy our first Kafka cluster using AMQ Streams, and we will also persist our data using rook-ceph's RBD Storage Class. 

## Prerequisites 
* A running Openshift cluster (version 4.3.8) 
* A rook-ceph RBD storage class (In case you haven't deployed reach out to my previous blog)


First let's create a project called `amq-streams` using oc: 

```bash 
oc new-project amq-streams 
```

Now let's reach out to our Openshift Web Console and deploy our AMQ Streams operator using Operator Hub in `amq-streams` project (select the project and click install): 

################################# Picture 

After we install, the operator should appear in the `amq-streams` project, let's verify that: 

```bash 
oc get pods 

amq-streams-cluster-operator-v1.4.0-f6d65d8b5-hqmrp   1/1     Running   1          43h
```

Now that we have our operator running, let's verify we have our RBD storage class is up and running, in this demo we will use PVCs taken from RBD to persist the data that is written to the Kafka commit log in each node: 

```bash 
oc get sc                                                                                                                                            1681  11:05:10  
NAME                        PROVISIONER                  AGE
rook-ceph-block (default)   rook-ceph.rbd.csi.ceph.com   43h
```

So we have our RBD storage class set as the default, which means we can start consuming PVs. To deploy our Kafka cluster, we will use a Kafka Cluster CRD: 

```bash 
oc create -f - <<EOF 
apiVersion: kafka.strimzi.io/v1beta1
kind: Kafka
metadata:
  name: kafka-cluster
  namespace: amq-streams
  labels:
    app: amq-streams-demo
spec:
  kafka:
    version: 2.4.0
    replicas: 3
    listeners:
      plain: {}
      tls: {}
    readinessProbe:
      initialDelaySeconds: 15
      timeoutSeconds: 5
    livenessProbe:
      initialDelaySeconds: 15
      timeoutSeconds: 5  
    config:
      offsets.topic.replication.factor: 3
      transaction.state.log.replication.factor: 3
      transaction.state.log.min.isr: 2
      log.message.format.version: '2.2'
    storage:
      type: persistent-claim
      size: 5Gi
      deleteClaim: true
  zookeeper:
    replicas: 3
    readinessProbe:
      initialDelaySeconds: 15
      timeoutSeconds: 5
    livenessProbe:
      initialDelaySeconds: 15
      timeoutSeconds: 5    
    storage:
      type: persistent-claim
      size: 3Gi
      deleteClaim: true
  entityOperator:
    topicOperator: {}
    userOperator: {}
EOF
```

So as you see we have our Kafka cluster CRD, which will create 3 replicas for both Zookeeper and Kafka, data will also be replicate 3 times across the Kafka cluster nodes, and will be saved on a PV created by the CRD to satisfy that Kafka commit log on each Kafka node. Those PVs will be created automatically in the RBD storage class as this is the default one. 

Now let's veirfy those pods are actually running: 

```bash 
oc get pods  
                                                     
NAME                                                  READY   STATUS    RESTARTS   AGE
amq-streams-cluster-operator-v1.4.0-f6d65d8b5-vqn8n   1/1     Running   0          3m38s
kafka-cluster-entity-operator-5888fdb467-5sh2h        3/3     Running   0          58s
kafka-cluster-kafka-0                                 2/2     Running   0          111s
kafka-cluster-kafka-1                                 2/2     Running   0          111s
kafka-cluster-kafka-2                                 2/2     Running   0          111s
kafka-cluster-zookeeper-0                             2/2     Running   0          2m43s
kafka-cluster-zookeeper-1                             2/2     Running   0          2m43s
kafka-cluster-zookeeper-2                             2/2     Running   0          2m43s
```

So we see we see we have the operator, Zookeeper and Kafka pods. The cluster-entity operator is used for creating Kafka users, managing Kafka cluster ACLs etc. Let's verify the PVs indeed were created: 

```bash 
oc get pv 

pvc-378aee04-38f4-4e5f-a851-7e6c150b5057   5Gi        RWO            Delete           Bound       amq-streams/data-kafka-cluster-kafka-0                rook-ceph-block            4m34s
pvc-3ebc5c72-494e-48b5-b816-a6ac98d72c53   3Gi        RWO            Delete           Bound       amq-streams/data-kafka-cluster-zookeeper-0            rook-ceph-block            5m27s
pvc-4491a189-4cde-4dbb-8604-80cf0424b008   3Gi        RWO            Delete           Bound       amq-streams/data-kafka-cluster-zookeeper-1            rook-ceph-block            5m27s
pvc-779a7cb8-d1f1-4407-ad83-a85d6fe687c5   3Gi        RWO            Delete           Bound       amq-streams/data-kafka-cluster-zookeeper-2            rook-ceph-block            5m27s
pvc-a6eff9da-cba0-4e8b-92af-462b4c389bcc   5Gi        RWO            Delete           Bound       amq-streams/data-kafka-cluster-kafka-2                rook-ceph-block            4m34s
pvc-fab0f3bc-12cf-48d4-b614-3f8b9059d6e2   5Gi        RWO            Delete           Bound       amq-streams/data-kafka-cluster-kafka-1                rook-ceph-block            4m34s
```

Now we have Zookeeper and Kafka saving their data into a rook-ceph cluster with the RBD storage class. Now let's create a KafkaTopic CRD so we could start interacting with the Kafka cluster:

```bash 
oc create -f - <<EOF 
apiVersion: kafka.strimzi.io/v1beta1
kind: KafkaTopic
metadata:
  name: my-topic
  labels:
    strimzi.io/cluster: kafka-cluster
  namespace: amq-streams
spec:
  partitions: 12
  replicas: 3
  config:
    retention.ms: 604800000
    segment.bytes: 1073741824

EOF
```

We will create a topic with 3 replicas and 12 partitions (4 partitions to each Kafka node), Each message that is written to the Kafka cluster will be first written to the primary partition and then replicated to two other secondary partitions. Let's verify the topic was successfuly created: 

```bash 
oc get kafkatopic 

NAME                                                          PARTITIONS   REPLICATION FACTOR
my-topic                                                      12           3
``` 

Now let's create producer/consumer to verify that we can publish and subscribe data to and from the created topic: 

```bash 
oc create -f - <<EOF
apiVersion: extensions/v1beta1
kind: Deployment
metadata:
  labels:
    app: hello-world-producer
  name: hello-world-producer
spec:
  replicas: 1
  template:
    metadata:
      labels:
        app: hello-world-producer
    spec:
      containers:
      - name: hello-world-producer
        image: strimzici/hello-world-producer:support-training
        env:
          - name: BOOTSTRAP_SERVERS
            value: kafka-cluster-kafka-bootstrap:9092
          - name: TOPIC
            value: my-topic
          - name: DELAY_MS
            value: "1000"
          - name: LOG_LEVEL
            value: "INFO"
          - name: MESSAGE_COUNT
            value: "1000000"
---
apiVersion: extensions/v1beta1
kind: Deployment
metadata:
  labels:
    app: hello-world-consumer
  name: hello-world-consumer
spec:
  replicas: 1
  template:
    metadata:
      labels:
        app: hello-world-consumer
    spec:
      containers:
      - name: hello-world-consumer
        image: strimzici/hello-world-consumer:support-training
        env:
          - name: BOOTSTRAP_SERVERS
            value: kafka-cluster-kafka-bootstrap:9092
          - name: TOPIC
            value: my-topic
          - name: GROUP_ID
            value: my-hello-world-consumer
          - name: LOG_LEVEL
            value: "INFO"
          - name: MESSAGE_COUNT
            value: "1000000"
EOF
```

Now let's read the logs for the consumer and the producer to see if the consumer subscribes to the messages the producer publishes: 

```bash 

oc logs hello-world-producer-5d96c5b9df-547p9

2020-04-21 08:48:10 INFO  KafkaProducerExample:18 - Sending messages "Hello world - 1"
2020-04-21 08:48:11 INFO  KafkaProducerExample:18 - Sending messages "Hello world - 2"
2020-04-21 08:48:12 INFO  KafkaProducerExample:18 - Sending messages "Hello world - 3"
2020-04-21 08:48:13 INFO  KafkaProducerExample:18 - Sending messages "Hello world - 4"
2020-04-21 08:48:14 INFO  KafkaProducerExample:18 - Sending messages "Hello world - 5"
``` 

Now let's check for the consumer logs: 

```bash 
oc logs hello-world-consumer-8f9cd7dfd-lc7p4

2020-04-21 08:48:12 INFO  KafkaConsumerExample:25 - 	partition: 2
2020-04-21 08:48:12 INFO  KafkaConsumerExample:26 - 	offset: 0
2020-04-21 08:48:12 INFO  KafkaConsumerExample:27 - 	value: Hello world - 0
2020-04-21 08:48:12 INFO  KafkaConsumerExample:24 - Received message:
2020-04-21 08:48:12 INFO  KafkaConsumerExample:25 - 	partition: 9
2020-04-21 08:48:12 INFO  KafkaConsumerExample:26 - 	offset: 0
2020-04-21 08:48:12 INFO  KafkaConsumerExample:27 - 	value: Hello world - 2
2020-04-21 08:48:12 INFO  KafkaConsumerExample:24 - Received message:
2020-04-21 08:48:12 INFO  KafkaConsumerExample:25 - 	partition: 11
2020-04-21 08:48:12 INFO  KafkaConsumerExample:26 - 	offset: 0
2020-04-21 08:48:12 INFO  KafkaConsumerExample:27 - 	value: Hello world - 3
2020-04-21 08:48:13 INFO  KafkaConsumerExample:24 - Received message:
2020-04-21 08:48:13 INFO  KafkaConsumerExample:25 - 	partition: 4
2020-04-21 08:48:13 INFO  KafkaConsumerExample:26 - 	offset: 0
2020-04-21 08:48:13 INFO  KafkaConsumerExample:27 - 	value: Hello world - 4
2020-04-21 08:48:14 INFO  KafkaConsumerExample:24 - Received message:
2020-04-21 08:48:14 INFO  KafkaConsumerExample:25 - 	partition: 1
2020-04-21 08:48:14 INFO  KafkaConsumerExample:26 - 	offset: 0
2020-04-21 08:48:14 INFO  KafkaConsumerExample:27 - 	value: Hello world - 5
```
We see that the messages the producer sends are processed by the consumer, now lets verify all partitions are evenly distributed and we have no lags between the producer and the consumer: 

```bash 
oc rsh kafka-cluster-kafka-0 bin/kafka-consumer-groups.sh --bootstrap-server kafka-cluster-kafka-bootstrap:9092 --describe --group my-hello-world-consumer

GROUP                   TOPIC           PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                     HOST            CLIENT-ID
my-hello-world-consumer my-topic        2          26              26              0               consumer-1-19d214cd-64a6-48bf-986f-bd696f11850f /10.128.0.73    consumer-1
my-hello-world-consumer my-topic        11         26              26              0               consumer-1-19d214cd-64a6-48bf-986f-bd696f11850f /10.128.0.73    consumer-1
my-hello-world-consumer my-topic        1          26              26              0               consumer-1-19d214cd-64a6-48bf-986f-bd696f11850f /10.128.0.73    consumer-1
my-hello-world-consumer my-topic        6          26              26              0               consumer-1-19d214cd-64a6-48bf-986f-bd696f11850f /10.128.0.73    consumer-1
my-hello-world-consumer my-topic        5          25              25              0               consumer-1-19d214cd-64a6-48bf-986f-bd696f11850f /10.128.0.73    consumer-1
my-hello-world-consumer my-topic        10         25              25              0               consumer-1-19d214cd-64a6-48bf-986f-bd696f11850f /10.128.0.73    consumer-1
my-hello-world-consumer my-topic        9          26              26              0               consumer-1-19d214cd-64a6-48bf-986f-bd696f11850f /10.128.0.73    consumer-1
my-hello-world-consumer my-topic        7          26              26              0               consumer-1-19d214cd-64a6-48bf-986f-bd696f11850f /10.128.0.73    consumer-1
my-hello-world-consumer my-topic        0          26              26              0               consumer-1-19d214cd-64a6-48bf-986f-bd696f11850f /10.128.0.73    consumer-1
my-hello-world-consumer my-topic        4          26              26              0               consumer-1-19d214cd-64a6-48bf-986f-bd696f11850f /10.128.0.73    consumer-1
my-hello-world-consumer my-topic        8          26              26              0               consumer-1-19d214cd-64a6-48bf-986f-bd696f11850f /10.128.0.73    consumer-1
my-hello-world-consumer my-topic        3          26              26              0               consumer-1-19d214cd-64a6-48bf-986f-bd696f11850f /10.128.0.73    consumer-1
```

So if we'll take a look we will see that my-topic indeed has 12 partitions (0-11), where each one gets an equal message number. The problem is that all of those messages are processed by one and only one consumer (can be verified in the HOST column) which can lead to a difference between the CURRENT-OFFSET and LOG_END_OFFSET. In the bottom line, messages will wait to be processed in the queue. Let's see how i looks by scaling the consumers to 0: 

```bash 
oc scale deployment hello-world-consumer --replicas=0
```

Now let's check the partitions: 

```bash 
oc rsh kafka-cluster-kafka-0 bin/kafka-consumer-groups.sh --bootstrap-server kafka-cluster-kafka-bootstrap:9092 --describe --group my-hello-world-consumer

GROUP                   TOPIC           PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID     HOST            CLIENT-ID
my-hello-world-consumer my-topic        0          72              75              3               -               -               -
my-hello-world-consumer my-topic        10         72              75              3               -               -               -
my-hello-world-consumer my-topic        11         72              76              4               -               -               -
my-hello-world-consumer my-topic        1          72              76              4               -               -               -
my-hello-world-consumer my-topic        2          72              76              4               -               -               -
my-hello-world-consumer my-topic        3          72              75              3               -               -               -
my-hello-world-consumer my-topic        4          72              76              4               -               -               -
my-hello-world-consumer my-topic        5          72              75              3               -               -               -
my-hello-world-consumer my-topic        6          72              75              3               -               -               -
my-hello-world-consumer my-topic        7          72              75              3               -               -               -
my-hello-world-consumer my-topic        8          72              76              4               -               -               -
my-hello-world-consumer my-topic        9          72              76              4               -               -               -
```

As you see, we have no CLIENT-ID and the LAG value rises (LAG is the differencial between the CURRENT-OFFSET and the LOG-END-OFFSET). Now let's scale te deployment into 3 consumers in the consumer group and see how the partitions evenly distribute themselves. First let's reset the topic offset to 0, so that all the messages will be re-processed:

```bash 
oc rsh kafka-cluster-kafka-0 bin/kafka-consumer-groups.sh --bootstrap-server kafka-cluster-kafka-bootstrap:9092 --group my-hello-world-consumer --reset-offsets --topic my-topic --execute --to-earliest 

GROUP                          TOPIC                          PARTITION  NEW-OFFSET     
my-hello-world-consumer        my-topic                       2          0              
my-hello-world-consumer        my-topic                       11         0              
my-hello-world-consumer        my-topic                       1          0              
my-hello-world-consumer        my-topic                       6          0              
my-hello-world-consumer        my-topic                       5          0              
my-hello-world-consumer        my-topic                       10         0              
my-hello-world-consumer        my-topic                       9          0              
my-hello-world-consumer        my-topic                       7          0              
my-hello-world-consumer        my-topic                       0          0              
my-hello-world-consumer        my-topic                       4          0              
my-hello-world-consumer        my-topic                       8          0              
my-hello-world-consumer        my-topic                       3          0        
```

All partitions are set to offset 0, now let's scale the consumer deployment to 3: 

```bash 
oc scale deployment hello-world-consumer --replicas=3
```

After the new pods are running, let's check for the partitions once again: 

```bash 
oc rsh kafka-cluster-kafka-0 bin/kafka-consumer-groups.sh --bootstrap-server kafka-cluster-kafka-bootstrap:9092 --describe --group my-hello-world-consumer

GROUP                   TOPIC           PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                     HOST            CLIENT-ID
my-hello-world-consumer my-topic        0          110             110             0               consumer-1-138a3ce0-b3ad-431f-8876-c03da230e435 /10.128.0.75    consumer-1
my-hello-world-consumer my-topic        1          111             111             0               consumer-1-138a3ce0-b3ad-431f-8876-c03da230e435 /10.128.0.75    consumer-1
my-hello-world-consumer my-topic        2          111             111             0               consumer-1-138a3ce0-b3ad-431f-8876-c03da230e435 /10.128.0.75    consumer-1
my-hello-world-consumer my-topic        3          110             110             0               consumer-1-138a3ce0-b3ad-431f-8876-c03da230e435 /10.128.0.75    consumer-1
my-hello-world-consumer my-topic        8          111             111             0               consumer-1-74963626-2931-4502-af30-55cf96803dbc /10.128.0.77    consumer-1
my-hello-world-consumer my-topic        9          111             111             0               consumer-1-74963626-2931-4502-af30-55cf96803dbc /10.128.0.77    consumer-1
my-hello-world-consumer my-topic        10         110             110             0               consumer-1-74963626-2931-4502-af30-55cf96803dbc /10.128.0.77    consumer-1
my-hello-world-consumer my-topic        11         111             111             0               consumer-1-74963626-2931-4502-af30-55cf96803dbc /10.128.0.77    consumer-1
my-hello-world-consumer my-topic        4          111             111             0               consumer-1-6995a646-2af0-43c3-a9f5-3a386377ee1f /10.128.0.76    consumer-1
my-hello-world-consumer my-topic        5          110             110             0               consumer-1-6995a646-2af0-43c3-a9f5-3a386377ee1f /10.128.0.76    consumer-1
my-hello-world-consumer my-topic        6          110             110             0               consumer-1-6995a646-2af0-43c3-a9f5-3a386377ee1f /10.128.0.76    consumer-1
my-hello-world-consumer my-topic        7          110             110             0               consumer-1-6995a646-2af0-43c3-a9f5-3a386377ee1f /10.128.0.76    consumer-1
```

So now we see that after the new pods has started consuming the meesages, we have no LAG, and now the HOST column contains 3 different consumers. Let's see how this thing looks from the consumer side, we'll pick one of the consumer pods and check his logs: 

```bash 
oc get pod hello-world-consumer-8f9cd7dfd-59xnd -o wide  

NAME                                   READY   STATUS    RESTARTS   AGE     IP            NODE                 NOMINATED NODE   READINESS GATES
hello-world-consumer-8f9cd7dfd-59xnd   1/1     Running   0          6m18s   10.128.0.77   crc-45nsk-master-0   <none>           <none>
```

``bash 
oc logs hello-world-consumer-8f9cd7dfd-59xnd 

2020-04-21 09:12:59 INFO  KafkaConsumerExample:24 - Received message:
2020-04-21 09:12:59 INFO  KafkaConsumerExample:25 - 	partition: 10
2020-04-21 09:12:59 INFO  KafkaConsumerExample:26 - 	offset: 123
2020-04-21 09:12:59 INFO  KafkaConsumerExample:27 - 	value: Hello world - 1487
2020-04-21 09:13:01 INFO  KafkaConsumerExample:24 - Received message:
2020-04-21 09:13:01 INFO  KafkaConsumerExample:25 - 	partition: 8
2020-04-21 09:13:01 INFO  KafkaConsumerExample:26 - 	offset: 124
2020-04-21 09:13:01 INFO  KafkaConsumerExample:27 - 	value: Hello world - 1489
2020-04-21 09:13:02 INFO  KafkaConsumerExample:24 - Received message:
2020-04-21 09:13:02 INFO  KafkaConsumerExample:25 - 	partition: 9
2020-04-21 09:13:02 INFO  KafkaConsumerExample:26 - 	offset: 124
2020-04-21 09:13:02 INFO  KafkaConsumerExample:27 - 	value: Hello world - 1490
```

As you see, the consumer we have picked is getting messages from the 4 partitions it's responsible for (which are partitions 8-11). 

## Conclusion 

We saw how we can move our Kafka functions into the Openshift Container Platform using AMQ Streams and rook-ceph RBD. This kind of deployment uses Kubernetes' objectives and can ease the deployment process by containing the infrastructure as part of the application deployment. Hope you have enjoyed this demo, Thank you and have fun :)

