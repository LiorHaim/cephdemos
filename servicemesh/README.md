# Get you applicaiton fully observed, monitored, traced and secured using Openshift Service Mesh Operator 

In todays world, microservices architecture becomes more and more popular, lots of organizations are looking forward to move to those kinds of architectures ant put the monolithic approach behind. There are few challenges in moving to microservices approach, which mainly comes from the fact that the application has a lot of moving parts. When you have a monolithic application, you have all composed in one piece - easier to deploy, monitor, observe and secure. As microservices became very popular, container orchestration engines such as Kubernetes/Openshift has become very popular too, where each microservice is actually one pod (generally speaking), and all microservices libe in the Kubernetes cluster. When you have lots of small components, it is becoming harder to monitor, observe, trace and secure your applications. For example, you have an application and you customers suffer from high response time, how can you trace the problematic component? where do you start? 
This is why I wanted to talk you guys about the Serivce Mesh Operator. Coming with the latest versions of Openshift, you can observe, trace, secure and monitor your microservices application with only a few clicks, to do so we will use 4 operators that will come into hand: 

## Relevant Operators 

* Kiali - Responsible for observablity, will present the architecture, in real-time
* Jaeger - Responsible for tracing, will help us in finding the bottleneck with distributed tracing 
* Elasticsearch - Collects the requests, integrates with Jaeger for requests tracing 
* Service Mesh - The whole package, gathers all of the above into one CR, and provides the Istio management system 

## Bookinfo Application 

We will use the bookinfo application for our demonstration. Bookinfo is a versioned application, where each request will lead us to a different version of the application. By getting access to the productpage we will hit a different version of the reviews microservice for each page refresh, a sketch: 

########## bookinfo picture 


Let's start by getting into our openshift UI dashboard, and install those operators (I recommend using those who are provided by redhat). Install Elasticsearch, Kiali, Jaeger, Service Mesh operators, cluster-wise.

After you have installed those operators, go to `Installed operators` and you should see something like this:

################ Picture 

Now that we have out operators up and running, let's create a project for out Istio managemnt system. In this project, the Service Mesh operator will install all of its management components (such as Istio components, Kiali, Jaeger, Grafana): 

```bash
oc new-project istio-system
```

Now that we have our project, let's create a CR to create the management system of the Service Mesh operator, This CR will create all of the mentioned compnents: 

```bash 

oc create -f - <<EOF 
apiVersion: maistra.io/v1
kind: ServiceMeshControlPlane
metadata:
  name: basic-install
  namespace: istio-system
spec:
  version: v1.1
  istio:
    gateways:
      istio-egressgateway:
        autoscaleEnabled: false
      istio-ingressgateway:
        autoscaleEnabled: false
        ior_enabled: false
    mixer:
      policy:
        autoscaleEnabled: false
      telemetry:
        autoscaleEnabled: false
    pilot:
      autoscaleEnabled: false
      traceSampling: 100
    kiali:
      enabled: true
    grafana:
      enabled: true
    tracing:
      enabled: true
      jaeger:
        template: all-in-one

EOF
```

As you see, in the last rows, we can enable/disable the creation of kiali,grafana and jaeger. It means that the Service Mesh operator will create a CR to the other operators for us if we choose to enable it.
After we have created the CR, let's verify that our management system was fully installed:

```bash 

oc get pods 
                                                                                       
NAME                                      READY   STATUS    RESTARTS   AGE
grafana-5b6d886976-vnh5p                  2/2     Running   0          25s
istio-citadel-6784798885-x2dvr            1/1     Running   0          3m16s
istio-egressgateway-b8d7d6fcf-l7sck       1/1     Running   0          68s
istio-galley-7549bb654b-4h7rx             1/1     Running   0          2m22s
istio-ingressgateway-7f6fcf4bc9-h9krz     1/1     Running   0          68s
istio-pilot-75d4fdb54f-rd5td              2/2     Running   0          87s
istio-policy-7cb97db7c8-5fhzj             2/2     Running   0          2m3s
istio-sidecar-injector-866fccd4d9-ntxxw   1/1     Running   0          38s
istio-telemetry-6585f4479c-pq9b6          2/2     Running   0          2m3s
jaeger-6599dbb7c6-kd9cp                   2/2     Running   0          2m20s
kiali-694c9ff744-q4zm8                    1/1     Running   0          4m
prometheus-6df66d57cd-jbqrd               2/2     Running   0          2m51s
```

Great! we have Prometheus & Grafana for monitoring, Istio for service mesh, Kiali for observability and Jaeger for the distributed tracing. The whole stack in one CR!
So now that we have our management system, let's create and example application so we could see how our managemnt system reacts to it: 

```bash 
oc new-project bookinfo
```

Now let's create the actual CR, which will tell our `ServiceMeshControlPlane` that we have a candidate for it to manage, which is actually our bookinfo project. Once we will create this CR our management system will start managing the bookinfo project. It will inject Istio's sidecars and will start to collect information on out application:

oc create -f - <<EOF
apiVersion: maistra.io/v1
kind: ServiceMeshMemberRoll
metadata:
  name: default
  namespace: istio-system
spec:
  members:
    - bookinfo
EOF
```

Now let's create the actual application. The bookinfo application is a simple web-based application that is divided into few versions. With this application we'll see how we can use Istio to route the traffic evenly between the versions (emphasize canary deployment), how we can observe our architecture and trace requests and response time. 

```bash 
oc apply -n bookinfo -f https://raw.githubusercontent.com/Maistra/istio/maistra-1.1/samples/bookinfo/platform/kube/bookinfo.yaml -n bookinfo
```

Now let's verify our application is up and running: 

```bash 

oc get pods -n bookinfo
                                                                                        
NAME                              READY   STATUS    RESTARTS   AGE
details-v1-d7db4d55b-8sx24        2/2     Running   0          54s
productpage-v1-5f598fbbf4-v9q2j   2/2     Running   0          47s
ratings-v1-85957d89d8-slh99       2/2     Running   0          52s
reviews-v1-67d9b4bcc-2cdw2        2/2     Running   0          50s
reviews-v2-67b465c497-cjftq       2/2     Running   0          50s
reviews-v3-7bd659b757-brlnn       2/2     Running   0          49s
```

As you see we have 2 containers running in our pod where one is for the application and the other is Istio's sidecar injected when the application starts.
Now we'll create a gateway which will actually tell istio that we want to create and ingress rule for our application so that customers sohuld reach it outside of our Openshift cluster: 

```bash
oc apply -n bookinfo -f https://raw.githubusercontent.com/Maistra/istio/maistra-1.1/samples/bookinfo/networking/bookinfo-gateway.yaml -n bookinfo
```

Now' let's create destination rules for out services, basically those destination rules will determine how Istio will route its traffic among our microservices:

```bash
oc apply -n bookinfo -f https://raw.githubusercontent.com/Maistra/istio/maistra-1.1/samples/bookinfo/networking/destination-rule-all.yaml -n bookinfo
```

Great! we have out application fully productional, now let's create and infinite loop to so that we will have some basic traffic towards our application, this loop will try and giy the productpage which by default uses all the other services:

```bash 
while :; do curl -s $(oc get route -n istio-system | grep istio-ingressgateway | awk '{print $2}')/productpage | grep -o "<title>.*</title>"; sleep 1; done
```

Basically, we now have a client that performs requests to our productpage, this way we will start observing our application. For the observability part, we'll use Kiali, collect the Kiali route that has been created: 

```bash 
oc get routes -n istio-system | grep kiali | awk '{print $2}'
```

Now open your browser and paste the result to enter the Kiali dashboard. When we enter the Kiali dashboard we see that we have a summerized graph for each application that is being managed by our Service Mesh management system, click on `Graph` to observe your microservices architecture: 

###################### enter kiali picture

Now let's observe our architecture and start collecting some information on our `bookinfo` application: 

################ Graph picture 

As you see we have a full architecture of our application, in real-time where the routes are presented by precentages. We see that istio by default load balances the traffic evenly between our versions, which is very similar to what will happen if we refresh the page a few times (the stars under the reviews will change it's color from red to black to white). 

Now, if we'll navigate to `workloads` in the Kiali dashbboard, under `Metrics` we'll see that we have graphs that reflect the response time and the number of ops/s for the `details` microservice (we could do it for every microservice in our application). We can also click the `View in Grafana` link that will automatically route us the the relevant dashboard in Grafana where we could investigate further in case we have some problem. 

################## Kiali workloads picture 

Next, navigate to `Services` and click the `details` service, In addition to the graphs we saw earlier, we can also trace the requests for our service, so we get a mini Jaeger dashboard that shows us the response time for that specific service and one again we can click the `View in Tracing` link that will redirect us automatically to the Jaeger dashboard: 

################### Kiali service picture 


Now let's interact with the Jaeger dashboard, collect the endpoint for the dashboard: 

```bash 
oc get routes -n istio-system | grep jaeger | awk '{print $2}'
```

Now open your browser and paste the result to enter the Jaeger dashboard. When we enter it, we see that we have the left panel used for the query defintion, where we could filter by http status codes, response duration, and of course the microservice name. 

################ Jaeger query 

Choose the `productpage` under `service` anf hit `Find Traces`. You will see a graph that presents the response times for this specific microservice. Choose the highest dot and click on it, this will lead you 
to a graph shows how long each microservice took to respond: 

################## Jaeger graph 


After we saw how we can trace and observe our `bookinfo` application, let's see how we can dive into the performance dashboards provided out of the box by Grafana, collect the Grafana route: 

```bash 
oc get routes -n istio-system | grep grafana | awk '{print $2}'
```

Now open your browser and paste the result to enter the Grafana dashboard, browse your dashboards, you'll see that there a few dashboards that were loaded automatically: 

########################## Grafana General 

Click on the `Istio Mesh Dashboard` and verify that you see the dashboard relevant to our bookinfo application: 

####################### Grafana Mesh 


## A tip 

Sometimes performance problems are caused by resource stravation (RAM/CPU), if that is the case, you will only see the response time is high but you won't know why. To solve this problem you could use the central Grafana used for the Openshift cluster and comes as part of the installation: 

```bash 
oc get route -n openshift-monitoring | grep grafana | awk '{print $2}'
```

Open your browser and paste the result to enter the central Grafana dashboard. In your dashboards, use the `Compute resources / Namespace (Workloads)` dashboard: 

####################### Grafana central dash


Now change the namespace context to our `bookinfo` application and you'll see this: 

########################### Graph grafana RAMCPU

This way you could investigate performance problems better by getting a full observability of your application resources. 
Congratulations! you have observed, monitored, traced your application and installation took only a few clicks! 

## Conclusion 

We saw how we can use Kiali, Jaeger, Service Mesh and Grafana to get a full management system for our Openshift applications. We can keep up adding applications horizontally and our `ServiceMeshControlPlane` will do the same as it did to our `bookinfo` application. Hope you have enjoyed this demo, see ya next time :)

