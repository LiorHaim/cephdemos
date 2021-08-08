# Install Openshift On A Single Node 

## Introduction 

As we all know the distributed cloud is already here. We see a lot of organizations trying to deploy their environments on multiple clouds, whether it's public, private or hybrid. 
Nowadays, a modern architecture won't include only central, massive clouds but multiple tiers starting from the central cloud to the edge, Where the foorprint is being reduced as the installation gets closer to an edge location. (For example Central Cloud --> 3-node Cluster --> A Single node --> IoT Devices).  

Those arcitectures are relevant to a lot of use cases we see today in the Industry such as AI, Telco, Manufacturing, Helathcare etc. 
That being said, we need to plan for the future and pick the right solution for the problem. As we are going distributed, we need those distributed clouds to be controlled in a simple, aligned and secured way. 

Today I wanted to share with you the simplicity of installing a Single Node Openshift, A thing that is very common when going distributed. It's important to say that a Single Node Openshift keeps the same API as every other Openshift cluster would, what makes it very easy to be controlled by central cloud management tools (such as ACM, will be covered in the next article). 

Let's get to work! 

## Prerequisistes 

* A Running VM for the Installation Preparation 
* A Running Openshift 4.8 Cluster 

## Installation 

On the bastion node, create a directory for hosting all the CLI tools needed for the installation: 

```
mkdir ocp4-install-sno && cd ocp4-install-sno
```

Once you are in the needed directory, make sure you download all the needed packages: 

```
#! /bin/bash 
wget https://mirror.openshift.com/pub/openshift-v4/clients/coreos-installer/v0.8.0-3/coreos-installer
wget https://mirror.openshift.com/pub/openshift-v4/dependencies/rhcos/latest/4.8.2/rhcos-4.8.2-x86_64-live.x86_64.iso
wget https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-install-linux.tar.gz
```

Now that you have the binaries, extract them and add execute permissions so you'll be able to use them:

```
chmod +x coreos-installer && tar xvf openshift-install-linux.tar.gz
```

Now, copy the following example for the `install-config.yaml` to your working directory. This file is being used by the Openshift installer to create the ignition file being used in the final Installation:

```bash 
apiVersion: v1
baseDomain: YOUR_BASE_DOMAIN
compute:
- hyperthreading: Enabled
  name: worker
  replicas: 0
controlPlane:
  hyperthreading: Enabled
  name: master
  replicas: 1
metadata:
  name: YOUR_CLUSTER_NAME
networking:
  clusterNetwork:
  - cidr: 10.128.0.0/14
    hostPrefix: 23
  networkType: OpenShiftSDN
  serviceNetwork:
  - 172.30.0.0/16
platform:
  none: {}
BootstrapInPlace:
  InstallationDisk: /dev/vda
pullSecret: 'YOUR_PULL_SECRET'
sshKey: 'YOUR_SSH_KEY'
```

Great, now that you have all set up, let's create the installation ISO! 
This ISO is being embedded with the Ignition file we've created before, and contains all the needed configuration for the installation. Once it's created, you can take the ISO and just boot the machine to it's installation. 

Now let's run a short script the will create the final ISO file for the installation: 

```bash 
#! /bin/bash 
./openshift-install --dir=. create single-node-ignition-config
./coreos-installer iso ignition embed -fi bootstrap-in-place-for-live-iso.ign rhcos-4.8.2-x86_64-live.x86_64.iso
```

Running this, we're creating the Ignition file for the configuration, then embedding it with the raw ISO in order to create the installation media. 

Awsome! we have all we need to boot the machine properly, let's move on for the installation part. 

### Configuring DNS, DHCP 

#### DHCP
 
Make sure you have registered your machine to your DHCP service in order for your machine to get the proper IP address. 

#### DNS

Make sure you have the following records available for the installer to resolve names: 

```bash 
* api.ocp-sno - (A Record) 
* api-int.ocp-sno - (A Record)
* *.apps.ocp-sno - (A Record)
* ocp-sno - (A + PTR Record)
``` 

Make sure you don't forget to give the proper PTR record for your host, or else the hostname won't be able to be pulled automatically, and the installation will fail. 

### Booting the SNO from ISO 

Just boot your VM/Bare Metal host from the created ISO and make sure you end up with the proper addresses and DNS names: 

####################### Picture 

Make sure you can SSH to your machine, this will show if the ignition configuration was inserted properly. You can also try the following command to see how the installation process is going (After SSHing to your node): 

```bash 
journalctl -b -f -u release-image.service -u bootkube.service
```

Now we just have to sit back in our chair and wait for the installation to complete, make sure you run the following command to get a status for your installation: 

```bash 
./openshift-install wait-for install-complete --log-level=debug
```


## Conclusion 

In the next few years, Most of our organization data will be processed at the edge to assure the best customer experience, Moving workloads to the edge has a lot of challenges such as security, compliance, version control, etc. 
With a Single Node Openshift being controlled by ACM, we can achieve that quite easily. 

Hope you've enjoyed this article, See ya next time :)
