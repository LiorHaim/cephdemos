
# Run real-time ETLs using Kafka Streams API on Openshift 

Today more and more organizations are moving away from ETL, an ETL process is the form of Extract-> Transform -> Load where the data is being extracted from it's source location, being transformed into a clean valuable data and then loaded into a target database/warehouse. ETL jobs are batch-driven, mostly time consuming and messy mainly because there is no alignment between the different ETL pipeline components, which made the ETL architecture to be looking like a big spagetti plate. 

So, is ETL dead? 
The answer is not at all, it's just being re-newed. 

Many organizations understand that in today's world we cannot afford running batch jobs at nights while having the data available only the day or two after, Today we need the data to be available in real-time. So what is the new ETL? The new ETL uses fast, reliable and resilient products such as Kafka to perform the Extract-> Transform-> Load pipeline in real-time. To do so, Kafka uses the Kafka Streams API, which is a programmable interface that allows us writing our own code to transform, clean, join our data in real time. 

Kafka Streams API will consume topics from our Kafka cluster and will transform the data into the final structure we want it to be, then it will load the data into a target topic so that other applications could subscribe and consume the transformed data. To emphasize how the Streams API works, we will be using a music chart application written in Java. 

## About Music Chart 

Music chart is a Java application that joins two topics from a given Kafka cluster, one topic contains a list of songs, and the other topic contains a random list of the songs that has being played. In our example, we have the `player-app` producer that notifies the Kafka topic each time a new song has been played. Our Music Chart app takes those two topics, and joins them to find out how many times a given songs have been played. This joined data can be sinked into target databases or can be consumed by subscribers for that given topic. 


Lets get it on! 

## Prerequisites 

* A running Openshift cluster (mine is 4.5.1) 


## Installation 

To start using the Streams API, we should first install our Kafka cluster, to do so we'll use `AMQ Streams` operator provided by Openshift. Let's create a project in which our Kafka cluster will be deployed in: 

```
$ oc new-project amq-streams
```

Now let's use the `OperatorHub` section to install our operator, search for the `AMQ Streams` operator: 

========= Image


After we have our operator installed, we can go on and create our Kafka cluster, to create it we'll use the `Kafka` CR: 

```bash 
oc create -f - <<EOF                                                                                                             
apiVersion: kafka.strimzi.io/v1beta1
kind: Kafka
metadata:
  name: my-cluster
  namespace: amq-streams
  labels:
    app: amq-streams-demo
spec:
  kafka:
    version: 2.5.0
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
      type: ephemeral
  zookeeper:
    replicas: 3
    readinessProbe:
      initialDelaySeconds: 15
      timeoutSeconds: 5
    livenessProbe:
      initialDelaySeconds: 15
      timeoutSeconds: 5
    storage:
      type: ephemeral
  entityOperator:
    topicOperator: {}
    userOperator: {}
EOF
```


Let's verify our Kafka cluster has been successfully created using the `oc get pods` command: 

```bash 
$ oc get pods 

NAME                                                   READY   STATUS    RESTARTS   AGE
amq-streams-cluster-operator-v1.5.2-84bb9447ff-h6llb   1/1     Running   0          5m19s
my-cluster-entity-operator-7d79758484-gm6g4            3/3     Running   0          15s
my-cluster-kafka-0                                     2/2     Running   0          39s
my-cluster-kafka-1                                     2/2     Running   0          39s
my-cluster-kafka-2                                     2/2     Running   0          39s
my-cluster-zookeeper-0                                 1/1     Running   0          69s
my-cluster-zookeeper-1                                 1/1     Running   0          69s
my-cluster-zookeeper-2                                 1/1     Running   0          69s
```

Great! we have our Kafka cluster ready to go :) 
Now let's create the two topics that will be used in this demo, to do so we will use the `KafkaTopic` CR: 

```bash 
oc create -f - <<EOF
apiVersion: kafka.strimzi.io/v1beta1
kind: KafkaTopic
metadata:
  name: songs
  labels:
    strimzi.io/cluster: my-cluster
spec:
  partitions: 12
  replicas: 3
  config:
    retention.ms: 7200000
    segment.bytes: 1073741824
---
apiVersion: kafka.strimzi.io/v1beta1
kind: KafkaTopic
metadata:
  name: played-songs
  labels:
    strimzi.io/cluster: my-cluster
spec:
  partitions: 12
  replicas: 3
  config:
    retention.ms: 7200000
    segment.bytes: 1073741824
EOF
```

Now let's verify our topics were successfuly created: 

```bash 
$ oc get kt 
                                                                                                                          
NAME           PARTITIONS   REPLICATION FACTOR
played-songs   12           3
songs          12           3
```

Now let's deploy the `player-app` which will be our producer. The `player-app` will write the list of songs to the the `songs` topic, and the random played songs to the `played-songs` topic: 

```bash 
$ oc create -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: player-app
  name: player-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: player-app
  template:
    metadata:
      labels:
        app: player-app
    spec:
      containers:
      - name: player-app
        image: shonpaz123/kafka-streams:player-app
EOF
```

Let's take a look at the `player-app` pod logs to see if the played songs has been written to the topic: 

```bash 
$ oc logs -f player-app-7d77899478-npt8r

2020-07-25 19:52:47,038 INFO  [org.acm.PlaySongsGenerator] (RxComputationThreadPool-1) song 2: Believe played.
2020-07-25 19:52:52,038 INFO  [org.acm.PlaySongsGenerator] (RxComputationThreadPool-1) song 7: Fox On The Run played.
2020-07-25 19:52:57,037 INFO  [org.acm.PlaySongsGenerator] (RxComputationThreadPool-1) song 2: Believe played.
2020-07-25 19:53:02,037 INFO  [org.acm.PlaySongsGenerator] (RxComputationThreadPool-1) song 5: Sometimes played.
2020-07-25 19:53:07,037 INFO  [org.acm.PlaySongsGenerator] (RxComputationThreadPool-1) song 6: Into The Unknown played.
2020-07-25 19:53:12,037 INFO  [org.acm.PlaySongsGenerator] (RxComputationThreadPool-1) song 2: Believe played.
2020-07-25 19:53:17,037 INFO  [org.acm.PlaySongsGenerator] (RxComputationThreadPool-1) song 5: Sometimes played.
2020-07-25 19:53:22,037 INFO  [org.acm.PlaySongsGenerator] (RxComputationThreadPool-1) song 2: Believe played.
2020-07-25 19:53:27,037 INFO  [org.acm.PlaySongsGenerator] (RxComputationThreadPool-1) song 2: Believe played.
2020-07-25 19:53:32,037 INFO  [org.acm.PlaySongsGenerator] (RxComputationThreadPool-1) song 8: Perfect played.
2020-07-25 19:53:37,037 INFO  [org.acm.PlaySongsGenerator] (RxComputationThreadPool-1) song 5: Sometimes played.
```

As you see there are some songs that are being played a few times, This is where we leverage the Kafka streams API that will count the number of times each song was played.
Let's use the `kafka-console-consumer.sh` script to list all the messages we have in those two topics to prove that we have that data in Kafka: 

```
$ oc exec -it my-cluster-kafka-0 bin/kafka-console-consumer.sh -- --bootstrap-server localhost:9092 --from-beginning --topic songs  

{"author":"James","id":5,"name":"Sometimes"}
{"author":"Cher","id":2,"name":"Believe"}
{"author":"Frozen II","id":6,"name":"Into The Unknown"}
{"author":"Scorpions","id":3,"name":"Still Loving You"}
{"author":"Queen","id":4,"name":"Bohemian Rhapsody"}
{"author":"Ed Sheeran","id":8,"name":"Perfect"}
{"author":"Sweet","id":7,"name":"Fox On The Run"}
{"author":"Ennio Morricone","id":1,"name":"The Good The Bad And The Ugly"}
```

Now let's take a look at the `played-songs` topic: 

```bash 
$ oc exec -it my-cluster-kafka-0 bin/kafka-console-consumer.sh -- --bootstrap-server localhost:9092 --from-beginning --topic played-songs

2020-07-25T19:52:47.038904Z;Alex
2020-07-25T19:52:57.038328Z;Burr
2020-07-25T19:53:07.038294Z;Burr
2020-07-25T19:53:12.038258Z;Edson
2020-07-25T19:53:22.038396Z;Edson
2020-07-25T19:53:27.038313Z;Kamesh
2020-07-25T19:53:52.038504Z;Alex
2020-07-25T19:54:02.038232Z;Burr
2020-07-25T19:54:27.038223Z;Kamesh
2020-07-25T19:54:42.038293Z;Alex
2020-07-25T19:55:12.038265Z;Kamesh
2020-07-25T19:55:17.038168Z;Kamesh
2020-07-25T19:55:22.038151Z;Kamesh
2020-07-25T19:57:07.038171Z;Kamesh
```

Great! we have our data, now we can start transforming it into our desired strcture, Let's deploy the `music-chart` application: 

```bash 
$ oc create -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: music-chart
  name: music-chart
spec:
  replicas: 1
  selector:
    matchLabels:
      app: music-chart
  template:
    metadata:
      labels:
        app: music-chart
    spec:
      containers:
      - name: music-chart
        image: shonpaz123/kafka-streams:music-chart
EOF
```

After we have our application deployed, let's take a look at the `music-chart` pod logs: 

```bash 
$ oc logs -f music-chart-778b8f767c-fhz4w 

[KTABLE-TOSTREAM-0000000006]: 1, PlayedSong [count=13, songName=The Good The Bad And The Ugly]
[KTABLE-TOSTREAM-0000000006]: 5, PlayedSong [count=22, songName=Sometimes]
[KTABLE-TOSTREAM-0000000006]: 7, PlayedSong [count=19, songName=Fox On The Run]
[KTABLE-TOSTREAM-0000000006]: 8, PlayedSong [count=13, songName=Perfect]
[KTABLE-TOSTREAM-0000000006]: 4, PlayedSong [count=12, songName=Bohemian Rhapsody]
[KTABLE-TOSTREAM-0000000006]: 3, PlayedSong [count=9, songName=Still Loving You]
[KTABLE-TOSTREAM-0000000006]: 2, PlayedSong [count=13, songName=Believe]
[KTABLE-TOSTREAM-0000000006]: 6, PlayedSong [count=15, songName=Into The Unknown]
[KTABLE-TOSTREAM-0000000006]: 2, PlayedSong [count=14, songName=Believe]
[KTABLE-TOSTREAM-0000000006]: 8, PlayedSong [count=14, songName=Perfect]
[KTABLE-TOSTREAM-0000000006]: 4, PlayedSong [count=13, songName=Bohemian Rhapsody]
[KTABLE-TOSTREAM-0000000006]: 2, PlayedSong [count=15, songName=Believe]
[KTABLE-TOSTREAM-0000000006]: 7, PlayedSong [count=20, songName=Fox On The Run]
```

As you see we our `music-chart` application used the data that we have in our Kafka cluster and counted the number of times each song was played! 

## Conclusion 

In this demo, I've showed you how you can create your own ETL using Kafka only, This method simlifies the way we treat the big data world today, mostly when having huge amounts of data moving back and forth in our organizations. That way, Kafka performs as a single-point-of-truth when having metrics, events, ETLs and more using Kafka as a fast, reliable and resilent solution. 
Hope you have enjoyed this demo, see ya next time :) 


