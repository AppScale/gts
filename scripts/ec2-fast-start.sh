#!/bin/bash
#
# Get a single AppScale node on AWS: read more at
# www.appscale.com/get-started.
#
# It needs to be ran on an official AppScale image. For more information
# on the supported platform look at https://github.com/AppScale/appscale/wiki.
# Once you have the IP of the instance you can do something like:
#
# ssh -i <key> ubuntu@<public IP> 'wget -O - fast-start.appscale.com|sudo -i sh'
#
# author: graziano

ADMIN_EMAIL="a@a.com"
ADMIN_PASSWD="aaaaaa"

# Print help screen.
usage() {
        echo "Usage: $0 [--user <email> --passwd <password>]"
        echo
        echo "Options:"
        echo "  --user <email>          administrator's email"
        echo "  --passwd <password>     administrator's password"
        echo
}

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

# Parse command line.
while [ $# -gt 0 ]; do
    if [ "$1" = "-h" -o "$1" = "--help" -o "$1" = "-?" ]; then
        usage
        exit 0
    fi
    if [ "$1" = "--user" ]; then
        shift
        if [ -z "$1" ]; then
            usage
            exit 1
        fi
        ADMIN_EMAIL="$1"
        shift
        continue
    fi
    if [ "$1" = "--passwd" ]; then
        shift
        if [ -z "$1" ]; then
            usage
            exit 1
        fi
        ADMIN_PASSWD="$1"
        shift
        continue
    fi
    usage
    exit 1
done

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
echo -n "Creating AppScalefile..."
echo "ips_layout :" > AppScalefile
echo "  controller : ${PRIVATE_IP}" >> AppScalefile
echo "login : ${PUBLIC_IP}" >> AppScalefile
echo "test : True" >> AppScalefile
echo "admin_user : $ADMIN_EMAIL" >> AppScalefile
echo "admin_pass : $ADMIN_PASSWD" >> AppScalefile
echo "done."


# Let's allow root login (appscale will need it to come up).
cat .ssh/id_rsa.pub >> .ssh/authorized_keys
ssh-keyscan $PUBLIC_IP $PRIVATE_IP 2> /dev/null >> .ssh/known_hosts

# Start AppScale.
appscale up

# Download sample app.
echo -n "Downloading sample app..."
wget -q -O guestbook.tar.gz http://www.appscale.com/wp-content/uploads/2014/07/guestbook.tar.gz
echo "done."

# Deploy sample app.
appscale deploy /root/guestbook.tar.gz
