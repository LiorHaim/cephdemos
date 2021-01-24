mkdir -p /data/etc/ceph 
mkdir -p /data/var/lib/ceph

podman run -d --name demo -e MON_IP=192.168.1.56 -e CEPH_PUBLIC_NETWORK=192.168.1.56/32 --net=host \
-v /data/var/lib/ceph:/var/lib/ceph:z \
-v /data/etc/ceph:/etc/ceph:z -e CEPH_DEMO_UID=test-user \
-e CEPH_DEMO_ACCESS_KEY=HC8V2PT7HX8ZFS8NQ37R -e CEPH_DEMO_SECRET_KEY=Y6CENKXozDDikJHQgkbLFM38muKBnmWBsAA1DXyU registry.redhat.io/rhceph/rhceph-3-rhel7:3-48 demo

export AWS_ACCESS_KEY_ID=HC8V2PT7HX8ZFS8NQ37R
export AWS_SECRET_ACCESS_KEY=Y6CENKXozDDikJHQgkbLFM38muKBnmWBsAA1DXyU

aws s3 mb s3://music-chart-songs-store-changelog --endpoint-url http://192.168.1.56:8080
