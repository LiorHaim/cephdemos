oc apply -f service-account.yaml
oc apply -f pvc.yaml
oc apply -f configmap.yaml
oc apply -f deploymentconfig.yaml
oc apply -f db-init-job.yaml
oc apply -f service.yaml
oc apply -f route.yaml

