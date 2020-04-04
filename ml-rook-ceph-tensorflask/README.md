## Run an automated ML pipeline with Ceph Bucket Notifications, Tensorflow and Flask using Openshift 

In today's world, many organizations are moving towards machine learning with understanding that there is a strong need of getting reliable data, fast. We are serrounded by organizations that are data-driven, searching for the best way of getting the knowledge that will help them to take the right business decisions. Most of these organizations collect huge amount of data from thousands of sources, but collecting the raw data isn't worth much on it's own unless we process and analyze it. When an organization reaches a point where it has massive amounts of data, it is important to keep the analysis process automatic as possible to avoid human intervention. In order to use those automatic pipelines we need to find the right solutions that will help us reaching our buisness goal. To give a short example of how we create such an automatic ML pipeline, we'll use few open source solutions that will help us with classifying images. 
Image classification refers to a process in computer vision that can classify an image according to it's visual content. For example, an image classification algorithm may be designed to tell if an image contains a human figure or not, another one may recognize objects in a given image. While detecting an object is trivial for humans, robust image classification is still a challenge in computer vision applications.

A short explenation of the demo's architecture: 
In this demo we will use Openshift Container Platform to run the different containerized workloads. Upon Opensfhit, we will use rook-ceph as an object store that will notify a Flask-Tensorflow service about images written to the S3 bucket. We will use Ceph Bucket Notifications to notify on objects that are created with a specific suffix, so each time a JPG image will be uploaded to to S3 bucket, Ceph will throw a notificatio towards our Flask REST API. When our REST API gets the notification, it will fetch the S3 object from Ceph and run the classifciation algorithm. To cut the long story short, for each image uploaded to our bucket, we should get a classifcation output. 

Image uploaded (*.JPG) --> S3 Bucket --> Notification for JPG image created --> HTTP endpoint --> Flask REST trigger --> Image classification algorithm --> Inference result 

# Prerequisites 

* Openshift Container Platform (4.3.8 version)
* Rook-Ceph cluster exposing S3 interface (octopus version) 
* Notify tool for configuring the bucket notification configuration (shonpaz123/notify:latest)
* Flask-Tensorflow image classification app (shonpaz123/image-classification:latest)

# Installation 

We'll start by verifying our s3 service is working as expected, to do so we'll expose the S3 service created by rook-ceph so we could curl it, and get the XML: 
```bash 
oc expose svc rook-ceph-rgw-my-store -n rook-ceph 

oc get route | grep rgw
rook-ceph-rgw-my-store   rook-ceph-rgw-my-store-rook-ceph.apps-crc.testing          rook-ceph-rgw-my-store   http                 None
```

Now let's curl to our S3 service ans see if we get the wanted XML saying our S3 service works properly: 
```bash 
curl http://rook-ceph-rgw-my-store-rook-ceph.apps-crc.testing
<?xml version="1.0" encoding="UTF-8"?><ListAllMyBucketsResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Owner><ID>anonymous</ID><DisplayName></DisplayName></Owner><Buckets></Buckets></ListAllMyBucketsResult>
```
Great, now we have the S3 service running, let's run the image classification app by using the following deployment example: 
```bash 
apiVersion: apps/v1
kind: Deployment
metadata:
  name: image-classifcation 
  labels:
    app: image-classifciation 
spec:
  replicas: 1
  selector:
    matchLabels:
      app: image-classification 
  template:
    metadata:
      labels:
        app: image-classification 
    spec:
      containers:
      - name: image-classification 
        image: shonpaz123/image-classification
        ports:
        - containerPort: 5001
        env: 
        - name: AWS_ACCESS_KEY_ID 
          value: replaceme 
        - name: AWS_SECRET_ACCESS_KEY
          value: replaceme 
        - name: service_point 
          value: replaceme  
---
apiVersion: v1
kind: Service
metadata:
  name: image-classification-service 
spec:
  selector:
    app: image-classification 
  ports:
    - protocol: TCP
      port: 5001
      targetPort: 5001
```

As you see, the deployment gets the S3 credentials and endpoint url and creates a service listening to HTTP requests to start classifying the uploaded image. Now let's run this Deployment:
```bash 
oc create -f image-classification.yaml 


oc get pods | grep class
image-classification-6d557979cf-slvqf                           1/1     Running     0          2m
```

Great, now we have our classification service up and running, we'll have to create a bucket so we could create the notification configuration: 
```bash 
aws s3 mb s3://image-classification --endpoint-url http://rook-ceph-rgw-my-store-rook-ceph.apps-crc.testing
```

Now after we have our S3 bucket created, let's create the notification configuration using Notify tool that will help use in creating the wanted configuration: 
```bash 
git clone https://github.com/shonpaz123/notify.git && cd notify/openshift 
```

In here we we'll edit the notify.env file with the needed variables: 
```bash 
ACCESS_KEY=                # S3 access key 
SECRET_KEY=                # S3 secret key 
ENDPOINT_URL=              # S3 HTTP url 
BUCKET_NAME=               # Created S3 bucket name 
HTTP_ENDPOINT=             # The HTTP endpoint of our Flask service 
FILTER=                    # example: '{"Key": {"FilterRules": [{"Name": "suffix", "Value": ".jpg"}]}}'
FILTER_TYPE=suffix         # can contain prefix/suffix/regex/metadata/tags
``` 

After we insert the right values, we'll use Openshift ability of processing our input with templates. to create the job the configures the notification configuration: 
```bash 
oc process -f notify.yaml --param-file notify.env | oc create -f -
```

Let's verify out job has completed (the job pod name will be created by the FILTER_TYPE value in the notify.env file): 
```bash 
oc get pods | grep suffix
suffix-qnp5k                                                   0/1     Completed   0          3h59m
```

Now after we have all the infrastructure set up, let's try uploading a Pizza image and see if we will get a classification for that image. The uploaded image: 



Upload the image to our S3 bucket: 
```bash 
aws s3 cp pepperoni-pizza-thinly-sliced-popular-topping-american-style-pizzerias-30402134.jpg s3://image-classification --endpoint-url http://rook-ceph-rgw-my-store-rook-ceph.apps-crc.testing
``` 

Now let's check our Flask service logs to see if we have a result: 
```bash 
oc logs image-classifcation-6d557979cf-slvqf
.
.
.
2020-04-04 19:47:14,020 - {'0.003111549': 'honeycomb', '0.7704552': 'pizza, pizza pie', '0.0039080456': 'hognose snake, puff adder, sand viper', '0.0031275006': 'trifle', '0.0043221256': 'book jacket, dust cover, dust jacket, dust wrapper'}
2020-04-04 19:47:14,021 - 10.128.0.136 - - [04/Apr/2020 19:47:14] "POST / HTTP/1.1" 200 -
``` 

We can see the we've got a result saying there are 77% chances that the given image is a Pizza. 

# Conclusion 

As we saw it was quite easy running our ML pipeline using the right software solutions. using the mentioned products, we could create a self-managed envrionment that simplify the interaction with our infrastructure using Openshifts objectives. With these being said, we could create an intelligent self-managed data-centric environments with a click of a button. 
Hope you have enjoyed this demo, I'll see you in the next one :)
