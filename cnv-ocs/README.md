# Virtual Machines or Containers? The answer is Both! 


As technologies emerge, and it seems that the words `microservices` and `DevOps` have become the answer for any technological problem, Organizations are putting a lot of effort in their automations, CI/CD pipelines, to improve their release lifecycle and gain competitive advantage while keep improving their code and enrich their feature set. 

CONTAINERS ARE'NT ALWAYS THE ANSWER!

Yes, I've just said it. We've became so exicted about microservices and containers, that we force this solution on every use case that we meet. 
Sometimes, the effort (in terms of time and money) that needs to be spent is so big, that it just doesn't worth the cost. Some use cases are better to stay monolithic, as there is no real advantage in moving away. 

That being said, assuming we have both VMs and containers in our organization, it is diffcult to have two different platforms to handle, and it's definetly easier to move to microservices approach when located on the same platform. 

This can save massive amounts of time and effort that needs to be put with improving the epmloyee skillbase, and as we already know TIME IS MONEY!

This is the reason why a new project has evolved in the community called `KubeVirt`. This project takes the advantages of Kubernetes and merges them with the abillity to run Virtual Machines. All well-known Kubernetes resources are now used in ordet to run VMs. Each VM that is being run under the KuberVirt operator management is actually represented as a Pod, that runs a libvirt process. 

We, In Red Hat started contributing to KubeVirt and allowed a downstream version of it now available via the Operator Hub. This operator is called `Openshift Virtualization`, and will be described in the following demo. Using OCS's abillity to provision many volumes, very fast using Copy-On-Write this solution fits to a whole. 

In this demo, I'll show you haw you can integrate both `Openshift Virtualization` and OCS in order to achieve a full ecosystem of a cloud-based virtual machine service on your premises! 

Let's get started!

 
## Prerequisistes

* Openshift 4.7.3 
* Openshift Virtualization 2.6 
* Openshift Container Storage 4.6

### Infrastructure Preparation 

In order to run Virtual Machines on our Openshift cluster, we need to install the `Openshift Virtualization` operator from the `Operator Hub`. Navigate to the `OperatorHub` tab --> `Openshift Virtualization` and click `Install`. 

######################################################333 Picture 

Once we have the operator installed, we need to create the `HyperConverged` custom resource in order to interact with the virtualization cluster. When created, pods will start running in the `openshift-cnv` namespace, where you could see all the needed services for running virtual machines on your Openshift cluster. 

######################################################333 Picture 


### Understanding Openshift Virtualization Basics

In order to create our new VM, let's create a new project that is called `my-ocpvirt`: 

```bash
$ oc new-project my-ocpvirt`
```

Verify that you are indeed in the correct project context: 

```bash 
$ oc project 
Using project "my-ocpvirt" on server "https://api.ocp.spaz.local:6443".
```

#### Creating A Boot Source 

Now that we have the project, let's start by creating a boot source. A boot source represents the way your VM will install its operating system, There are several ways to do so: 
* Using an ISO file, and mapping that ISO directly to the VM when it boots, as you would do with any other server
* Using a qcow2 file, that holds the operating system guest image so that the server will be able to boot up directly 

In the Demo, we'll be focusing on the latter option. 
There are several ways you could use a boot source in `Openshift Virtualization`:

* Import the guest image from an external http endpoint (generic http or object storage with public access) 
* Existing PVC where you have the qcow2 file stored 
* Extetnal registry (with public access) where you could pull the file the is stored as a container image 

As eventually we want to allow our users to have "golden image", we'll pre-create the boot source and upload the qcow2 guest image to a PVC with a function called `Data Upload`. 
This function allows us to upload the guest image file, and `Openshift Virtualization` will save it in a special namespace called `openshift-virtualization-os-images`. This PVC will be attached to an existing operating syste, for example `Red Hat Enteprise Linux 8.3`, And from that point each customer that is trying to create a RHEL8 VM will be using this guest image. 

Navigate to `Storage` --> `PersistentVolumeClaims` --> `Create PersistentVolumeClaim` --> `With Data Upload form`:


######################################################333 Picture 

Browse to your qcow2 file's location, and fill all the other needed values. It is very important to have the access mode in RWX with Block mode, so that the VM will be shared across nodes to survive a node aviction using `LiveMigration`. In case this won't be the configuration, RBD will not be able to allow the operating system PVC sharing across nodes. 

In addition, make sure that you tick the `Attach this data to a virtual machine OS` and attach it to RHEL8, so that it can be reusable. 

Hit `Upload`, and you'll see that you have a pod running with the name `cdi-upload-rhel8` which is responsible to upload the qcow2 file from your computer to a PVC: 

```bash
$ oc get pods -n openshift-virtualization-os-images

NAME                                               READY   STATUS    RESTARTS   AGE
cdi-upload-rhel8                             1/1     Running   0          87s
```

Once this pod exists, you could be rest assured that your boot source is ready to use! 


#### Creating A Virtual Machine From Template 

Verify the you have the boot source avaiable by navigating to `Virtualization` --> `Templates`: 

###########################3# templates picture 


If you see the `Boot Source` in `Available` mode, you are good to go! 


#### Creating our Virtual Machine 

Navigate to `Virtualization` --> `Create Virtual Machine` where you'll be redirected to select a template, choose one of the following and continue: 


################################# picture for choosing a template 

Choose your VM name, mine is called `my-rhel8-vm`, pick a flavor and hit the `Create Virtual Machine` button to create your VM. 
You can also customize your VM in order to add more disks, more network interfaces, add a `cloudInit` script but we'll save that for a different demo as this is a bit advanced and out of scope. 

Important! having multiple network interfaces for your VM can benefit when you need some advanced network capabilities such as SR-IOV, NAT, etc in order to allow a better performance/security. 

After creating the VM, you'll see your VM in the `Virtualization` tab and the VM will be in `Importing (CDI)` phase, where the qcow2 file is being imported to a newly created PVC in your namespace. 
Once this phase ends, your VM will start booting until it reaches a running state: 


############################## VM running picture


Great! now our VM is in running state, located in the propper namespace and scheduled on one of the workers. 
FYI, A virtual machine in Openshift is actually a Pod that runs a `libvirt` process that represents the virtual machine itself, all other computatinal such as disks, network drives, etc are attached via external kubernetes handling such as CNI and CSI. 

### Connecting to our VM via Console 

Click on the VM's name and navigate to `Console`, switch to `Serial Console` and then click on the `Show Password` button to verify your `cloud-user` password, Log-in to the VM: 


################################# picture for choosing a template 

#### Exposing Our VM To The Outside World 

In order to expose our vm to external access, we'll use the `virtctl` command-line that can be found here. 
Download and add it to your path, so you could start using it. It'll take your existing Kubernetes context and use it to find out all the related metadata. 

Verify your VM is existing and in running state: 

```bash
$ oc get vm

NAME          AGE   VOLUME
my-rhel8-vm   37m   
```

Now let's expose it: 

```bash
$ virtctl expose vm my-rhel8-vm --port=30825 --target-port=22 --name=my-rhel8-vm-ssh --type=NodePort
Service my-rhel8-vm-ssh successfully exposed for vm my-rhel8-vm
```

Now let's verify that the service was indeed created: 

```bash
$ oc get svc

NAME              TYPE       CLUSTER-IP       EXTERNAL-IP   PORT(S)           AGE
my-rhel8-vm-ssh   NodePort   172.30.109.240   <none>        30825:32471/TCP   3s
```

The exposure here is handled by a `NodePort` service, which maps a port located on the Openshift worker to the one the actual pod running the VM is using. Let's try to connecto via SSH: 


```bash
$ HYPERVISOR=$(oc get pods -o wide | awk '{print $7}' | grep -v NODE)

$ ssh -p 32471 cloud-user@$HYPERVISOR

cloud-user@ocp-worker01.spaz.local's password: 
Activate the web console with: systemctl enable --now cockpit.socket

Last login: Sun Apr 11 09:59:22 2021
[cloud-user@my-rhel8-vm ~]$ cat /etc/redhat-release 
Red Hat Enterprise Linux release 8.2 (Ootpa)
```

#### Migrate Our VM To a Different Hypervisor 

There cases where there are some node failures, or we should drain a node to be able to do some maintenance work. To allow contuinuity of our VM service, a live migration should be performed on all VMs located on that host to a different one in the Openshift cluster. 

Let's see how we can do that using `Openshift Virtualization`: 

################################################# GIF


## Conclusion 

We saw how we could use Openshift as a hosting platform for both containers and virtual machines. Openshift Virtualization is very useful for customers who are trying to have a unified solution for both virtualization and microservices (to ease on-the-job trainings and reuse man power) on their way to a fully-architected microservices approach, or customers who are trying to board legacy systems and containers on a single platform. 

Adding OCS's abillity to provision VMs fastly using Copy-On-Write and share volumes across nodes, this becomes an enriched virtualization platform that works side-by-side with containers.

I hope you've anjoyed reading, see ya next time :)  




