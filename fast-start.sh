#!/bin/bash
#
# Get a single AppScale node on AWS: read more at
# www.appscale.com/get-started.
#
# It needs to be ran on an official AppScale image (you will find the AMI
# at https://github.com/AppScale/appscale/wiki/AppScale-on-Amazon-EC2).
# Once you have the IP of the instance you can do something like:
#
# ssh -i <key> ubuntu@<public IP> 'wget -O - fast-start.appscale.com|sudo -i sh'
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

# Get the public and private IP of this instance.
PUBLIC_IP="$(ec2metadata --public-ipv4 2> /dev/null)"
if [ -z "$PUBLIC_IP" ]; then
    echo "Cannot get public IP of instance!"
    exit 1
fi
PRIVATE_IP="$(ec2metadata --local-ipv4 2> /dev/null)"
if [ -z "$PRIVATE_IP" ]; then
    echo "Cannot get private IP of instance!"
    exit 1
fi

# This is to create the minimum AppScalefile.
echo "ips_layout :" > AppScalefile
echo "  controller : ${PRIVATE_IP}" >> AppScalefile
echo "login : ${PUBLIC_IP}" >> AppScalefile
echo "test : True" >> AppScalefile

# Let's allow root login (appscale will need it to come up).
cat .ssh/id_rsa.pub >> .ssh/authorized_keys
ssh-keyscan $PUBLIC_IP $PRIVATE_IP 2> /dev/null >> .ssh/known_hosts

# Start AppScale.
appscale up
