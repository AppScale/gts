set -u
set -e

cd `dirname $0`/..
if [ -z "$APPSCALE_HOME_RUNTIME" ]; then
    export APPSCALE_HOME_RUNTIME=`pwd`
fi

if [ -z "${2-}" ]; then
    DESTDIR=""
else
    DESTDIR=$2
fi
APPSCALE_HOME=${DESTDIR}${APPSCALE_HOME_RUNTIME}
CURL_OPTS="-s"

. debian/appscale_install_functions.sh

echo "Install AppScale into ${APPSCALE_HOME}"
echo "APPSCALE_HOME in runtime=${APPSCALE_HOME_RUNTIME}"

# Let's make sure we got at least one input.
if [ -z "$1" ]; then
        echo "ERROR: need to have at least one target!"
        exit 1
fi

case "$1" in
    # At this time we cannot simply install pieces of AppScale, and the
    # space saving is minimal. So we install all the components.
    all|core|cassandra)
        # Scratch install of appscale including post script.
        installappscaleprofile
        . /etc/profile.d/appscale.sh
        upgradepip
        installgems
        postinstallhaproxy
        postinstallnginx
        installPIL
        installpythonmemcache
        installlxml
        installxmpppy
        installjavajdk
        installphp54
        installappserverjava
        installtornado
        installpycrypto 
        installflexmock
        installpycapnp
        installzookeeper
        postinstallzookeeper
        installcassandra
        postinstallcassandra
        postinstallrabbitmq
        installsolr
        installservice
        postinstallservice
        postinstallmonit
        sethosts
        setulimits
        increaseconnections
        installVersion
        installrequests
        installpyopenssl
        postinstallrsyslog
        installpsutil
        installapiclient
        buildgo
        installtaskqueue
        installdatastore
        preplogserver
        prepdashboard
        fetchclientjars
        ;;
esac
