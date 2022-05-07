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

for e in range(10):
    data = {'number' : e}
    logger.info(f"Writing document {data} to Kafka cluster...")
    producer.send(args.topic, value=data)
    time.sleep(1)

