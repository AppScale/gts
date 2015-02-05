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
PROVIDER=""
CURL="$(which curl)"
IP="$(which ip)"
APPSCALE_CMD="/usr/local/appscale-tools/bin/appscale"

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

# Check if we have the basic commands and environment available.
[ -x "${CURL}" ] || { echo "error: 'curl' not found!"; exit 1; }
[ -x "${IP}" ] || { echo "error: 'ip' not found!"; exit 1; }
[ -x "${APPSCALE_CMD}" ] || { echo "error: 'appscale' not found!"; exit 1; }
[ -d appscale ] || { echo "error: cannot find appscale on this image"; exit 1; }

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
PRIVATE_IP="$(ec2metadata --local-ipv4 2> /dev/null)"

# Let's try to detect the environment we are using.
if [ -n "$PUBLIC_IP" -a -n "$PRIVATE_IP" ]; then
    PROVIDER="AWS"
elif ${CURL} metadata.google.internal -i |grep Metadata-Flavor: Google ; then
    # As per https://cloud.google.com/compute/docs/metadata.
    PROVIDER="GCE"
else
    # Let's assume virtualized cluster.
    PROVIDER="CLUSTER"
fi

# Let's make sure we got the IPs to use in the configuration.
case "$PROVIDER" in 
"AWS" )
    # We have already discovered them.
    ;;
* )
    # Let's discover the device used for external communication.
    DEFAULT_DEV="$($IP route list scope global | sed 's/.*dev \b\([A-Za-z0-9_]*\).*/\1/')"
    [ -z "$DEFAULT_DEV" ] || { echo "error: cannot detect the default route"; exit 1; }
    # Let's find the IP address to use.
    PUBLIC_IP="$($IP addr show dev $DEFAULT_DEV scope global | sed -n 's;.*inet \([0-9.]*\).*;\1;p')"
    # There is no Private/Public IPs in this configuratio.
    PRIVATE_IP="$PUBLIC_IP"
    ;;
esac

# Let's make sure we detected the IPs.
[ -n "$PUBLIC_IP" ] || { echo "Cannot get public IP of instance!" ; exit 1 ; }
[ -n "$PRIVATE_IP" ] || { echo "Cannot get private IP of instance!" ; exit 1 ; }

# Tell the user what we detected.
echo "Detectd enviroment: ${PROVIDER}"
echo "Private IP found: ${PRIVATE_IP}"
echo "Public IP found:  ${PUBLIC_IP}"

# This is to create the minimum AppScalefile.
echo -n "Creating AppScalefile..."
echo "ips_layout :" > AppScalefile
echo "  controller : ${PRIVATE_IP}" >> AppScalefile
echo "login : ${PUBLIC_IP}" >> AppScalefile
echo "test : true" >> AppScalefile
#echo "admin_user : $ADMIN_EMAIL" >> AppScalefile
#echo "admin_pass : $ADMIN_PASSWD" >> AppScalefile
echo "done."

# Let's allow root login (appscale will need it to come up).
cat .ssh/id_rsa.pub >> .ssh/authorized_keys
ssh-keyscan $PUBLIC_IP $PRIVATE_IP 2> /dev/null >> .ssh/known_hosts

# Start AppScale.
${APPSCALE_CMD} up

# Download sample app.
echo -n "Downloading sample app..."
wget -q -O guestbook.tar.gz http://www.appscale.com/wp-content/uploads/2014/07/guestbook.tar.gz
echo "done."

# Deploy sample app.
${APPSCALE_CMD} deploy /root/guestbook.tar.gz
