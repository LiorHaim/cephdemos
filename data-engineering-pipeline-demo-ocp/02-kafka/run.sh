oc apply -f kafka.yaml
sleep 90
oc apply -f topics.yaml
oc apply -f kafkaconnect.yaml
sleep 60
oc apply -f kafkaconnector-s3.yaml

