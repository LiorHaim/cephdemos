# Deploy Ceph easily for functional testing, POCs and Workshops 

Ceph is a distributed, scalable storage system which is oftenly being used as an object, block and file storage. Today i'll talk about two deployment strategies of Ceph, that will help you with the following: 

* Dev functional testing - your developers can run a Ceph cluster on their own computer, which can ease on the development process and improve the developers experience since Ceph can be provisined as any other microservice. 

* New feature implementation - developers can test new upstream/downstream features on their own computers without having to interact with the production cluster.

* Infra functional testing - you can use a whole cluster deployment on your own computer to test some deep Ceph components such as the CRUSH map, OSDs, pools, etc.

* Workshops -  you can train other people by having them to run Ceph on their own computer, no need for real servers.

* POCs - you can deploy Ceph easily and be rest ensured that this behaviour will be the same in your production cluster.

## Prerequisites 

* Docker (19.03)
* Vagrant (2.27)
* Vagrant provider - Virtualbox(6.0)/Libvirt(4.5.0)
* Ansible (2.9.x)
* netaddr python (0.14.0)

## Single instance Ceph cluster

The simplest way to deploy a ceph cluster is to use docker, with this approach you can create a single container deployment when all Ceph daemons reside on this container. With a single command you can deploy a whole Ceph cluster used for functional testing. For example, if I have an on-premise Ceph cluster used for production Block, File and Object storage and I want each developer in my organization to have it's own experience when developing applications, I can deploy a single instance Ceph cluster for each one of my developers. 

To do so, we'll create a data directory where all the Ceph cluster information will be stored. After creating the data directory we'll run the docker container, which will run an entrypoint.sh script that will boostrap all the Cehp daemons, create radosgw-admin users, etc. The container images used can be both Upstream and Downstream, so if you want to use some of the new upstream features you can by using a different container image. 

To run the single instance Ceph cluster, first create the data directoris used for the Ceph deployments: 

```bash 
$ sudo mkdir -p /data/etc/ceph/ 
$ sudo mkdir -p /data/var/lib/ceph/
```

After the directory creation, let's run the container and test it's functionality: 

```bash 
$ sudo docker run -d --name demo -e MON_IP=192.168.1.37 -e CEPH_PUBLIC_NETWORK=192.168.1.37/32 --net=host \
-v /data/var/lib/ceph:/var/lib/ceph:z \
-v /data/etc/ceph:/etc/ceph:z -e CEPH_DEMO_UID=test-user \
-e CEPH_DEMO_ACCESS_KEY=test -e CEPH_DEMO_SECRET_KEY=test registry.redhat.io/rhceph/rhceph-4-rhel8 demo
```

Let's move on the arguments we pass to the ceph cluster: 

```bash 
MON_IP, CEPH_PUBLIC_NETWORK - pick an existing ip address to attach to the monitor, where the public network CIDR is /32 in my deployment to prevent an auto-attachment (Ceph will try to look for a suitable ip address by default). 

CEPH_DEMO_UID, CEPH_DEMO_ACCESS_KEY, CEPH_DEMO_SECRET_KEY - the entrypoint.sh script will create a radosgw-admin user with the provided access and secret keys
```

Notice that we use the downstram image version `registry.redhat.io/rhceph/rhceph-4-rhel8` but we could also use any upstream version to test some new features.
Now let's run the `ceph status` command to check out Ceph cluster's health: 

```bash 
$ sudo docker exec -it demo ceph status  
                                                                                                          
  cluster:
    id:     a54e3507-ea21-46cd-9c41-ea6014ef3ad4
    health: HEALTH_WARN
            mon spaz is low on available space
 
  services:
    mon:        1 daemons, quorum spaz (age 24s)
    mgr:        spaz(active, since 18s)
    mds:        cephfs:1 {0=demo=up:active}
    osd:        1 osds: 1 up (since 18s), 1 in (since 18s)
    rbd-mirror: 1 daemon active (4139)
    rgw:        1 daemon active (spaz)
 
  task status:
 
  data:
    pools:   7 pools, 56 pgs
    objects: 213 objects, 4.9 KiB
    usage:   1.0 GiB used, 9.0 GiB / 10 GiB avail
    pgs:     56 active+clean
 
  io:
    client:   54 KiB/s rd, 457 B/s wr, 80 op/s rd, 53 op/s wr
```

Great! now we have a running cluster, now let's test the object storage part where we have created the user and his credentials with the entrypoint.sh script: 
Configure the created access and secret keys: 

```bash 
$ export AWS_ACCESS_KEY_ID=test
$ export AWS_SECRET_ACCESS_KEY=test
```

Since our RGW listents on the host network, the RGW connection will be available through the `http://127.0.0.1:8080` address, lets create a bucket and upload some file:

```bash 
$ aws s3 mb s3://test --endpoint-url http://127.0.0.1:8080                                                                                         
make_bucket: test
```

```bash 
$ aws s3 cp /etc/hosts s3://test --endpoint-url http://127.0.0.1:8080                                                                             
upload: ../../etc/hosts to s3://test/hosts
```

```bash 
$ aws s3 ls s3://test --endpoint-url http://127.0.0.1:8080                                                                                       
2020-05-02 16:41:59        136 hosts
```

## Vagrant based Ceph cluster 

In addition to the container based deployment, we can use the Vagrant deployment to provide a more data-centric functional testing, instead of testing feature functionality, sometimes we need to perform a deeper test that touches the RADOS engine. For example, CRUSH map migrations, OSD backends replacement, pool protection strategies, mgr modules, etc. To do so, we can use the Vagrant provisioners engine to deploy a Ceph cluster based on one of the Vagrant providers (Virtualbox/Libvirt), this cluster will be deployed on Virtual Machines. 

After running the `vagrant up` command, Vagrant will run an Ansible provision task that will deploy our Ceph cluster automatically using `ceph-ansible`. First clone the git repository: 

```bash 
$ git clone https://github.com/ceph/ceph-ansible.git && cd ceph-ansible 
```

Now copy the vagrant_variables.yaml.sample file to your own :

```bash 
$ cp vagrant_variables.yml.sample vagrant_variables.yml
$ cp site.yml.sample site.yml
```

Now let's look at the file's structure to understand better how we can tune our deployment: 

```bash 
$ cat vagrant_variables.yml | grep -v "#"       
```

```bash                                                                     
---

docker: false

mon_vms: 3
osd_vms: 3
mds_vms: 0
rgw_vms: 0
nfs_vms: 0
grafana_server_vms: 0
rbd_mirror_vms: 0
client_vms: 0
iscsi_gw_vms: 0
mgr_vms: 0

public_subnet: 192.168.42
cluster_subnet: 192.168.43

memory: 1024

eth: 'eth1'

disks: [ '/dev/sdb', '/dev/sdc' ]

vagrant_box: centos/7
vagrant_sync_dir: /home/vagrant/sync

os_tuning_params:
  - { name: fs.file-max, value: 26234859 }

debug: false
```

We can control the number of VMs that will be deployed for each Ceph component, the public and cluster network CIDRs, the disks will be used for the OSDs, VMs memory, etc. A change in one of those parameters will automatically update the Vagrantfile in the deployment phase. Choose which Ceph components you want and let's start the deployment.

From the ceph-ansible directory: 

```bash 
$ sudo vagrant up --provision --provider=libvirt 
```

The deployment will create the machines, and will run the ansible playbook that will create the Ceph cluster. For a supported Downstream version of this deployment, you could use the following: 

```bash 
$ wget https://github.com/shonpaz123/ceph-tools/raw/master/ceph-ansible-rhcs_4.0.zip 
```

```bash 
$ unzip ceph-ansible-rhcs_4.0.zip
```

```bash 
$ cd ceph-ansible-rhcs-4-vagrant 
```

```bash 
$ ANSIBLE_ARGS='--extra-vars "rh_username=<changeme> rh_password=<changeme>"' vagrant up --provision --provider <changeme>
```

Notice that you should provide your rh username and password to download the supported packages, as in the previous step, the deployment will boot your machines and then will deploy the Ceph cluster  (mon,rgw,mgr are collocated). In addition, since this deployment provisions RHCS4.0 deployment, the Ansible version should be 2.8. 

Wait till the playbook finishes: 

```bash 
TASK [show ceph status for cluster ceph] ***************************************
Saturday 02 May 2020  18:20:20 +0300 (0:00:00.949)       0:23:12.692 ********** 
ok: [mon0 -> 192.168.121.244] => 
  msg:
  - '  cluster:'
  - '    id:     f9cd6ed1-5f37-41ea-a8a9-a52ea5b4e3d4'
  - '    health: HEALTH_WARN'
  - '            too few PGs per OSD (24 < min 30)'
  - ' '
  - '  services:'
  - '    mon: 1 daemons, quorum mon0 (age 7m)'
  - '    mgr: mon0(active, starting, since 0.396392s)'
  - '    mds: cephfs:1 {0=mon0=up:active}'
  - '    osd: 6 osds: 6 up (since 5m), 6 in (since 5m)'
  - '    rgw: 1 daemon active (mon0.rgw0)'
  - ' '
  - '  task status:'
  - ' '
  - '  data:'
  - '    pools:   6 pools, 48 pgs'
  - '    objects: 211 objects, 4.2 KiB'
  - '    usage:   6.0 GiB used, 288 GiB / 294 GiB avail'
  - '    pgs:     48 active+clean'
  - ' '
  - '  io:'
  - '    client:   767 B/s rd, 170 B/s wr, 0 op/s rd, 0 op/s wr'
  - ' '

PLAY RECAP *********************************************************************
client0                    : ok=101  changed=18   unreachable=0    failed=0    skipped=244  rescued=0    ignored=0   
mon0                       : ok=435  changed=77   unreachable=0    failed=0    skipped=523  rescued=0    ignored=0   
osd0                       : ok=147  changed=27   unreachable=0    failed=0    skipped=246  rescued=0    ignored=0   
osd1                       : ok=139  changed=26   unreachable=0    failed=0    skipped=237  rescued=0    ignored=0   
osd2                       : ok=140  changed=26   unreachable=0    failed=0    skipped=236  rescued=0    ignored=0 
```

Now we see that our cluster is healthy, in comparison to the previous step, now we have our components running on individual servers simulating the work in a real production cluster. To test our cluster, let's connect to the mon machine, and run the following script: 

```bash 
$ vagrant ssh mon0
$ sudo su -
```

```bash 
#! /bin/bash
yum install -y python-pip
pip install awscli 
radosgw-admin user create --uid test --display-name test-user --access-key test --secret-key test 
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
aws s3 mb s3://test --endpoint-url http://127.0.0.1:8080
aws s3 cp /etc/hosts s3://test --endpoint-url http://127.0.0.1:8080
```

Now let's see if the object was indeed created: 

```bash 
$ aws s3 ls s3://test --endpoint-url http://127.0.0.1:8080

2020-05-02 15:34:49        208 hosts
```

Great! it seems that our deployment works and our Ceph cluster is functional. 

## Conclusion 

We saw that Ceph can be deployed very easily using Docker and Vagrant. With the Docker deployment, we can test our Ceph clusters' behviour with some new features mainly for the gateways (RBD, RGW, CephFS). With the Vagrant deployment, we could test Ceph's core components and more complcated workloads. Home you have enjoyed this demo, have fun :)


