# Install Openshift Container Storage using the Local Storage Operator in a disconnected environemnt 

## Important Note 

Installing OCS in a disconnected environment is currently in a Development Preview, to do so you should contant Red Hat support to create a support exception for the installation phase. 
In this demo we will mirror all the needed data for OCS to be deployed using the LSO in a disconnected environment. 

## Prerequisites

* A running Openshift Cluster (+-1 with your Openshift Container Storage version) 
* A registry VM with internet access 

## Connected Environment 

### Create the Mirror Registry 

On the registry machine, let's install the needed wget package to pull the oc client:
 
```bash
$ yum install -y wget 
```

Pull the oc client, extract it and copy it as executable:

```bash
$ wget https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/openshift-client-linux.tar.gz
$ tar xvf openshift-client-linux.tar.gz
$ cp oc /bin/
```

Install the needed tools for you to spin up the mirror registry: 

```bash
$ yum -y install podman httpd-tools
```

Create the needed directories for the mirror registry:

```bash
$ mkdir -p /opt/registry/{auth,certs,data}
$ cd /opt/registry/certs
```

Let's create an answer file for the registry, which will be used to generate the certificate for out registry:

```bash
$ cat >csr_answer.txt << EOF
[req]
default_bits = 4096
prompt = no
default_md = sha256
distinguished_name = dn
[ dn ]
C=US
ST=New York
L=New York
O=MyOrg
OU=MyOU
emailAddress=me@working.me
CN = ${YOUR_REGISTRY_DNS_NAME}
EOF
```

Generate the certificate using the provided answer file: 
 
```bash
$ openssl req -newkey rsa:4096 -nodes -sha256 -keyout domain.key -x509 -days 1825 -out domain.crt -config <( cat csr_answer.txt )
```

Create an htpasswd login auhentication for your registry: 

```bash 
$ htpasswd -bBc /opt/registry/auth/htpasswd admin admin
```

Enable HTTP/HTTPS access to your registry:

```bash
$ export FIREWALLD_DEFAULT_ZONE=`firewall-cmd --get-default-zone`
$ firewall-cmd --add-service=https --zone=${FIREWALLD_DEFAULT_ZONE} --permanent
$ firewall-cmd --add-service=http --zone=${FIREWALLD_DEFAULT_ZONE} --permanent
```

Start your registry using Podman, the registry will listen in port 443, so no need to specifiy the registry port further more: 

```bash
$ podman run --name mirror-registry -p 443:5000 \ 
     -v /opt/registry/data:/var/lib/registry:z \
     -v /opt/registry/auth:/auth:z \
     -e "REGISTRY_AUTH=htpasswd" \
     -e "REGISTRY_AUTH_HTPASSWD_REALM=Registry Realm" \
     -e REGISTRY_AUTH_HTPASSWD_PATH=/auth/htpasswd \
     -v /opt/registry/certs:/certs:z \
     -e REGISTRY_HTTP_TLS_CERTIFICATE=/certs/domain.crt \
     -e REGISTRY_HTTP_TLS_KEY=/certs/domain.key \
     -e REGISTRY_COMPATIBILITY_SCHEMA1_ENABLED=true \
     -d docker.io/library/registry:2
```

Now let's add the created certificate to our trusted certificates and update the ca-trust so we could test our registry connection:

```bash
$ cp /opt/registry/certs/domain.crt /etc/pki/ca-trust/source/anchors/
$ update-ca-trust
$ curl -u admin:admin ${YOUR_REGISTRY_DNS_NAME}/v2/_catalog
```

Now let's base64 the registry password so we could add it to our pull-secret:

```bash
$ REG_SECRET=`echo -n 'admin:admin' | base64 -w0`
$ cat pull-secret.json | jq
$ export FQDN_REGISTRY="${YOUR_REGISTRY_DNS_NAME}"
$ cat pull-secret.json | jq '.auths += {"FQDN_REGISTRY": {"auth": "REG_SECRET","email": "me@working.me"}}' | sed "s/REG_SECRET/$REG_SECRET/" | sed "s/FQDN_REGISTRY/$FQDN_REGISTRY/" > pull-secret-bundle.json
$ cat pull-secret-bundle.json | jq
```

### Build redhat-operators Catalog

Now after we have finished with the registry configuration and we have the registry container running, let's start mirroring all the needed images for our installation: 

```bash
$ export AUTH_FILE="pull-secret-bundle.json"
$ export MIRROR_REGISTRY_DNS="${YOUR_REGISTRY_DNS_NAME}"
```

When we are using a disconnected Catalog, basically we should build the container image and push it to our registry. This image represents what we see in the 'Operatorhub` tab in the openshift console. 
Later on, we will create a catalogSource that will point to this container and will basically present all the operators that we have in our registry. Now let's build the catalog itself: 

```bash
$ oc adm catalog build --appregistry-org redhat-operators --from=registry.redhat.io/openshift4/ose-operator-registry:v4.4 \
               --to=${MIRROR_REGISTRY_DNS}/olm/redhat-operators:v1 --registry-config=${AUTH_FILE} \
               --filter-by-os="linux/amd64" --insecure 
```

This process takes the operator from the redhat-operators repository from the `registry.redhat.io` registry using the provided pull-secret and mirrors it into our catalog. The container image will be built and pushed into the mirror registry with the provided tag.

The OperatorHub object has a default configuration for sources it should pull the images from, since we are in a disconnected environment and we have no catalogSource, we'll just disable all the existing sources until we create the catalogSources in a later stage: 

```bash 
$ oc patch OperatorHub cluster --type json -p '[{"op": "add", "path": "/spec/disableAllDefaultSources", "value": true}]'
```

### Mirror only OCS and LSO operators 

Instead of mirroring all the redhat-operators repository (which is about ~70GB and could take about 5 hours to mirror), we could create a custom Catalog that will eventually contain only the operatos that we need for the OCS installation: 

```bash
$ git clone https://github.com/arvin-a/openshift-disconnected-operators.git && cd openshift-disconnected-operators
```

In this git repo, you'll find a `offline-operator-list` file which will contain all the needed operators for the OCS installation, please change the file as the following: 

```bash 	
local-storage-operator
ocs-operator
```

Now, make sure you have all the dependencies needed as mentioned in the git repo and then just mirror the needed images o you mirror registry: 

```bash
$ ./mirror-operator-catalogue.py \
--catalog-version 1.0.0 \
--authfile pull-secret-bundle.json \
--registry-olm ${YOUR_REGISTRY_DNS_NAME} \
--registry-catalog ${YOUR_REGISTRY_DNS_NAME} \
--operator-file ./offline-operator-list
```

This tool takes those operators and handles all the needed mirroring for you using Skopeo, eventually you will end up with having all the needed images for OCS and LSO mirrored to your registry.

### Add Related Images 

As for OCS4.4, it doest not contain all the needed relatedImages, so we'll have to manually mirror additional images so that the OCS CSV installation won't fail. To do so, save the following content into a `mapping-missing.txt` file, which will contain all the additional images that need to be mirrored: 

```bash
registry.redhat.io/openshift4/ose-csi-external-resizer-rhel7@sha256:e7302652fe3f698f8211742d08b2dcea9d77925de458eb30c20789e12ee7ae33=<your_registry>/openshift4/ose-csi-external-resizer-rhel7
registry.redhat.io/ocs4/ocs-rhel8-operator@sha256:78b97049b194ebf4f72e29ac83b0d4f8aaa5659970691ff459bf19cfd661e93a=<your_registry>/ocs4/ocs-rhel8-operator
quay.io/noobaa/pause@sha256:b31bfb4d0213f254d361e0079deaaebefa4f82ba7aa76ef82e90b4935ad5b105=<your_registry>/noobaa/pause
quay.io/noobaa/lib-bucket-catalog@sha256:b9c9431735cf34017b4ecb2b334c3956b2a2322ce31ac88b29b1e4faf6c7fe7d=<your_registry>/noobaa/lib-bucket-catalog
registry.redhat.io/ocs4/ocs-must-gather-rhel8@sha256:823e0fb90bb272997746eb4923463cef597cc74818cd9050f791b64df4f2c9b2=<your_registry>/ocs4/ocs-must-gather-rhel8
```

Now we'll use sed to change the target registry for the mirroring part to your registry DNS name: 

```bash 
$ sed -i 's/<your_registry>/${YOUR_REGISTRY_DNS_NAME}/g' mapping-missing.txt
```

After we have our file set up, let's start the mirroring: 

```bash
$ oc image mirror -f mapping-missing.txt --insecure --registry-config=${AUTH_FILE}
```

This command takes the sources of the images and pushed them into our mirror registry.

## Disconnected Environment Installation  

Basically, right now you have all the needed information and tools for you the use the installation in a disconnected location. You could just tar the `/opt/registry` directory and take the tarball with you, then untar it in your disconnected environment. This directory has all the needed images in the `data` directory, and can be easily spin up in the disconnected environment using the previous stages. 

Some things that might be useful:

* You will probably have to create the registry certficiate once again, with you new DNS name (you could also generate it with the target DNS name in advance). 
* If you create the htpasswd credentails again, don't forget to re-create the pull-secret-bundle.json file 
* Verify that your OCP nods have both network and DNS access to your registry

### Create An imageContentSourcePolicy 

In the `publish` directory, you will have `olm-icsp.yaml` that will be looking like this:

```bash
apiVersion: operator.openshift.io/v1alpha1
kind: ImageContentSourcePolicy
metadata:
  name: olm-image-content-source
spec:
  repositoryDigestMirrors:
  - mirrors:
    - ${YOUR_REGISTRY_DNS_NAME}
    source: registry.redhat.io
  - mirrors:
    - ${YOUR_REGISTRY_DNS_NAME}/ocs4
    source: registry.redhat.io/ocs4
  - mirrors:
    - ${YOUR_REGISTRY_DNS_NAME}/rhceph
    source: registry.redhat.io/rhceph
  - mirrors:
    - ${YOUR_REGISTRY_DNS_NAME}/noobaa
    source: quay.io/noobaa
  - mirrors:
    - ${YOUR_REGISTRY_DNS_NAME}/openshift4
    source: registry.redhat.io/openshift4
  - mirrors:
    - ${YOUR_REGISTRY_DNS_NAME}/rhscl
    source: registry.redhat.io/rhscl
```

This file will tell OCP which repos it should relate when trying to install all the OCS components. Each time you will create a storageCluster, OCP will convert the image with your registry's path. Don't forget to change the mirror to your registry DNS name!

Now, apply this file. This will trigger a MachineConfigPool change that will reboot all your nodes, the process should take about ~20 minutes.

```bash
$ oc apply -f publish/olm-icsp.yaml
$ watch "oc get nodes"
```

### Granting Pull Access To Your Mirror Registry 

To grant our OCP cluster the ability of pulling the needed images, we should first create a pull secret in our `openshift-marketplace` namespace using the pull-secret-bundle.json file that we have created previously: 

```bash 
$ oc project openshift-marketplace 
$ oc create secret generic pull-external-registry \
    --from-file=.dockerconfigjson=pull-secret-bundle.json \
    --type=kubernetes.io/dockerconfigjson
$ oc secrets link default pull-external-registry --for=pull
```

Now after we have the pull access, let's add our registry's certificate to the `additionalCATrust` of our cluster: 

```bash
$ oc create configmap registry-cas -n openshift-config --from-file=${YOUR_REGISTRY_DNS_NAME}=/opt/registry/certs/domain.crt
$ oc patch image.config.openshift.io/cluster --patch '{"spec":{"additionalTrustedCA":{"name":"registry-cas"}}}' --type=merge
```

### Creating the catalogSources

Now we can finally create out catalogSource that will eventually point for our OCS, lib-bucket-provisioner and LSO operators:

```bash
$ oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: CatalogSource
metadata:
  name: lib-bucket-catalogsource
  namespace: openshift-marketplace
spec:
  displayName: lib-bucket-provisioner
  icon:
    base64data: PHN2ZyBpZD0iTGF5ZXJfMSIgZGF0YS1uYW1lPSJMYXllciAxIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxOTIgMTQ1Ij48ZGVmcz48c3R5bGU+LmNscy0xe2ZpbGw6I2UwMDt9PC9zdHlsZT48L2RlZnM+PHRpdGxlPlJlZEhhdC1Mb2dvLUhhdC1Db2xvcjwvdGl0bGU+PHBhdGggZD0iTTE1Ny43Nyw2Mi42MWExNCwxNCwwLDAsMSwuMzEsMy40MmMwLDE0Ljg4LTE4LjEsMTcuNDYtMzAuNjEsMTcuNDZDNzguODMsODMuNDksNDIuNTMsNTMuMjYsNDIuNTMsNDRhNi40Myw2LjQzLDAsMCwxLC4yMi0xLjk0bC0zLjY2LDkuMDZhMTguNDUsMTguNDUsMCwwLDAtMS41MSw3LjMzYzAsMTguMTEsNDEsNDUuNDgsODcuNzQsNDUuNDgsMjAuNjksMCwzNi40My03Ljc2LDM2LjQzLTIxLjc3LDAtMS4wOCwwLTEuOTQtMS43My0xMC4xM1oiLz48cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik0xMjcuNDcsODMuNDljMTIuNTEsMCwzMC42MS0yLjU4LDMwLjYxLTE3LjQ2YTE0LDE0LDAsMCwwLS4zMS0zLjQybC03LjQ1LTMyLjM2Yy0xLjcyLTcuMTItMy4yMy0xMC4zNS0xNS43My0xNi42QzEyNC44OSw4LjY5LDEwMy43Ni41LDk3LjUxLjUsOTEuNjkuNSw5MCw4LDgzLjA2LDhjLTYuNjgsMC0xMS42NC01LjYtMTcuODktNS42LTYsMC05LjkxLDQuMDktMTIuOTMsMTIuNSwwLDAtOC40MSwyMy43Mi05LjQ5LDI3LjE2QTYuNDMsNi40MywwLDAsMCw0Mi41Myw0NGMwLDkuMjIsMzYuMywzOS40NSw4NC45NCwzOS40NU0xNjAsNzIuMDdjMS43Myw4LjE5LDEuNzMsOS4wNSwxLjczLDEwLjEzLDAsMTQtMTUuNzQsMjEuNzctMzYuNDMsMjEuNzdDNzguNTQsMTA0LDM3LjU4LDc2LjYsMzcuNTgsNTguNDlhMTguNDUsMTguNDUsMCwwLDEsMS41MS03LjMzQzIyLjI3LDUyLC41LDU1LC41LDc0LjIyYzAsMzEuNDgsNzQuNTksNzAuMjgsMTMzLjY1LDcwLjI4LDQ1LjI4LDAsNTYuNy0yMC40OCw1Ni43LTM2LjY1LDAtMTIuNzItMTEtMjcuMTYtMzAuODMtMzUuNzgiLz48L3N2Zz4=
    mediatype: image/svg+xml
  image: quay.io/noobaa/lib-bucket-catalog@sha256:b9c9431735cf34017b4ecb2b334c3956b2a2322ce31ac88b29b1e4faf6c7fe7d
  publisher: Red Hat
  sourceType: grpc  
EOF
```

Now let's create the catalogSource for the redhat-operators catalog (don't forget to change the image to your mirror registry!): 

```bash
$ oc create -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: CatalogSource
metadata:
  name: redhat-operators
  namespace: openshift-marketplace
spec:
  sourceType: grpc
  icon:
    base64data: PHN2ZyBpZD0iTGF5ZXJfMSIgZGF0YS1uYW1lPSJMYXllciAxIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxOTIgMTQ1Ij48ZGVmcz48c3R5bGU+LmNscy0xe2ZpbGw6I2UwMDt9PC9zdHlsZT48L2RlZnM+PHRpdGxlPlJlZEhhdC1Mb2dvLUhhdC1Db2xvcjwvdGl0bGU+PHBhdGggZD0iTTE1Ny43Nyw2Mi42MWExNCwxNCwwLDAsMSwuMzEsMy40MmMwLDE0Ljg4LTE4LjEsMTcuNDYtMzAuNjEsMTcuNDZDNzguODMsODMuNDksNDIuNTMsNTMuMjYsNDIuNTMsNDRhNi40Myw2LjQzLDAsMCwxLC4yMi0xLjk0bC0zLjY2LDkuMDZhMTguNDUsMTguNDUsMCwwLDAtMS41MSw3LjMzYzAsMTguMTEsNDEsNDUuNDgsODcuNzQsNDUuNDgsMjAuNjksMCwzNi40My03Ljc2LDM2LjQzLTIxLjc3LDAtMS4wOCwwLTEuOTQtMS43My0xMC4xM1oiLz48cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik0xMjcuNDcsODMuNDljMTIuNTEsMCwzMC42MS0yLjU4LDMwLjYxLTE3LjQ2YTE0LDE0LDAsMCwwLS4zMS0zLjQybC03LjQ1LTMyLjM2Yy0xLjcyLTcuMTItMy4yMy0xMC4zNS0xNS43My0xNi42QzEyNC44OSw4LjY5LDEwMy43Ni41LDk3LjUxLjUsOTEuNjkuNSw5MCw4LDgzLjA2LDhjLTYuNjgsMC0xMS42NC01LjYtMTcuODktNS42LTYsMC05LjkxLDQuMDktMTIuOTMsMTIuNSwwLDAtOC40MSwyMy43Mi05LjQ5LDI3LjE2QTYuNDMsNi40MywwLDAsMCw0Mi41Myw0NGMwLDkuMjIsMzYuMywzOS40NSw4NC45NCwzOS40NU0xNjAsNzIuMDdjMS43Myw4LjE5LDEuNzMsOS4wNSwxLjczLDEwLjEzLDAsMTQtMTUuNzQsMjEuNzctMzYuNDMsMjEuNzdDNzguNTQsMTA0LDM3LjU4LDc2LjYsMzcuNTgsNTguNDlhMTguNDUsMTguNDUsMCwwLDEsMS41MS03LjMzQzIyLjI3LDUyLC41LDU1LC41LDc0LjIyYzAsMzEuNDgsNzQuNTksNzAuMjgsMTMzLjY1LDcwLjI4LDQ1LjI4LDAsNTYuNy0yMC40OCw1Ni43LTM2LjY1LDAtMTIuNzItMTEtMjcuMTYtMzAuODMtMzUuNzgiLz48L3N2Zz4=
    mediatype: image/svg+xml
  image: ${YOUR_REGISTRY_DNS_NAME} 
  displayName: Redhat Operators Catalog
  publisher: Red Hat  
EOF
```

Now we can see that we have all the needed operators in the `OperatorHub` tab in the openshift console. From here you could use my previous blog on deploying OCS using the LSO regularly. 

### Operators Image 

## Conclusion 

So we have been through the process of mirroring all the needed catalogs and images for the OCS and LSO operators to operate in a disconnected environment. This process requires some manual work, but in later version, when disconnected environments installation of OCS will be supported (currently in Development Preview) the process will be easier. 
Hope you have enjoyed this demo, until the next time :)
