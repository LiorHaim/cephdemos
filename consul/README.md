## Consul and Ceph's RGW for DNS resolving, Load-Balancing and Service Discovery

As we saw in the previous chapters, Ceph has become a major part of the big data world whether it's for archival, backup or data processing. One of Ceph's components, the Rados Gateway (RGW) provides a native S3 API for object storage. RGW itself combines frontend and backend, where the frontend handles HTTP requests (CIVETWEB), and the backend handles RADOS engine access. The RGW is a web server that can be horizontally scaled and this feature provides a lot of challenges mainly with load-balancing, service discovery and DNS resolving. It is very important to find the right solution when dealing with object storage services in on-premise cloud environments. Most of the solutions nowadays are made of few different products complicating infrastructure management and creating dependency (most of them are part of the data path, which means all client workloads are going through the load balancing layer, and we as DevOps Engineers will need to deal with scale-out more often). 
This is why I wanted to talk about Consul by Hashicorp. Consul provides load balancing, DNS resolving and service discovery in the same product. It is easy to use, and can be easily deployed on bare-metal/virtual machine/microservices infrastructure. Consul is not part of the data path and does it's resolving, discovery and load-balancing from the side. These features make Consul the lead product for integrating with Ceph's RGW webservers. In this demo, we'll make consul load balance, resolve and health check Ceph's RGWs. 

## Installation 
To run this demo, you should have a running Ceph cluster with at least two RGW instances. 

In my environment, I have used Vagrant and deployed the following: 
* 1 OSD server 
* 2 Mon/Mgr/RGW (collocated management plain) 

And my Consul server is located on my workstation, acessing both rgw servers with Virtualbox bridged network. 
* 1 Consul server (my workstation) 

Let's pull the consul docker image to run the consul server, to do so: 
```bash 
docker pull consul 
``` 

A short brief about Consul's objectives: 
* config.json - a file contains all the needed information for consul to run the server like domain, datacenter, dns server bind port, how many servers are in the cluster and who are they etc. 

* service.json - a json file contains the service definition, including health checks (in out demo for the rgw servers). 

We will deploy consul server with docker-compose, we'll have one consul server, a real production deployment should contain at least 3 servers for high availability. to those servers, you could configure DNS HA from you organization domain controller in case one of them gets unresponsive. 

Let's create a directory for consul's config files: 

```bash 
mkdir /etc/consul.d
``` 

Let's take a look on the config.json file:  

```bash 
{
  "datacenter": "dc1",
  "domain": "domain1",
  "data_dir": "/tmp/consul",
  "log_level": "INFO",
  "node_name": "consul101",
  "server": true,
  "bootstrap_expect": 1,
  "bind_addr": "0.0.0.0",
  "client_addr": "0.0.0.0",
  "advertise_addr": "<DOCKER_CONTAINER_IP>",
  "addresses": {
    "http": "0.0.0.0"
  },
  "ports": {
    "http": 80,
    "dns": 53
  }
}
``` 
The service definition file (This is for one server, to load balance create another one and change the id, ip and port): 

```bash 
{
  "service": {
    "id": "rgw01",
    "name": "s3",
    "address": "<RGW_IP>",
    "port": <RGW_PORT>,
    "check": {
      "http": "http://<RGW_IP>:<RGW_PORT",
      "interval": "10s",
      "timeout": "1s"
    }
  }
}
``` 


And the docker-compose file: 

```bash
version: '2'
services:
  consul01:
    image: docker.io/consul
    hostname: consul 
    network_mode: "host"
    restart: always
    environment:
      - CONSUL_BIND_INTERFACE=<DOCKER0_INTERFACE> 
      - CONSUL_ALLOW_PRIVILEGED_PORTS="8301"
    volumes:
      - /etc/consul.d:/etc/consul
    command: consul agent -ui -config-dir /etc/consul
``` 

Now, after you have copied the needed files to /etc/consul.d dir, we can start the Consul server: 

```bash 
docker-compose up -d 

  RequestsDependencyWarning)
       Name                     Command               State   Ports
-------------------------------------------------------------------
consuld_consul01_1   docker-entrypoint.sh consu ...   Up           
``` 

Now, Let's test out dns resolving by using the dig command, output should be as the following: 

```bash 
dig @127.0.0.1 s3.service.dc1.domain1

;; ANSWER SECTION:
s3.service.dc1.domain1.	0	IN	A	192.168.42.10
s3.service.dc1.domain1.	0	IN	A	192.168.42.11
``` 

As you see, i have directed the dns query to localhost since Consul DNS server runs on my computer, DNS query returned the two rgw's ip addresses. Now let's check we can accesess the rgws and we get the famoud xml: 

```bash 
curl s3.service.dc1.domain1:8080

<?xml version="1.0" encoding="UTF-8"?><ListAllMyBucketsResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Owner><ID>anonymous</ID><DisplayName></DisplayName></Owner><Buckets></Buckets></ListAllMyBucketsResult>
```
Great, now let's configure awscli to access this single url and see if we can upload objects (radosgw user was pre-created):

```bash 
export AWS_ACCESS_KEY_ID=**********
export AWS_SECRET_ACCESS_KEY=*********************
aws s3 mb s3://test --endpoint-url http://s3.service.dc1.domain1:8080
make_bucket: test
``` 
So we have managed to create a bucket, now let's upload few objects to our rgws: 

```bash 
for i in {1..10};do aws s3 cp /etc/hosts s3://test/$i --endpoint-url http://s3.service.dc1.domain1:8080;done
upload: ../../../etc/hosts to s3://test/1                          
upload: ../../../etc/hosts to s3://test/2                          
upload: ../../../etc/hosts to s3://test/3                          
upload: ../../../etc/hosts to s3://test/4                          
upload: ../../../etc/hosts to s3://test/5                          
upload: ../../../etc/hosts to s3://test/6                          
upload: ../../../etc/hosts to s3://test/7                          
upload: ../../../etc/hosts to s3://test/8                          
upload: ../../../etc/hosts to s3://test/9                          
upload: ../../../etc/hosts to s3://test/10   
``` 

So we have tested load balancing, and DNS resolving. Now let's test Consul's service discovery feature by shutting down one of the rgws as we upload objects and see if upload process crash (We'll run upload script and stop one of the rgw's service): 

```bash 
systemctl stop ceph-radosgw@rgw.rgw0.service 


for i in {1..30};do aws s3 cp /etc/hosts s3://test/$i --endpoint-url http://s3.service.dc1.domain1:8080;done
upload: ../../../etc/hosts to s3://test/1                          
upload: ../../../etc/hosts to s3://test/2                         
upload: ../../../etc/hosts to s3://test/3                          
upload: ../../../etc/hosts to s3://test/4                          
upload: ../../../etc/hosts to s3://test/5                          
upload: ../../../etc/hosts to s3://test/6                          
upload: ../../../etc/hosts to s3://test/7                          
upload: ../../../etc/hosts to s3://test/8                          
upload: ../../../etc/hosts to s3://test/9                          
upload: ../../../etc/hosts to s3://test/10                         
upload: ../../../etc/hosts to s3://test/11                         
upload: ../../../etc/hosts to s3://test/12                         
upload: ../../../etc/hosts to s3://test/13                         
upload: ../../../etc/hosts to s3://test/14                         
upload: ../../../etc/hosts to s3://test/15                         
upload: ../../../etc/hosts to s3://test/16                         
upload: ../../../etc/hosts to s3://test/17                         
upload: ../../../etc/hosts to s3://test/18                         
upload: ../../../etc/hosts to s3://test/19                         
upload: ../../../etc/hosts to s3://test/20                         
upload: ../../../etc/hosts to s3://test/21                         
upload: ../../../etc/hosts to s3://test/22                         
upload: ../../../etc/hosts to s3://test/23                         
upload: ../../../etc/hosts to s3://test/24                         
upload: ../../../etc/hosts to s3://test/25                         
upload: ../../../etc/hosts to s3://test/26                         
upload: ../../../etc/hosts to s3://test/27                         
upload: ../../../etc/hosts to s3://test/28                         
upload: ../../../etc/hosts to s3://test/29                         
upload: ../../../etc/hosts to s3://test/30  
``` 
As you see, upload process has fully completed, which means stopping one of the rgws didn't disrupt real time uploading. To verify: 

```bash 
dig @127.0.0.1 s3.service.dc1.domain1

;; ANSWER SECTION:
s3.service.dc1.domain1.	0	IN	A	192.168.42.11
```
## Conclustion 
As you see, we got only one of the rgw's address from consul because the other one crashed. 

As we saw, we have three main abilities needed when running s3 service in our private cloud, Consul provides all of these in only one simple deployment. These abilities and the fact Consul is not a part of the data path, unlock the complications in managing our s3 service. 




