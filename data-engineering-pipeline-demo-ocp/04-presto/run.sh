oc create secret generic aws-secret --from-literal=AWS_ACCESS_KEY_ID="HC8V2PT7HX8ZFS8NQ37R" --from-literal=AWS_SECRET_ACCESS_KEY="Y6CENKXozDDikJHQgkbLFM38muKBnmWBsAA1DXyU"
oc apply -f postgres.yaml
sleep 60
oc apply -f presto.yaml
