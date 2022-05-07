# Program & Containerize Your Kafka Producer/Consumer In Minutes 

In this article, I'll show how you can build your own `Kafka` producer/consumer in minutes. 

We often need to be able to program our own producer/consumer for demos, functional testing, and sometimes even scale testing. 

In this article I've used a `pip3` library called `kafka-python` in order to interact with a containerized `Kafka` cluster installed as part of this article. 

As Kubernetes is a major factor in our infrastructure today, we'll containerize our producer/consumer as well to be able to `lift-and-shift` our producer/consumer into our Kubernetes cluster. 

So let's go!

## Prerequisites 

* Podman installed on your computer (I've added the `docker-podman` package as well)

**Note:** The `docker-podman` package is an alias that gived you the ability of using `Docker` commands altought there is no Docker Engine underneath. 

## Setting Up A Containerized Kafka Cluster

In order to run our containerized `Kafka` cluster, We'll use single-node based services, so our `Zookeeper` and `Broker` will be installed on a single container. 

Let's start by creating a shared network for our `Kafka` cluster: 

```bash
$ docker network create kafka 
```
This will create an isolated network under a network namespace, that will allow our containers to share subnets, DNS records, etc. 

Now we'll initialize our `Zookeeper` service: 

```bash
$ docker run -d --name zookeeper --net kafka -e ZOOKEEPER_CLIENT_PORT=2181 -e ZOOKEEPER_TICK_TIME=2000 -p 22181:2181 confluentinc/cp-zookeeper:latest
```

As you can see, we've run the `Zookeeper` container with a hardened name, and attached it to the previously created network. We've also exposed the `Zookeeper` port, which is `2181` to `22181` on the host, just in case we'll have to access it externally. 

Great! no that we have `Zookeeper` running, Let's set-up our `Kafka` broker, to start write/read events: 

```bash 
$ docker run -d --name kafka --net kafka -e KAFKA_BROKER_ID=1 -e KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181 -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092,PLAINTEXT_HOST://localhost:29092 -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT -e KAFKA_INTER_BROKER_LISTENER_NAME=PLAINTEXT -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 -p 29092:29092 confluentinc/cp-kafka:latest
```

As with `Zookeeper`, we gave our `Broker` container a name and attached it to the shared network, so that the cluster will be able to resolve the attached containers. 

Some important configuration to notice: 
* `KAFKA_ZOOKEEPER_CONNECT` connects to the name that was given to our `Zookeeper` container, using the DNS record that was created automatically by our shared network
* `KAFKA_ADVERTISED_LISTENERS` defines how should `Kafka` advertize its nodes, as we need it to listen both our containerized network and the outside world, we'll tell `Kafka` that the broker name that will be returen for internal access (inside the containerized network) is `kafka:9092`. and for external network `localhost:29092`. 

As you can see, we tell our `Kafka` broker that it'll have only one replica, and we map the `29092` port to the host itself, in case we'll need to access it externally. 

## Interacting With Our Kafka Topic 

Let's login to our `Kafka` cluster in order to create a topic: 

```bash
$ docker exec -it kafka bash
```

Now let's create a topic with `Kafka's` internal scripts: 

```bash
$ kafka-topics --create --topic test --replication-factor 1 --partitions 1 -bootstrap-server kafka:9092

Created topic test.
```

Great! let's verify that everything we configured correctly: 

```bash
$ kafka-topics --describe --topic test --bootstrap-server localhost:9092

Topic: test	TopicId: AsiqI1nXTSO0xp8tYCi0Zw	PartitionCount: 1	ReplicationFactor: 1	Configs: 
	Topic: test	Partition: 0	Leader: 1	Replicas: 1	Isr: 1
```

We see that our topic was successfully created, Let's test it. 

We'll use `Kafka's` internal scripts to interact with this topic. 

First, we'll send some messages using our `Kafka` producer: 

```bash
$ kafka-console-producer --topic test --bootstrap-server kafka:9092

>test
>This is test
```

Now, we'll do the same to read the advertized messages: 

```bash
$ kafka-console-consumer --topic test --bootstrap-server kafka:9092 --from-beginning

test
This is test
```

Great! but now we haven't tested network access as this thing happened locally on our broker. 

In order to test our created topic externally, we'll have to use the external representation of our `Kafka` broker, which is `localhost:29092`. 

In order to interact with our cluster, we'll use a tool called `kcat` the simulates producer/consumer with an easy CLI: 

```bash 
$ kcat -b localhost:29092 -t test

% Auto-selecting Consumer mode (use -P or -C to override)
test
This is test
```

As we've mapped the external port of our `Kafka` broker to port `29092` on the host, we're now able to connect to the cluster externally. In my case, It's `localhost` as I run it on my computer, but it could be any IP that you'll choose. 

**Note:** If you plan on not using `localhost`, change `KAFKA_ADVERTISED_LISTENERS` to suite the external representation that you choose 

Now let's produce some events to the same topic using `kcat`: 

```bash
$ kcat -b localhost:29092 -t test -P

This is test 2
```

Read the topic content once again:

```bash
$ kcat -b localhost:29092 -t test

% Auto-selecting Consumer mode (use -P or -C to override)
test
This is test
This is test 2
```

## Developing Our Own Kakfa Producer/Consumer

Let's start by writing the code that will eventually act as our `Kafka` producer: 

```python
from kafka import KafkaProducer
from json import dumps
import argparse
import time
import logging
import sys 

Log_Format = "%(levelname)s %(asctime)s - %(message)s"
logging.basicConfig(
                    stream = sys.stdout,
                    filemode = "w",
                    format = Log_Format,
                    level = logging.INFO)

logger = logging.getLogger()


parser = argparse.ArgumentParser() 
parser.add_argument('-b', '--bootstrap-servers', help="Bootstrap servers to use from Kafka cluster",
                            required=True)
parser.add_argument('-t', '--topic', help="Topic to use from Kafka cluster",
                            required=True)
args = parser.parse_args()

print(args.bootstrap_servers)
producer = KafkaProducer(bootstrap_servers=[args.bootstrap_servers],
                         value_serializer=lambda x:
                         dumps(x).encode('utf-8'))

for e in range(100):
    data = {'number' : e}
    logger.info(f"Writing document {data} to Kafka cluster...")
    producer.send(args.topic, value=data)
    time.sleep(1)

```

This simple code will write `100` events to our `Kafka` cluster, while sleeping for a second between iterations. 

The script uses `argparse` to get the broker list, so as the wanted topic and prints to written messages to STDOUT. 

In order to containerize this code snippet, we'll have to use two more files. 

The first one, is the `Dockerfile` that holds the way our producer container image should be built: 

```bash
# choose python image
FROM python:3.8-slim-buster

# install needed pip packages
RUN mkdir /code
WORKDIR /code
COPY producer.py /code/
COPY requirements.txt /code/
RUN pip3 install -r requirements.txt

# run script from entry point
ENTRYPOINT [ "python3", "./producer.py" ]
```

The second one is the `requirements.txt` file that holds all of our dependencies: 

```bash
kafka-python 
argparse 
```

Now let's build our producer image: 

```bash
$ docker build -t kafka-basic-producer .
```

Great, now we can test it in front of our containerized `Kafka cluster:

```bash
$ docker run --rm --name kafka-basic-producer --net kafka localhost/kafka-basic-producer -b 'kafka:9092' -t 'test'
```

AS ou can see, we've used `kafka:9092` as the broker list, as this is the internal shared network. We've also used the `test` script that was created in previous stages. 

Look at the container logs: 

```bash
$ docker logs -f kafka-basic-producer

NFO 2022-05-05 22:18:31,575 - Writing document {'number': 0} to Kafka cluster...
INFO 2022-05-05 22:18:32,579 - Writing document {'number': 1} to Kafka cluster...
INFO 2022-05-05 22:18:33,582 - Writing document {'number': 2} to Kafka cluster...
INFO 2022-05-05 22:18:34,585 - Writing document {'number': 3} to Kafka cluster...
INFO 2022-05-05 22:18:35,587 - Writing document {'number': 4} to Kafka cluster...
INFO 2022-05-05 22:18:36,589 - Writing document {'number': 5} to Kafka cluster...
INFO 2022-05-05 22:18:37,591 - Writing document {'number': 6} to Kafka cluster...
INFO 2022-05-05 22:18:38,594 - Writing document {'number': 7} to Kafka cluster...
INFO 2022-05-05 22:18:39,597 - Writing document {'number': 8} to Kafka cluster...
INFO 2022-05-05 22:18:40,599 - Writing document {'number': 9} to Kafka cluster...
```

Nice! we have our events written to our containerized `Kafka` cluster. 

Let's do the same with our consumer, Take a look at its code snippet: 

```python
from kafka import KafkaConsumer
from json import loads
import argparse
import time
import logging
import sys 

Log_Format = "%(levelname)s %(asctime)s - %(message)s"
logging.basicConfig(
                    stream = sys.stdout,
                    filemode = "w",
                    format = Log_Format,
                    level = logging.INFO)

logger = logging.getLogger()


parser = argparse.ArgumentParser() 
parser.add_argument('-b', '--bootstrap-servers', help="Bootstrap servers to use from Kafka cluster",
                            required=True)
parser.add_argument('-t', '--topic', help="Topic to use from Kafka cluster",
                            required=True)
args = parser.parse_args()

consumer = KafkaConsumer(args.topic, auto_offset_reset='earliest', enable_auto_commit=True, 
                         group_id='my-group-1', bootstrap_servers=[args.bootstrap_servers], 
                         value_deserializer=lambda m: loads(m.decode('utf-8')))

for m in consumer:
    logger.info(f"Consuming document {m.value} from Kafka cluster...")
    time.sleep(1)
```

Code looks quite the same, except that here we load our data from the cluster. Let's build it the same way we did with our producer: 

```bash
$ docker build -t kafka-basic-consumer .
```

Now let's run it: 

```bash
$ docker run --rm --name kafka-basic-consumer --net kafka localhost/kafka-basic-consumer -b 'kafka:9092' -t 'test'
```

When looking at the logs we see that now we have our messages read from the cluster: 

```bash
$ docker logs -f kafka-basic-consumer 

INFO 2022-05-05 22:36:32,278 - Consuming document {'number': 0} from Kafka cluster...
INFO 2022-05-05 22:36:33,279 - Consuming document {'number': 1} from Kafka cluster...
INFO 2022-05-05 22:36:34,281 - Consuming document {'number': 2} from Kafka cluster...
INFO 2022-05-05 22:36:35,282 - Consuming document {'number': 3} from Kafka cluster...
INFO 2022-05-05 22:36:36,283 - Consuming document {'number': 4} from Kafka cluster...
INFO 2022-05-05 22:36:37,284 - Consuming document {'number': 5} from Kafka cluster...
INFO 2022-05-05 22:36:38,285 - Consuming document {'number': 6} from Kafka cluster...
INFO 2022-05-05 22:36:39,287 - Consuming document {'number': 7} from Kafka cluster...
INFO 2022-05-05 22:36:40,288 - Consuming document {'number': 8} from Kafka cluster...
INFO 2022-05-05 22:36:41,290 - Consuming document {'number': 9} from Kafka cluster...
```

Thank you very much for reading that far, Hope you've enjoyed our demo. 

See ya next time!