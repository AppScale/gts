cd `dirname $0`/..
if [ -z "$APPSCALE_HOME_RUNTIME" ]; then
    export APPSCALE_HOME_RUNTIME=`pwd`
fi

DESTDIR=$2
APPSCALE_HOME=${DESTDIR}${APPSCALE_HOME_RUNTIME}

. debian/appscale_install_functions.sh

echo "Install AppScale into ${APPSCALE_HOME}"
echo "APPSCALE_HOME in runtime=${APPSCALE_HOME_RUNTIME}"

# Let's make sure we got at least one input.
if [ -z "$1" ]; then
        echo "ERROR: need to have at least one target!"
        exit 1
fi

case "$1" in
    core)
        # Scratch install of appscale including post script.
        installappscaleprofile
        . /etc/profile.d/appscale.sh
        installgems
        postinstallhaproxy
        postinstallnginx
        portinstallmonit
        installPIL
        installpythonmemcache
        installlxml
        installxmpppy
        installappserverjava
        installjavajdk
        installphp54
        installappserverjava
        installthrift
        installtornado
        installpycrypto 
        postinstalltornado
        installflexmock
        installzookeeper
        postinstallzookeeper
        postinstallrabbitmq
        installcelery
        installservice
        postinstallservice
        setupntp
        sethosts
        setulimits
        increaseconnections
        ;;
    cassandra)
        installcassandra
        postinstallcassandra
        ;;
        # For test only. this should be included in core and all.
    solr)
        installsolr
        ;;
    zookeeper)
        installzookeeper
        postinstallzookeeper
        ;;
    rabbit-mq)
        postinstallrabbitmq
        ;; 
    celery)
        installcelery
        ;;
    all)
        # Scratch install of appscale including post script.
        installappscaleprofile
        . /etc/profile.d/appscale.sh
        installgems
        postinstallhaproxy
        postinstallnginx
        portinstallmonit
        installPIL
        installpythonmemcache
        installlxml
        installxmpppy
        installjavajdk
        installphp54
        installappserverjava
        installthrift
        installtornado
        installpycrypto 
        installflexmock
        postinstalltornado
        installzookeeper
        postinstallzookeeper
        installcassandra
        postinstallcassandra
        postinstallrabbitmq
        installcelery
        installsolr
        installservice
        postinstallservice
        setupntp
        sethosts
        setulimits
        increaseconnections
        ;;
esac
