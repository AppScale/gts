cd `dirname $0`/..
if [ -z "$APPSCALE_HOME_RUNTIME" ]; then
    export APPSCALE_HOME_RUNTIME=`pwd`
fi

DESTDIR=$2
APPSCALE_HOME=${DESTDIR}${APPSCALE_HOME_RUNTIME}

. debian/appscale_install_functions.sh

echo "Install AppScale into ${APPSCALE_HOME}"
echo "APPSCALE_HOME in runtime=${APPSCALE_HOME_RUNTIME}"

case "$1" in
    core)
	# scratch install of appscale including post script.
	installappscaleprofile
	. /etc/profile.d/appscale.sh
	installgems
	postinstallgems
        installsetuptools
	installhaproxy
	postinstallhaproxy
	installnginx
	postinstallnginx
        installpython27
        installnumpy
        installpythonmemcache
        installmatplotlib
        installPIL
        installpycrypto
        installlxml
        installxmpppy
	installjavajdk
        installappserverjava
        postinstallappserverjava
	installthrift_fromsource
	postinstallthrift_fromsource
        installtornado
        postinstalltornado
	installprotobuf
	postinstallprotobuf
        installflexmock
        installnose
	installzookeeper
	postinstallzookeeper
        installrabbitmq
        postinstallrabbitmq
        installcelery
	installservice
	postinstallservice
	setupntpcron
	sethosts
        setulimits
        increaseconnections
	;;
    cassandra)
	installcassandra
	postinstallcassandra
	;;
        # for test only. this should be included in core and all.
    zookeeper)
	installzookeeper
	postinstallzookeeper
	;;
    protobuf-src)
	installprotobuf_fromsource
	postinstallprotobuf
	;;
    rabbit-mq)
        installrabbitmq
        postinstallrabbitmq
        ;; 
    celery)
        installcelery
        ;;
    all)
	# scratch install of appscale including post script.
	installappscaleprofile
	. /etc/profile.d/appscale.sh
	installgems
	postinstallgems
        installsetuptools
	installhaproxy
	postinstallhaproxy
	installnginx
	postinstallnginx
        installpython27
        installnumpy
        installpythonmemcache
        installmatplotlib
        installPIL
        installpycrypto
        installlxml
        installxmpppy
	installjavajdk
        installappserverjava
        postinstallappserverjava
	installthrift_fromsource
	postinstallthrift_fromsource
        installtornado
        installflexmock
        installnose
        postinstalltornado
	installprotobuf
	postinstallprotobuf
	installzookeeper
	postinstallzookeeper
        installcassandra
	postinstallcassandra
        installrabbitmq
        postinstallrabbitmq
        installcelery
	installservice
	postinstallservice
	setupntpcron
        sethosts
        setulimits
        increaseconnections
	;;
esac
