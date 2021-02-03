oc delete -f 05-superset/service.yaml -f 05-supersetservice-account.yaml -f 05-supersetroute.yaml -f 05-supersetdeploymentconfig.yaml -f 05-supersetdb-init-job.yaml -f 05-supersetconfigmap.yaml
oc delete -f 02-kafka/kafkaconnector-s3.yaml -f 02-kafkakafkaconnect.yaml -f 02-kafkatopics.yaml -f 02-kafkakafka.yaml
oc delete -f 03-music-chart-app/music-chart.yaml -f 03-music-chart-app/player-app.yaml
oc delete -f 04-presto/presto.yaml -f 04-presto/postgres.yaml
aws s3 rm --recursive s3://music-chart-songs-store-changelog --endpoint-url http://192.168.1.59:8080
