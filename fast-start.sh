#!/bin/bash
#
# Get a single AppScale node on AWS: read more at
# www.appscale.com/get-started.
#
# It needs to be ran on an official AppScale image (you will find the AMI
# at https://github.com/AppScale/appscale/wiki/AppScale-on-Amazon-EC2).
# Once you have the IP of the instance you can do something like:
#
# ssh -i <key> ubuntu@<public IP> 'wget -q -O - https://raw.githubusercontent.com/obino/appscale/fast-start/fast-start.sh|sudo -i bash'
#
# author: graziano

# We need to be root. Usually we login as ubuntu, then sudo.
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
        ifconfig $x:0 $PUBLIC_IP > /dev/null 2> /dev/null
        if $? ; then
            echo "Couldn't set an alias for the public IP!"
            exit 1
        fi
        break
    fi
done

# create simple AppScalefile
echo "ips_layout :" > AppScalefile
echo "  controller : ${PUBLIC_IP}" >> AppScalefile
echo "test : True" >> AppScalefile

# allow root login
cat .ssh/id_rsa.pub >> .ssh/authorized_keys
ssh-keyscan $PUBLIC_IP 2> /dev/null >> .ssh/known_hosts

# bring appscale up
appscale up
