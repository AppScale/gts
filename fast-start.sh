#!/bin/bash
#
# Get a single node on AWS
#
# author: graziano

# We need to be root.
if [ "$(id -u)" != "0" ]; then
    CMD=$(readlink -f $0)
    if ! sudo -i bash $CMD ; then
        exit 1
    else
        exit 0
    fi
fi

# Make sure this is an AppScale image.
if [ ! -d appscale ]; then
    echo "Cannot find appscale on this image!"
    exit 1
fi

# Get the public IP of this instance.
PUBLIC_IP="$(ec2metadata --public-ipv4 2> /dev/null)"
if [ -z "$PUBLIC_IP" ]; then
    echo "Cannot get public IP of instance!"
    exit 1
fi

# Create a virtual interface with this public IP.
for x in eth0 em0 eth1 em1 ; do
    if ifconfig $x > /dev/null 2> /dev/null; then
        ifconfig $x:0 $PUBLIC_IP
        break
    fi
done

# create simple AppScalefile
echo "ips_layout :" > AppScalefile
echo "  controller : ${PUBLIC_IP}" >> AppScalefile
echo "test : True" >> AppScalefile

# allow root login
cat .ssh/id_rsa.pub >> .ssh/authorized_keys
ssh-keyscan $PUBLIC_IP >> .ssh/known_hosts

# bring appscale up
appscale up
