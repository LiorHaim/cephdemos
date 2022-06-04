# Deploy Your Virtualized Web Application Using Openshift Virtualization, Ansible, And MetalLB For A Pure IaC 

We all know that `Kubernetes` is the new OS for our datacenter, whether it's in cloud, on-premise or at the edge. 

Using the `Kubevirt.io` project, we can now deploy VMs on top of `Kubernetes` in addition to containers. 

This allows us to take advantage of the agility and protability of `Kubernetes` in our virtualized workloads as well, integrating with defacto standart automation APIs, such as `Ansible`. 

In the demo, I'd like to show how you can deploy and end-to-end virutalized web appllication and expose it to the outside world in a single click, in order to achieve a real infrastructure-as-code deployment on top of `Kubernetes`

So let's go :) 

## Prerequisites 

* A running Openshift cluster (4.10)
* Openshift Virtualization operator installed (4.10)
* MetalLB operator installed (4.10)
* A bastion server for running the IaC automation (RHEL 8.5)
* Ansible installed (2.9.27)


## Preparing The K8S Dynamic Inventory 

In this demo, we'll use the `K8S` dynamic inventory plugin for `Ansible`, that will allow us to query available resources in a given namespace on demand. 

To make sure that you configure it properly, make sure to use the `Ansible` [documentation](https://docs.ansible.com/ansible/latest/scenario_guides/kubernetes_scenarios/k8s_inventory.html).

Let's try to understand how this thing works in a high-level. 

Basically what happens, is that the `pip` package the we install, can be implemented to query a given namespace and return all the resources under that namespace. 

That way, as in other dynamic inventory plugins, if things change beneath the engine, we get all the latest updates. 

As Kubernetes is a dynamic orchestration layer, where resources tend to change often, we make sure that we work with all of the latest resources and not with stale ones. 

In order to make sure that you have configured your dynamic inventory plugin properly, make sure to create the following inventory file:

```bash 
$ cat hosts.k8s.yaml 

plugin: kubernetes.core.k8s
connections:
- namespaces:
    - test-vms
```

As you can see, I've given the plugin the wanted namespace to work on, and it returns all the resources under that namespace divided into `Ansible` groups: 

```bash 
$ ansible-inventory --list -i hosts.k8s.yaml | yq -P

_meta:
  hostvars: {}
all:
  children:
    - api-ocp-spaz-local_6443
    - ungrouped
api-ocp-spaz-local_6443:
  children:
    - namespace_test-vms
namespace_test-vms:
  children:
    - namespace_test-vms_pods
    - namespace_test-vms_services
```

## A High-Level Sketch 

Let's try to dive in and understand what we're trying to solve here. 

Basically, we want to deploy and end-to-end we application (basic httpd app), including all the resources that are needed underneath (The VMs, config management, load balancers, etc) so that our application acts properly in production. 

At the end, a single click will allow us to have this all configured. 

![HL Architecture Sketch](images/01-architecture-hl-sketch.jpg)


As you can see, we have the bastion server that deployes this whole magic, and interacts with our cluster API directly to query and create resources. 

Once the VM, and the LB for that VM are being created, the `Ansbile` host queries the resources using the dynamic inventory plugin to catch the VMs that were created and deploy the apache based application on top. 

Now that we have all of the theory set up, lets start writing some playbooks!

## Creating Resources Using Ansible K8S Module & Jinja2

In order to create all needed resources, we'll use the `Ansible K8S Module` that will allow us to interact with our `Openshift Cluster API` in order to create all of the needed resources. 

In addition, we'll use `Jinja2` to render variables dynamically at runtime, as our playbook runs. 


### Creating Virtual Machines 

In order to create a Virtal Machine, we'll interact with the `Openshift Virtualization` operator to create the proper custom resources. 


This automation ofcourse assumes that we have a `RHEL 8.5` template already imported to `Openshift Virtualization`, and ready to use. 

We'll create a custom resource called `VirtualMachine`, that defines the properties of the VMs that we want to deploy, including all of their needed configuration for installing the applications. 

```bash
$ cat vm-configuration.yaml.j2

apiVersion: kubevirt.io/v1
kind: VirtualMachine
metadata:
  labels:
    app: "{{ item }}"
    flavor.template.kubevirt.io/large: "true"
    os.template.kubevirt.io/rhel8.5: "true"
    vm.kubevirt.io/template: rhel8-server-large
    vm.kubevirt.io/template.namespace: openshift
    vm.kubevirt.io/template.revision: "1"
    vm.kubevirt.io/template.version: v0.19.4
    workload.template.kubevirt.io/server: "true"
  name: "{{ item }}"
  namespace: "{{ namespace }}"
spec:
  dataVolumeTemplates:
  - metadata:
      name: "{{ item }}-rootdisk-tk882"
    spec:
      source:
        pvc:
          name: rhel8
          namespace: openshift-virtualization-os-images
      storage:
        accessModes:
        - ReadWriteOnce
        resources:
          requests:
            storage: 20Gi
        storageClassName: ocs-external-storagecluster-ceph-rbd
  running: true
  template:
    metadata:
      annotations:
        vm.kubevirt.io/flavor: large
        vm.kubevirt.io/os: rhel8
        vm.kubevirt.io/workload: server
      labels:
        flavor.template.kubevirt.io/large: "true"
        kubevirt.io/domain: "{{ item }}"
        kubevirt.io/size: large
        os.template.kubevirt.io/rhel8.5: "true"
        vm.kubevirt.io/name: "{{ item }}"
        workload.template.kubevirt.io/server: "true"
    spec:
      domain:
        cpu:
          cores: 1
          sockets: 2
          threads: 1
        devices:
          disks:
          - disk:
              bus: virtio
            name: cloudinitdisk
          - bootOrder: 1
            disk:
              bus: virtio
            name: rootdisk
          interfaces:
          - name: default
            masquerade: {}
            model: virtio
          networkInterfaceMultiqueue: true
        resources:
          requests:
            memory: 8Gi
      evictionStrategy: LiveMigrate
      hostname: "{{ item }}"
      networks:
      - name: default
        pod: {}
      terminationGracePeriodSeconds: 180
      volumes:
      - cloudInitNoCloud:
          userData: |
            #cloud-config
            user: cloud-user
            password: 'xxxx'
            chpasswd:
              expire: false
            ssh_authorized_keys:
              - >-
                ssh-rsa
                AAAAB3NzaC1yc2E...
            hostname: "{{ item }}"
            bootcmd:
              - subscription-manager register --username=xxxx --password=xxxx
            packages:
             - httpd
             - python3

            runcmd:
              - [ systemctl, daemon-reload ]
              - [ systemctl, enable, httpd.service ]
              - [ systemctl, start, httpd.service ]
        name: cloudinitdisk
      - dataVolume:
          name: "{{ item }}-rootdisk-tk882"
        name: rootdisk
```

As you can see, we've created a `Jinja2` template that defines how each VM should look like. The `{{ item }}` field shows that we expect our playbook to run over those variables at runtime, we'll connect the dots later in this article. 

An important thing to look at is that we use `cloudinit` in order to configure the VM at startup. This `cloudinit` script will run when the VM boots, and will prepare all repositories, SSH keys, packages, etc. 

### Creating LB For Virtual Machines 

Now that we have the needed configuration for the Virtual Machines, we need to expose them outside of our cluster, so that end users will be able to access them. 

We'll use `MetalLB` operator, in order to create an external ip address for each one of our VMs. This address will be able to hop between nodes, so that if a node fails, the VM, including its floating IP will be able to move to another host and continue serving the application properly. 

```bash
$ cat vm-fip-configuration-yaml.j2 

apiVersion: v1
kind: Service
metadata:
  name: "{{ item }}"
  namespace: "{{ namespace }}"
  annotations:
    metallb.universe.tf/address-pool: example
spec:
  ports:
  - port: 22
    name: "ssh"
    targetPort: 22
  - port: 80
    name: "http"
    targetPort: 80
  selector:
    kubevirt.io/domain: "{{ item }}"
  type: LoadBalancer
```

Make sure that you have configures an `address pool` for your `MetalLB` operator, in your wanted scope so that it'll be able to give your VM a valid address. 

For each VM, we use the `{{ item }}` field as in the previous section, so that `MetalLB` will know how to find the VMs by their given names (which is basically the `kubevirt.io/domain` label that is given to each created VM automatically). 

The VM names will be passed in the `vars` section in our playbook later on. 

### Create The Application Web Page 

When VMs are up and running, we'll configure our apache based application on top, using a rendered `index.html` file that will point to the VM that in runs on. 

When the playbook runs, we'll run over the existing `index.html` file with the following: 

```bash 
<!DOCTYPE html>
<html>
   <head>
      <title>Openshift Virtualization Demo</title>
   </head>

   <body>
	   <h1>This is an Openshift Virtualization Demo on server {{inventory_hostname }} </h1>
      <img src="https://i.ytimg.com/vi/345uHQVwWic/maxresdefault.jpg" alt="Simply Easy Learning" width="1500"
         height="750">
   </body>
</html>
```

### Wrapping Things Up 

Now let's take a look at the main playbook that will use our created `Jinja2` templates: 

```bash
$ cat openshift-virtualization-iac-httpd.yaml

---
- hosts: localhost
  gather_facts: false
  serial: 1
  connection: local
  vars:
    vm_names:
    - app-server-1
    - app-server-2
    - app-server-3
    namespace: "test-vms"
  tasks: 
    - name: Create VMs using Kubernetes module
      kubernetes.core.k8s:
        template:
          path: 'vm-configuration.yaml.j2'
        state: present
      loop: "{{ vm_names }}"
    
    - name: Expose VMs to the outside world using MetalLB
      kubernetes.core.k8s:
        template:
          path: 'vm-fip-configuration-yaml.j2'
        state: present
      loop: "{{ vm_names }}"
    
    - name: Pause for 5 minutes to allow a proper VM creation
      pause:
        minutes: 12

- name: Deploy httpd based VMs using IaC w/ Openshift Virtualization 
  remote_user: cloud-user
  gather_facts: no
  serial: 1
  become: yes 
  hosts: namespace_test-vms_services

  tasks:
    - name: Verify that httpd package is installed 
      package:
        name: httpd
        state: present 
      check_mode: true

    - name: Copy index.html template to default httpd directory 
      template: 
        src: index.html.j2
        dest: /var/www/html/index.html

    - name: Retart httpd service to enable changes 
      service: 
        name: httpd 
        state: restarted 
```

As you can see, in the first phase we define variables (`vm_names` and `namespace`) that will be used in our `Jinja2` templates. When we loop on the `vm_names` variable, the `{{ item }}` field is being runover for each one of the created VMs. 

After we create all of the infrastructure resources, we wait for the `cloudinit` scipt to finish (can take a few minutes), and then we go to the second part of the playbook. 

In the second part, we rely on the dynamic inventory plugin to return the `namespace_test-vms_services` group as our hosts field, which will return the VM names for running the automation. 

Then, we use the `cloud-user` and the public SSH key that were created in the `cloudinit` sciprt that we passed to each one of the created VMs to connect to those VMs and run the application installation. 

**Important!** Make sure to have DNS names configured for those VMs as configured in the `vm_names` variable or else you wouldn't be able to connect to them via SSH

## Running The Automation 

In order to run the automation, we'll use the built in `Ansible` commands: 

```bash 
$ ansible-playbook openshift-virtualization-iac-httpd.yaml -i hosts.k8s.yaml
```

Make sure that the playbook has finished successfully: 

```bash
PLAY RECAP ***************************************************************************************************************************************
app-server-1               : ok=3    changed=2    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0   
app-server-2               : ok=3    changed=2    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0   
app-server-3               : ok=3    changed=2    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0   
localhost                  : ok=3    changed=1    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0   

```

And the all of the reousrces were created successfully as well, Let's starts with the VMs: 

```bash
$ oc get vms

NAME           AGE   STATUS    READY
app-server-1   19m   Running   True
app-server-2   19m   Running   True
app-server-3   19m   Running   True
```
And now let's verify that the external addresses were created as well: 

```bash
$ oc get svc 

NAME           TYPE           CLUSTER-IP       EXTERNAL-IP     PORT(S)                     AGE
app-server-1   LoadBalancer   172.30.142.171   192.168.1.157   22:32660/TCP,80:32187/TCP   13d
app-server-2   LoadBalancer   172.30.222.116   192.168.1.159   22:30241/TCP,80:32319/TCP   13d
app-server-3   LoadBalancer   172.30.92.174    192.168.1.160   22:30328/TCP,80:32655/TCP   13d
```

Now let's try to access our application using our web browser, we'll take `app-server-1` as example to see what's the output: 


![Deployed Application](images/02-show-app.png)

## Conclusion 

We saw that we can deploy an entire infrastructure, including a web application in a single click, all using the `Kubernetes` API. 

This brings a lot of agility and protability to our applications, in terms of integrations with new automation engines, and of course with other products in the `Kubernetes` ecosystem. 

Hope you've enjoyed this demo, See ya next time :) 