# Git-Like Data Set Versioning using LakeFS and Ceph S3

Data has become the core business of every modern organization today, whether it's for decision making, reporting, predicting, analyzing and many other use cases that don't fall short. 
Eventually, Data, In it's final form will be presented to stakeholders in order for them to understand what happens in the organization, whether it's internally or externally. 

If we take AI as an example, We see that a lot of the assumptions being made by AI are the direct results of the data that the algorithm using. AI is using the datasets that are provided by Data Engineers in order to train models at scale, And those models will provide business recommendations and predictions that will be used by the stakeholders. 

You can surly understand that due to the presented above, The integrity of data is an important thing, It should be reliable enough for the AI model to base its theories on. 

We see that AI running on Kubernetes is not a joke, and a lot of workloads are being migrated towards Kubernetes as it treats AI models as they were microservices that are going through a CI/CD pipeline (using tools like MLOps, Kubeflow, etc). The source code is being saved into git repostories, gets pacakged into a container image, and eventually being deployed into Kubernetes as part of the data pipeline (using GitOps, CD, or any other deployment strategy). 

This empowers the control we have significantelly, As we can pormote or rollback specific versions of our AI models we have when problems occure (inaccuracy for example). 

Even more than that, We can now even control our dataset versions, And treat it as it was a git repository. By doing that, we control the versions that we hold as our data sets, So if for example a new data source was added and should be written to the data lake, we can branch the current dataset, Verify that the new data source isn't harmful (by running unit tests), and then merge the changes back to the origin and provide the tested data to our scientists or BI engineers.  

Today, We'll see how we could use `LakeFS` in order to version our data lake as it was a git repository. We'll use Ceph S3 as a data lake that will be directly attached to LakeFS as an S3 blockstore. 


## Prerequisites

* A Ceph cluster that exposes a RadosgW S3 interface 
* Docker-compose installed on your computer 


## Installation 

Let's create a radosgw user in order to interact with Ceph's S3 interface: 

```bash
radosgw-admin user create --uid=lakefs --display-name="Lakefs User" --access-key=lakefs --secret-key=lakefs
```

Next, we'll save Ceph's S3 configuration in Lakefs's config file, to make sure Lakefs uses Ceph as it's S3 blockstore: 

```bash
LAKEFS_CONFIG_FILE=./.lakefs-env
echo "AWS_ACCESS_KEY_ID=lakefs" > $LAKEFS_CONFIG_FILE
echo "AWS_SECRET_ACCESS_KEY=lakefs" >> $LAKEFS_CONFIG_FILE
echo "LAKEFS_BLOCKSTORE_S3_ENDPOINT=http://192.168.1.53:8080" >> $LAKEFS_CONFIG_FILE
echo "LAKEFS_BLOCKSTORE_TYPE=s3" >> $LAKEFS_CONFIG_FILE
echo "LAKEFS_BLOCKSTORE_S3_FORCE_PATH_STYLE=true" >> $LAKEFS_CONFIG_FILE
```

We'll deploy Lakefs using `docker-compose`, Which will deploy both Lakefs and Postgres to save data and metadata persistency: 

```bash
curl https://compose.lakefs.io | docker-compose --env-file $LAKEFS_CONFIG_FILE -f - up
``` 

Now that we have the LAkefs stack up and running, Let's create our S3 bucket, Which will be used by Lakefs to store versioned objects: 

```bash
aws s3 mb s3://lakefs/ --endpoint-url http://192.168.1.53:8080
make_bucket: lakefs
```

We now have all the infrastructure requirements ready, And we can create the actual repository: 

```bash
lakectl repo create lakefs://repo s3://lakefs -d main

Repository: lakefs://repo
Repository 'repo' created:
storage namespace: s3://lakefs
default branch: main
timestamp: 1625919817
```

As you see, this repository actually points to the created S3 bucket that was given as part of the S3 context in the configuration/ 
Let's make sure we can query that repository: 

```bash
lakectl repo list

+------------+-------------------------------+------------------+-------------------+
| REPOSITORY | CREATION DATE                 | DEFAULT REF NAME | STORAGE NAMESPACE |
+------------+-------------------------------+------------------+-------------------+
| repo       | 2021-07-10 15:23:37 +0300 IDT | main             | s3://lakefs       |
+------------+-------------------------------+------------------+-------------------+
```

Now, let's create a simple text file with a string within it, So that we could upload it to Lakefs: 

```bash
echo "My name is Shon Paz" >> txtfile.txt
```

Now we can upload the text file from the source given to our target repostiroy, in the `main` branch: 

```bash
lakectl fs upload -s txtfile.txt lakefs://repo/main/txtfile.txt

Path: txtfile.txt
Modified Time: 2021-07-10 15:24:35 +0300 IDT
Size: 20 bytes
Human Size: 20 B
Physical Address: s3://lakefs/84935fb66e4947338cb934d6318302db
Checksum: ad44412ae72bc202dcb12891111a1864
```

As you see, lakefs returnes the physical address of the S3 object itself, which means we could access it as any other S3 object with the given credentials. 
Now let's read the object's content to verify that it suits the content that we put in it: 

```bash
lakectl fs cat lakefs://repo/main/txtfile.txt

My name is Shon Paz
```

Like any other git repository, Once we have the files we want, we can commit our changes to the current branch we're in, So we'll commit this file to the 'main' branch:

```bash
lakectl commit -m "added one version of the txt file" lakefs://repo/main

Branch: lakefs://repo/main
Commit for branch "main" completed.

ID: 3a08e3da303b4b722d426cff458264b391c0209dacf9280b6bf5d73d0c92ff07
Message: added one version of the txt file
Timestamp: 2021-07-10 15:25:27 +0300 IDT
Parents: 7263176783ca345a7782d36ec14205b78a0f92b4956a4e93a0e704af32353052
```

Now that we have a stable version of our file located in Lakefs, Let's play with it a bit to create a second version: 
We'll add a line to the text file to create a second version of it in the next steps:

```bash
echo "And my last name is Paz" >> txtfile.txt
```

Now we'll create a new branch, used for the second version of the text file: 

```bash
lakectl branch create lakefs://repo/txtfile_change -s lakefs://repo/main

Source ref: lakefs://repo/main
created branch 'txtfile_change' 3a08e3da303b4b722d426cff458264b391c0209dacf9280b6bf5d73d0c92ff07
```

Let's make sure that the second branch was created: 

```bash
lakectl branch list lakefs://repo

+----------------+------------------------------------------------------------------+
| BRANCH         | COMMIT ID                                                        |
+----------------+------------------------------------------------------------------+
| main           | 3a08e3da303b4b722d426cff458264b391c0209dacf9280b6bf5d73d0c92ff07 |
| txtfile_change | 3a08e3da303b4b722d426cff458264b391c0209dacf9280b6bf5d73d0c92ff07 |
+----------------+------------------------------------------------------------------+
```

Great! we now have two branches under out Lakefs repository. 
Let's upload the updated file into our new branch: 

```bash
lakectl fs upload -s txtfile.txt lakefs://repo/txtfile_change/txtfile.txt

Path: txtfile.txt
Modified Time: 2021-07-10 15:26:57 +0300 IDT
Size: 44 bytes
Human Size: 44 B
Physical Address: s3://lakefs/cb9f5d4a125b421ea819c32a71b77e0a
Checksum: b25434f55350323f5f543ee0b92939bf
```

Next, We'll read the updated file's content and verify that we have the updated line: 

```bash 
lakectl fs cat lakefs://repo/txtfile_change/txtfile.txt

My name is Shon Paz
And my last name is Paz
```
Awsome! Now we'll commit the scond change into our newly created branch: 

```bash
lakectl commit -m "added second version of the txt file" lakefs://repo/txtfile_change

Branch: lakefs://repo/txtfile_change
Commit for branch "txtfile_change" completed.

ID: c25f69534a85da7b1afcc38ef293d57724c1e14a79e24e23aa7c8cdbab74336f
Message: added second version of the txt file
Timestamp: 2021-07-10 15:28:11 +0300 IDT
Parents: 3a08e3da303b4b722d426cff458264b391c0209dacf9280b6bf5d73d0c92ff07
```

Like in every git repository we have, Once we've validated our data set we can merge the changes! 
Let's merge the updated file from the newly created brnach (txtfile_change) into our main branch: 

```bash
lakectl merge lakefs://repo/txtfile_change lakefs://repo/main

Source: lakefs://repo/txtfile_change
Destination: lakefs://repo/main
Merged "txtfile_change" into "main" to get "a8b251a43e2e306e5dc170c05d0e83e289a0b162ff272d3a660c644e709b96f0".

Added: 0
Changed: 1
Removed: 0
```

We see that we get informed that changed has been merged and that one file was changes. 
Let's re-read the file from the `main` branch to verify that those changes were indeed merged: 

```bash
lakectl fs cat lakefs://repo/main/txtfile.txt

My name is Shon Paz
And my last name is Paz
```

## Conclusion 

We saw how we could use LakeFS's ability to treat Ceph's S3 blockstore as it was git repository. We've talked about the benefits this kind of ability could provide to our overall core business. Hope you have enjoyed this demo, See ya next time :)
