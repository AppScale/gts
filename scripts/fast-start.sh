#!/bin/bash
#
# Get a single AppScale node on AWS: read more at
# www.appscale.com/get-started.
#
# It needs to be ran on an official AppScale image. For more information
# on the supported platform look at https://github.com/AppScale/appscale/wiki.
# Once you have the IP of the instance you can do something like:
#
# ssh -i <key> ubuntu@<public IP> 'curl -Lo - fast-start.appscale.com|sudo -i sh'
#

# On some systems, when running this script from rc.local (ie at boot
# time) there may not be any user set, which will cause ssh-copy-id to
# fail.  Forcing HOME to the default enables ssh-copy-id to operate
# normally.
export HOME="/root"

PATH="${PATH}:/usr/local/bin"
ADMIN_EMAIL=""
ADMIN_PASSWD=""
PROVIDER=""
CURL="$(which curl)"
IP="$(which ip)"
APPSCALE_CMD="$(which appscale)"
APPSCALE_UPLOAD="$(which appscale-upload-app)"
GOOGLE_METADATA="http://169.254.169.254/computeMetadata/v1/instance/"
GUESTBOOK_URL="https://www.appscale.com/wp-content/uploads/2017/09/guestbook.tar.gz"
GUESTBOOK_APP="${HOME}/guestbook.tar.gz"
MD5_SUMS="${HOME}/appscale/md5sums.txt"
USE_DEMO_APP="Y"
FORCE_PRIVATE="N"
AZURE_METADATA="http://169.254.169.254/metadata/v1/InstanceInfo"

# Print help screen.
usage() {
    echo "Usage: $0 [--user <email> --passwd <password>][--no-demo-app]"
    echo
    echo "Options:"
    echo "  --user <email>          administrator's email"
    echo "  --passwd <password>     administrator's password"
    echo "  --no-demo-app           don't start the demo application"
    echo "  --force-private         don't use public IP (needed for marketplace)"
    echo "  --no-metadata-server    don't try to contact metadata servers"
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
    if [ "$1" = "--no-demo-app" ]; then
        shift
        USE_DEMO_APP="N"
        continue
    fi
    if [ "$1" = "--force-private" ]; then
        shift
        FORCE_PRIVATE="Y"
        continue
    fi
    if [ "$1" = "--no-metadata-server" ]; then
        shift
        PROVIDER="CLUSTER"
        continue
    fi
    usage
    exit 1
done

# Sanity check on the given options.
if [ -n "$ADMIN_EMAIL" ]; then
    [ -n "${ADMIN_PASSWD}" ] || { echo "error: you need to specify password with admin email"; exit 1; }
else
    [ -z "${ADMIN_PASSWD}" ] || { echo "error: you need to specify admin email with password"; exit 1; }
fi

# Let's try to detect the environment we are using.
PUBLIC_IP=""
PRIVATE_IP=""

if [ -z "${PROVIDER}" ]; then
    if grep docker /proc/1/cgroup > /dev/null ; then
        # We need to start sshd by hand.
        /usr/sbin/sshd
        # Force Start cron
        /usr/sbin/cron
        PROVIDER="Docker"
    elif lspci | grep VirtualBox > /dev/null ; then
        PROVIDER="VirtualBox"
    elif ${CURL} -iLs metadata.google.internal |grep 'Metadata-Flavor: Google' > /dev/null ; then
        # As per https://cloud.google.com/compute/docs/metadata.
        PROVIDER="GCE"
    elif [ "$(${CURL} -s -o /dev/null -w "%{http_code}" $AZURE_METADATA)" = "200" ] ; then
        PROVIDER="Azure"
    else
        # Get the public and private IP of this instance.
        PUBLIC_IP="$(ec2metadata --public-ipv4 2> /dev/null)"
        PRIVATE_IP="$(ec2metadata --local-ipv4 2> /dev/null)"

        if [ "$PUBLIC_IP" = "unavailable" ]; then
            PUBLIC_IP=""
        fi
        if [ "$PRIVATE_IP" = "unavailable" ]; then
            PRIVATE_IP=""
        fi

        if [ -n "$PUBLIC_IP" -a -n "$PRIVATE_IP" ]; then
            PROVIDER="AWS"
        else
            # Let's assume virtualized cluster.
            PROVIDER="CLUSTER"
        fi
    fi
fi

# Let's make sure we got the IPs to use in the configuration.
case "$PROVIDER" in
"AWS" )
    # Set variables for AWS. We already have the IPs.
    ADMIN_PASSWD="$(ec2metadata --instance-id)"
    ADMIN_EMAIL="a@a.com"
    ;;
"GCE" )
    # We assume a single interface here.
    PUBLIC_IP="$(${CURL} -sH 'Metadata-Flavor: Google' ${GOOGLE_METADATA}/network-interfaces/0/access-configs/0/external-ip)"
    PRIVATE_IP="$(${CURL} -sH 'Metadata-Flavor: Google' ${GOOGLE_METADATA}/network-interfaces/0/ip)"
    # Let's use a sane hostname.
    ${CURL} -Lo /tmp/hostname -sH "Metadata-Flavor: Google" ${GOOGLE_METADATA}/hostname
    cut -f 1 -d '.' /tmp/hostname > /etc/hostname
    hostname -b -F /etc/hostname
    # Set admin user email and password.
    ADMIN_EMAIL="$(${CURL} --fail -sH "Metadata-Flavor: Google" ${GOOGLE_METADATA}/attributes/adminUser)"
    ADMIN_PASSWD="$(${CURL} --fail -sH "Metadata-Flavor: Google" ${GOOGLE_METADATA}/attributes/appscale_user_password)"
    if [ -z "$ADMIN_PASSWD" ]; then
        echo "Google Cloud Launcher context missing. Using Google Compute Engine defaults."
        ADMIN_EMAIL="a@a.com"
        ADMIN_PASSWD="$(cat /etc/hostname)"
    fi
    ;;
"VirtualBox")
    # Let's discover the device used for external communication. In
    # Vagrant this should not be used!
    DEFAULT_DEV="$($IP route list scope global | sed 's/.*dev \b\([A-Za-z0-9_]*\).*/\1/' | uniq)"
    # Let's find the IP address to use.
    for device in $($IP route list scope link | awk '{print $3}') ; do
        if [ ${device} != ${DEFAULT_DEV} ]; then
            PUBLIC_IP="$($IP addr show dev ${device} scope global | sed -n 's;.*inet \([0-9.]*\).*;\1;p')"
            break
        fi
    done
    PRIVATE_IP="$($IP addr show dev ${DEFAULT_DEV} scope global | sed -n 's;.*inet \([0-9.]*\).*;\1;p')"
    ;;
"Azure")
    DEFAULT_DEV="$($IP route list scope global | sed 's/.*dev \b\([A-Za-z0-9_]*\).*/\1/' | uniq)"
    PUBLIC_IP="$(wget http://ipinfo.io/ip -qO -)"
    PRIVATE_IP="$($IP addr show dev ${DEFAULT_DEV} scope global | sed -n 's;.*inet \([0-9.]*\).*;\1;p')"
    ADMIN_EMAIL="a@a.com"
    ADMIN_PASSWD="$(cat /etc/hostname)"
    ;;
"CLUSTER"|"Docker")
    ADMIN_EMAIL="a@a.com"
    ADMIN_PASSWD="appscale"
    # Let's discover the device used for external communication.
    DEFAULT_DEV="$($IP route list scope global | sed 's/.*dev \b\([A-Za-z0-9_]*\).*/\1/' | uniq)"
    [ -z "$DEFAULT_DEV" ] && { echo "error: cannot detect the default route"; exit 1; }
    # Let's find the IP address to use.
    PUBLIC_IP="$($IP addr show dev ${DEFAULT_DEV} scope global | sed -n 's;.*inet \([0-9.]*\).*;\1;p')"
    # There is no private/public IPs in this configuration.
    PRIVATE_IP="${PUBLIC_IP}"
    ;;
* )
    echo "Couldn't detect infrastructure ($PROVIDER)"
    exit 1
    ;;
esac

# Let's make sure we don't overwrite and existing AppScalefile.
if [ ! -e AppScalefile ]; then
    # Let's make sure we detected the IPs.
    [ -z "$PUBLIC_IP" ] && { echo "Cannot get public IP of instance!" ; exit 1 ; }
    [ -z "$PRIVATE_IP" ] && { echo "Cannot get private IP of instance!" ; exit 1 ; }

    # Tell the user what we detected.
    echo "Detected enviroment: ${PROVIDER}"
    echo "Private IP found: ${PRIVATE_IP}"
    echo "Public IP found:  ${PUBLIC_IP}"

    # This is to create the minimum AppScalefile.
    echo -n "Creating AppScalefile..."
    echo "ips_layout :" > AppScalefile
    echo "  -" >> AppScalefile
    echo "    roles:" >> AppScalefile
    echo "      - master" >> AppScalefile
    echo "      - compute" >> AppScalefile
    echo "      - database" >> AppScalefile
    echo "      - zookeeper" >> AppScalefile
    echo "    nodes: ${PRIVATE_IP}" >> AppScalefile
    if [ "${FORCE_PRIVATE}" = "Y" ]; then
        echo "login : ${PRIVATE_IP}" >> AppScalefile
    else
        echo "login : ${PUBLIC_IP}" >> AppScalefile
    fi
    if [ -z "${ADMIN_EMAIL}" ]; then
        echo "test : true" >> AppScalefile
    else
        echo "admin_user : $ADMIN_EMAIL" >> AppScalefile
        echo "admin_pass : $ADMIN_PASSWD" >> AppScalefile
    fi
    echo "group : faststart-${PROVIDER}" >> AppScalefile
    echo "done."

    # Let's allow root login (appscale will need it to come up).
    mkdir -p "${HOME}/.ssh"
    chmod 700 "${HOME}/.ssh"

    # Create an SSH key if it does not exist, and allow for local ssh
    # passwordless operations.
    test -e "${HOME}/.ssh/id_rsa.pub" || ssh-keygen -q -t rsa -f "${HOME}/.ssh/id_rsa" -N ""
    cat "${HOME}/.ssh/id_rsa.pub" >> "${HOME}/.ssh/authorized_keys"
    chmod 600 "${HOME}/.ssh/authorized_keys"

    # Make sure the localhost is known to ssh.
    if [ -e "${HOME}/.ssh/known_hosts" ]; then
      ssh-keygen -R $PUBLIC_IP
      ssh-keygen -R $PRIVATE_IP
    fi
    ssh-keyscan $PUBLIC_IP $PRIVATE_IP 2> /dev/null >> "${HOME}/.ssh/known_hosts"

    # Download sample app.
    if [ ! -e ${GUESTBOOK_APP} ]; then
      echo "Downloading sample app."
      ${CURL} -Lso ${GUESTBOOK_APP} ${GUESTBOOK_URL}
      if ! md5sum -c ${MD5_SUMS} ; then
        echo "Failed to get sample app (md5 check failed)!"
        echo "Removing sample app tarball and disabling starts of sample app."
        rm -f ${GUESTBOOK_APP}
        USE_DEMO_APP="N"
      fi
    fi
else
    # If AppScalefile is present, do not redeploy the demo app.
    USE_DEMO_APP="N"
fi

# Start AppScale.
${APPSCALE_CMD} up

# We need to set the login after AppScale is up for marketplace.
if [ "${FORCE_PRIVATE}" = "Y" ]; then
    ${APPSCALE_CMD} set login ${PUBLIC_IP}
fi

# If we don't need to deploy the demo app, we are done.
if [ "${USE_DEMO_APP}" != "Y" ]; then
    exit 0
fi

# Get the keyname.
KEYNAME=$(grep keyname "${HOME}/AppScalefile" | cut -f 2 -d ":")
[ -z "${KEYNAME}" ] && { echo "Cannot discover keyname: is AppScale deployed?" ; exit 1 ; }

# Deploy sample app.
[ -z "${ADMIN_EMAIL}" ] && ADMIN_EMAIL="a@a.com"
[ -e ${GUESTBOOK_APP} ] && ${APPSCALE_UPLOAD} --keyname ${KEYNAME} --file ${GUESTBOOK_APP}

# Relocate to port 80.
${APPSCALE_CMD} relocate guestbook 80 443
