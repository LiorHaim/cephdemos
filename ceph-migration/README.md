# The beauty in Ceph's modularity 

Ceph is a distributed storage system, most of the people treat Ceph as it is a very complex system, full of components needed to be managed. Hard work and effort has been given to turn Ceph to what it is today, a portable, resilient, performent, self-healing storage system. With Ceph, you can easily have millions and billions of objects moving in the cluster to save the wanted state. The fact that Ceph is a Software Defined Storage system helps us in being more flexible with the hardware we choose, the operating system we pick and even the location the servers are in. For example, we can have a Ceph cluster running both RHEL and CentOS operating systems in a hybrid way, running on different racks or even geo-locations (not recommended). Today I want to talk with you guys on the beauty of Ceph's modularity, we'll see how we can move ~70,000 objects between servers running different OSD backends (TBD) live without having any "maintanace" window needed to be taken, we just move the data between servres while the cutomers can still continue working with our Ceph cluster. We'll see how we can throttle the migration process, improve our performance by using some new features, and eventually have our entire data located on a whole new set of servers located on a different location (can be a rack, a datacenter, or even a region).

## Prerequisites

* A running Ceph cluster (minimum luminous/RHCS3.0)

## Introsuction
First of all let's have a short recap on Ceph's compnents: 

* OSD - Object Storage Daemon, a process responsible for writing our data to the disk. usually 1:1 ratio between OSD process and a disk (each process writes and reads from one disk only).
* OSD Backend - Holds the information on how workloads performs against the disk, whether it's and LVM, an entire disk, or a partition that the OSD process needs to interact with. In earlier versions Filestore was used (was based on a Journal device used as a "persistent write cache" and a partition uses a whole disk for storing the data), and in the current versions Filestore is deprecated and Bluestore is being used (based on LVM, having no filesystem overhead by using block device for storing data and a dedicated lvm for storing metadata). 
* Objectstore API - an unified API, that provides the ability of running both Bluestore and Filestore OSDs in the same cluster sharing data. They are both using the same API, so data can be moved between them with no problem although they have a whole different bakcend implementations. 
* CRUSH map - responsible holding the location of every data component in the cluster, this map tells Ceph how it should treat our data, where it should store it, and what does it needs to do when a failure occures. 
* CRUSH rule - Tells Ceph which protection strategy to use (EC/Replica), where to store the data (which devices and servers) and how. 
* CRUSH bucket - A container that holds virtually a set of devices (hosts, racks, disks, datacenters, etc).

Let's start by looking on our OSD tree, showing us that we have 2 root buckets, which means that we have two seperated virtual containers in this cluster. I have added the `destination` root bucket and added 3 hosts where each host has 2 OSDs. These hosts contain Bluestore OSDs, while the `default` hosts contain Filestore OSDs, they'll use the Objectstore API to move data between them. 

```bash
$ ceph osd tree 

ID  CLASS WEIGHT  TYPE NAME        STATUS REWEIGHT PRI-AFF 
-15       0.28738 root destination                         
 -7       0.09579     host osd3                            
  2   hdd 0.04790         osd.2        up  1.00000 1.00000 
  8   hdd 0.04790         osd.8        up  1.00000 1.00000 
-11       0.09579     host osd4                            
  5   hdd 0.04790         osd.5        up  1.00000 1.00000 
  9   hdd 0.04790         osd.9        up  1.00000 1.00000 
 -9       0.09579     host osd5                            
  4   hdd 0.04790         osd.4        up  1.00000 1.00000 
 10   hdd 0.04790         osd.10       up  1.00000 1.00000 
 -1       0.28738 root default                             
 -3       0.09579     host osd0                            
  1   hdd 0.04790         osd.1        up  1.00000 1.00000 
  6   hdd 0.04790         osd.6        up  1.00000 1.00000 
-13       0.09579     host osd1                            
  0   hdd 0.04790         osd.0        up  1.00000 1.00000 
  7   hdd 0.04790         osd.7        up  1.00000 1.00000 
 -5       0.09579     host osd2                            
  3   hdd 0.04790         osd.3        up  1.00000 1.00000 
 11   hdd 0.04790         osd.11       up  1.00000 1.00000 
```

Let's create a pool, so that our OSDs will have some PGs distributed among them: 

```bash
$ ceph osd pool create bench 128 128  
pool 'bench' created
```

Now let's look a the first 6 OSDs (the `destination` hosts OSDs), we see that we have 0 PGs, which means they won't get any data when we will write to the cluster. This happens because the CRUSH rule tells Ceph to store data only on the `default` OSDs, we'll see it later: 

```bash
$ ceph osd df -f json-pretty | jq '.nodes[0:6][].pgs'
0
0
0
0
0
0
```

Now let's look at the second set of 6 OSDs (the `default` hosts OSDs), we see that we have pgs which means those OSDs will get data when we'll first write to the cluster:

```bash
$ ceph osd df -f json-pretty | jq '.nodes[6:12][].pgs'
83
77
68
92
76
84
```

Let's write some data to the cluster to fill it up a bit, we'll use the `rados bench` tool write 4KiB objects for 200 seconds without cleaning up the data after the writing process has finished:  

```bash 
$rados bench -p bench -o 4096 -t 16 200 write --no-cleanup
```

Now if we look at the cluster, we see that we have ~70,000 objects written to the cluster (don't mind the capacity, I had some data before starting this demo): 

```bash
$ ceph -s

  cluster:
    id:     6c701fa4-15b3-4276-b252-c22591ea5410
    health: HEALTH_OK
 
  services:
    mon: 1 daemons, quorum mon0 (age 53m)
    mgr: mon0(active, since 43m)
    osd: 12 osds: 12 up (since 49m), 12 in (since 49m)
    rgw: 1 daemon active (mon0.rgw0)
 
  task status:
 
  data:
    pools:   5 pools, 160 pgs
    objects: 68.64k objects, 267 MiB
    usage:   25 GiB used, 563 GiB / 588 GiB avail
    pgs:     160 active+clean
```

Let's create a new CRUSH rule, that says that data should reside on the root bucket called `destination`, the replica factor is the default (which is 3), the failure domain is host, and the device type is hdd (all of the device types are hdd in this demo, the only difference is the root bucket). Eventually, Ceph will use the `destination` root bucket resources to satisfy the end state. 
ceph osd crush rule create-replicated replicated_destination destination host hdd

Let's validate the new CRUSH rule has been created, and compare between the two. We see that under `item_name` we have a different root bucket to use. Of course creating this CRUSH rule won't do anything yet because the pool still used the old CRUSH rule: 

```bash 
$ ceph osd crush dump -f json-pretty | jq '.rules'

[
  {
    "rule_id": 0,
    "rule_name": "replicated_rule",
    "ruleset": 0,
    "type": 1,
    "min_size": 1,
    "max_size": 10,
    "steps": [
      {
        "op": "take",
        "item": -1,
        "item_name": "default~hdd"
      },
      {
        "op": "chooseleaf_firstn",
        "num": 0,
        "type": "host"
      },
      {
        "op": "emit"
      }
    ]
  },
  {
    "rule_id": 1,
    "rule_name": "replicated_destination",
    "ruleset": 1,
    "type": 1,
    "min_size": 1,
    "max_size": 10,
    "steps": [
      {
        "op": "take",
        "item": -16,
        "item_name": "destination~hdd"
      },
      {
        "op": "chooseleaf_firstn",
        "num": 0,
        "type": "host"
      },
      {
        "op": "emit"
      }
    ]
  }
]
```

Let's change bench's pool CRUSH rule, by changing this value we tell Ceph to move all the data from the old servers to the new servers, to be percised between the Filestore OSDs to the Bluestore ones: 

```bash 
$ ceph osd pool set bench crush_rule replicated_destination
set pool 5 crush_rule to replicated_destination
```

Let's look a the cluster's status to see if things has started to move:

```bash 
$ ceph -s 

  data:
    pools:   5 pools, 160 pgs
    objects: 68.64k objects, 267 MiB
    usage:   25 GiB used, 563 GiB / 588 GiB avail
    pgs:     0.625% pgs not active
             133332/205929 objects degraded (64.747%)
             70281/205929 objects misplaced (34.129%)
             124 active+recovery_wait+undersized+degraded+remapped
             32  active+clean
             2   active+recovering+undersized+remapped
             1   remapped+peering
             1   active+recovering+undersized+degraded+remapped
```

We see that there are object in `degraded` and `misplaces` state, which means that Ceph has come to understanding that the data should be moved to the new servers (don't mind the inactive PGs, I caught it in peering state). Now let's spin up the speed a little bit by telling Ceph to have more PGs migrating from the old servers to the new ones (this value throttles the migration of the PGs, so setting it to 1 will have the migration moving slowly so that customers will be much less impacted by the migration process): 

```bash 
$ ceph tell osd.* injectargs '--osd-max-backfills 10'

osd.0: osd_max_backfills = '10' 
osd.1: osd_max_backfills = '10' 
osd.2: osd_max_backfills = '10' 
osd.3: osd_max_backfills = '10' 
osd.4: osd_max_backfills = '10' 
osd.5: osd_max_backfills = '10' 
osd.6: osd_max_backfills = '10' 
osd.7: osd_max_backfills = '10' 
osd.8: osd_max_backfills = '10' 
osd.9: osd_max_backfills = '10' 
osd.10: osd_max_backfills = '10' 
osd.11: osd_max_backfills = '10' 
```

Let's verify that the data migration process has finished and the new servers are now holding the data:

```bash 
$ ceph -s

  cluster:
    id:     6c701fa4-15b3-4276-b252-c22591ea5410
    health: HEALTH_WARN
            application not enabled on 1 pool(s)
 
  services:
    mon: 1 daemons, quorum mon0 (age 2h)
    mgr: mon0(active, since 2h)
    osd: 12 osds: 12 up (since 2h), 12 in (since 2h)
    rgw: 1 daemon active (mon0.rgw0)
 
  task status:
 
  data:
    pools:   5 pools, 160 pgs
    objects: 68.64k objects, 267 MiB
    usage:   26 GiB used, 562 GiB / 588 GiB avail
    pgs:     160 active+clean
```

It seems like the cluster is in healthy state, let's verify that the new OSDs have the data: 

```bash 
$ ceph osd df -f json-pretty | jq '.nodes[0:6][].pgs'

81
79
76
84
88
72
```

Let's check it for the old servers too: 

```bash
$ ceph osd df -f json-pretty | jq '.nodes[6:12][].pgs'

0
0
0
0
0
0
```

Now that we have our data fully migrated, Let's use the `balancer` feature to create even distribution of the PGs amonf the OSDS. By default, the PGs are distributed with CRUSH between the OSDs so that each PG is backed up by a set of OSDS (depends on the protection strategy and the replica factor). Let's enable the balancer and create a plan: 

```bash 
$ ceph mgr module enable balancer
$ ceph balancer on 
$ ceph osd set-require-min-compat-client luminous set require_min_compat_client to luminous
$ ceph balancer mode upmap
$ ceph balancer off && ceph balancer on 
```

After enabling the automatic plan (balancer will run whenever it will reveal that there are imbalanced PGs in the cluster), let's check the balancer's status:

```bash 
$ ceph balancer status

{
    "last_optimize_duration": "0:00:00.003862", 
    "plans": [], 
    "mode": "upmap", 
    "active": true, 
    "optimize_result": "Optimization plan created successfully", 
    "last_optimize_started": "Wed May  6 15:30:07 2020"
}
```

After the distribution process has finised, we see that now we have an even number of PGs per OSD. This thing can improve your performance dramatically (eventually it will prevent imbalanced utilization of the disk and will create harmony): 

```bash 
$ ceph osd df -f json-pretty | jq '.nodes[0:6][].pgs'

80
80
80
80
80
80
```

Now after we have a perfect new environment, let's throw the old servers away. NO! the whole thing with software defined it we can re-use our hardware! let's scale out the new environemnt. To do so, I have runied the old servers, created Bluestore OSDs on them and added them to the cluster. Now let's move them into the `destination` root bucket: 

```bash 
ceph osd crush move osd0 root=destination
moved item id -3 name 'osd0' to location {root=destination} in crush map

ceph osd crush move osd1 root=destination
moved item id -13 name 'osd1' to location {root=destination} in crush map

ceph osd crush move osd2 root=destination
moved item id -5 name 'osd2' to location {root=destination} in crush map
```
After moving the servers, let's verify they were indeed transfered to the `destination` root bucket. By moving them into the new root bucket, Ceph will understand that it has new devices to use, so he will try to move the data to use those extra disks: 

```bash 
$ ceph osd tree 

ID  CLASS WEIGHT  TYPE NAME        STATUS REWEIGHT PRI-AFF 
-15       0.57477 root destination                         
 -3       0.09579     host osd0                            
  0   hdd 0.04790         osd.0        up  1.00000 1.00000 
  6   hdd 0.04790         osd.6        up  1.00000 1.00000 
-13       0.09579     host osd1                            
  3   hdd 0.04790         osd.3        up  1.00000 1.00000 
 11   hdd 0.04790         osd.11       up  1.00000 1.00000 
 -5       0.09579     host osd2                            
  4   hdd 0.04790         osd.4        up  1.00000 1.00000 
  9   hdd 0.04790         osd.9        up  1.00000 1.00000 
-11       0.09579     host osd3                            
  2   hdd 0.04790         osd.2        up  1.00000 1.00000 
  8   hdd 0.04790         osd.8        up  1.00000 1.00000 
 -7       0.09579     host osd4                            
  5   hdd 0.04790         osd.5        up  1.00000 1.00000 
 10   hdd 0.04790         osd.10       up  1.00000 1.00000 
 -9       0.09579     host osd5                            
  1   hdd 0.04790         osd.1        up  1.00000 1.00000 
  7   hdd 0.04790         osd.7        up  1.00000 1.00000 
 -1             0 root default                             
```

Not let's verify all 12 OSDs have PGs: 

```bash 
$ ceph osd df -f json-pretty | jq '.nodes[0:12][].pgs'

31
48
34
43
48
37
37
42
40
42
45
33
```

Great! but we haven't finished, let's take a few minutes and let the balancer do it's magic. After the balancer finishes, we see that we have out PGs distributed on more devices evenly. This thing will significantly help our performance because we have more spindles, more servers, and we have our workloads evenly distributed among those disks! 

```bash 
$ ceph osd df -f json-pretty | jq '.nodes[0:12][].pgs'

39
40
39
40
41
40
39
40
40
41
40
39
```

## Conclusion 

We saw how we can take adventage of Ceph's portability, replication and self-healing mechanisms to create an harmonic cluster moving data between locations, servers and OSD backends without the customer even have to know we play we their data. We also saw how we can tune performance by using the `balancer` feature and how we can throttle the migration process to prevent cutsomers performance issued. Hope this article has convienced you that Ceph is more than just a complex distributed storage system. Hope you have enjoyed this article, see you next time :)
