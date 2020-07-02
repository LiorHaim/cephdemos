
# Deploying a Containerized RHCS4.1 cluster 

Ceph is a distributed, unified software-defined storage solution, it can be the source of your relavant storage protocols by exposing block, file and object storage. Most of Ceph's installation today are being used as daemons treated as systemd services and can be started, stopped, reloaded, disabled, etc. With the massive adoption of microservices and container engines, Ceph daemons can be installed as containers too without causing any bottlenecks at all. Having Ceph running in containers increases management simplicity dramatically since containers are stateless and can be easily spawn up when having a failure. Even more than that, upgrading a containerized Ceph cluster will only require pulling the diffs from the newer container image. 

In this demo I'll show you how you can deploy a collocated containerized Ceph cluster using the `ceph-ansible` package. In our demo, OSD, Mon, Mgr and RGW daemons will be collocated within the same servers for simplicity, the only dedicated Virtual Machine will be the used for the Prometheus & Grafana deployment (can be collocated as well).  

## Prerequisites 

* 1 Ansible bastion running Ceph-ansible 
* 3 Virtual Machines used for Ceph's containers (Don't forget attach disks for the OSDs)
* 1 Virtual Machine used for Ceph's Prometheus & Grafana 
* Passwordless SSH configures between the bastion and the rest of the srevers 

**Note**: All VMs are running RHEL8.2 Operating System 

## Installation 

### Preparing the Deployer 


The Ansible deployer is responsible for running the ansible playbook that will deploy our Ceph cluster. This is why we need two main repositories when running our deployment: 

* ansible-2.8-for-rhel-8-x86_64-rpms - Will provide us the suitable `ansible` package 
* rhceph-4-tools-for-rhel-8-x86_64-rpms - Will provide us the relavent `ceph-ansible` package

To use those repositories, make sure you use the `subscription-manager` to enable those repositories: 

```bash 
$ subscription-manager register 
``` 

```bash 
$ subscription-manager attach --auto
``` 

```bash 
$ subscription-manager repos --enable ansible-2.8-for-rhel-8-x86_64-rpms
```

```bash 
$ subscription-manager repos --enable rhceph-4-tools-for-rhel-8-x86_64-rpms
``` 

After enabling the needed repos, let's install the packages needed for the deployment: 

```bash 
$ yum install -y ansible
```

```bash 
$ yum install -y ceph-ansible
```

### Setting Passwordless SSH 

We need the bastion to be able to SSH our machines without needing to type a password, in order to do so: 

```bash 
$  ssh-keygen -t rsa -b 4096 -N '' -f ~/.ssh/id_rsa
```

Now to copy the public key to all of your machines you could use: 

```bash 
ssh-copy-id <user>@<machine>
```

After we have configured Passwordless SSH, let's build our inverntory file to suite oue Ceph cluster deployment, in the `/etc/ansible/hosts`: 

```bash 
[mons]
ceph-osd1
ceph-osd2
ceph-osd3 

[mgrs]
ceph-osd1
ceph-osd2

[rgws:children]
mons 

[grafana-server]
ceph-grafana

[osds]
ceph-osd1
ceph-osd2
ceph-osd3
```

Now let's test our SSH connection using the ansible `ping` module: 

```bash 
$ ansible -m ping all

ceph-osd3 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
ceph-osd1 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
ceph-osd2 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
ceph-grafana | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

### Setting the installation files 

The ceph-ansible package holds all the installation files in the `/usr/share/ceph-ansible` directory. There you will find all the playbooks, roles, and vars files needed for the installation. We will use two files for the installation. 

First, change directory:

```bash 
cd /usr/share/ceph-ansible
```

#### Changing variables in the all.yml file 

The `group_vars/all.yml` file contains all the needed vars for us (except few vars for the OSDs), it contains a lot of variables but i'll sum up the minimal needed variables for the installation: 

```bash 
monitor_interface: eth0
public_network: x.x.x.x/x
cluster_network: x.x.x.x/x
radosgw_interface: eth0
radosgw_num_instances: 1
ceph_docker_image: "$REG/rhceph-4-rhel8"
ceph_docker_image_tag: "latest"
ceph_docker_registry: "$REG"
ceph_docker_registry_auth: true
ceph_docker_registry_username: "$REG_USER"
ceph_docker_registry_password: "$REG_PASSWORD"
containerized_deployment: True
dashboard_enabled: True
```

Simple as that, just search for each one of those vars in the `group_vars/all.yml` file and change them to suite your own environment. A little explanation on what each of those variables mean: 

* monitor_interface - The interface the Mon container will bind for its ip address and port 
* public_network - The front-facing network (can be collocated with the cluster network)
* cluster_network (optional) - The replication network for the OSDs (can be collocated with the public network)
* radosgw_interface - The interface the RGW container will bind for its ipaddress and port
* radosgw_num_instances (optional) - The number of RGW containers per server, default is 1
* ceph_docker_image & ceph_docker_image_tag: Choosing the ceph container image with the right version, the registry can be your own enterprise registry
* ceph_docker_registry_auth/username/password - In case you use credentials to login to your enterprise registry 
* containerized_deployment - Will determine whether the containerized auitable playbooks will run 
* dashboard_enabled - Will deploy Ceph's dashboard using the Mgr module 

After configurering the `group_vars/all.yml` file, Let's touch the second file needed to be changes. 

#### Changing variables in the osds.yml file 

The `group_vars/osds.yml` file contains all the needed vars regarding the OSDs deployment in our cluster, to make things simple, we'll use the automatic creation of our osds by letting the playbook create all the needed lvms for us. 

in the `group_vars/osds.yml` file change the following: 

```bash 
devices: 
- /dev/sdX
- /dev/sdY
```

This configuration will make the playbook take those disks, create lvms and then create OSDs upon those disks, so make sure you have the same disk labels on each server. This is assuming you have two disks per server, you can have more or less (supported 1 up to 36). 

### Running the playbook 

Now that we have the minimal configuration needed for our Ceph cluster deployment, let's run the installation playbook: 

```bash 
ansible-playbook site-container.yml
```

The playbook will start deploying our cluster, When the playbook finishes you'll see the following: 

```bash 
TASK [show ceph status for cluster ceph] *****************************************************************************************************************************************************
Thursday 02 July 2020  12:25:10 +0000 (0:00:01.088)       0:12:33.779 ********* 
ok: [ceph-osd1 -> ceph-osd1] => 
  msg:
  - '  cluster:'
  - '    id:     138a6332-2094-4b11-b4a1-be658e71e9c5'
  - '    health: HEALTH_OK'
  - ' '
  - '  services:'
  - '    mon: 3 daemons, quorum ceph-osd1,ceph-osd2,ceph-osd3 (age 9m)'
  - '    mgr: ceph-osd1(active, since 25s), standbys: ceph-osd2'
  - '    osd: 6 osds: 6 up (since 7m), 6 in (since 3w)'
  - '    rgw: 3 daemons active (ceph-osd1.rgw0, ceph-osd2.rgw0, ceph-osd3.rgw0)'
  - ' '
  - '  task status:'
  - ' '
  - '  data:'
  - '    pools:   7 pools, 448 pgs'
  - '    objects: 246 objects, 46 KiB'
  - '    usage:   60 GiB used, 424 GiB / 484 GiB avail'
  - '    pgs:     448 active+clean'
  - ' '
  - '  io:'
  - '    client:   1.2 KiB/s rd, 85 B/s wr, 1 op/s rd, 0 op/s wr'
  - ' '


```

Now we have our Ceph cluster up and running! let's verify that be executing a `ceph -s` coomand on one of our servers:

```bash 
$ ssh ceph-osd1
```

```bash 
$ podman exec -it ceph-mon-ceph-osd1 ceph -s

  cluster:
    id:     138a6332-2094-4b11-b4a1-be658e71e9c5
    health: HEALTH_OK
 
  services:
    mon: 3 daemons, quorum ceph-osd1,ceph-osd2,ceph-osd3 (age 11m)
    mgr: ceph-osd1(active, since 88s), standbys: ceph-osd2
    osd: 6 osds: 6 up (since 9m), 6 in (since 3w)
    rgw: 3 daemons active (ceph-osd1.rgw0, ceph-osd2.rgw0, ceph-osd3.rgw0)
 
  task status:
 
  data:
    pools:   7 pools, 448 pgs
    objects: 246 objects, 46 KiB
    usage:   60 GiB used, 424 GiB / 484 GiB avail
    pgs:     448 active+clean


```

Great! we see that the cluster is in `HELATH_OK` and we can start using it :) 

## Conclusion 

We saw how we can deploy a containerized Ceph cluster using the `ceph-ansible` package. The installation is quite easy and you can have you Ceph cluster ready in 20 minutes or so (depneding on your environment size). Hope you have enjoyed this demo, see ya next time :)