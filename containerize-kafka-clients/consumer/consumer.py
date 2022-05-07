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

