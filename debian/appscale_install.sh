
cd `dirname $0`/..
if [ -z "$APPSCALE_HOME_RUNTIME" ]; then
    export APPSCALE_HOME_RUNTIME=`pwd`
fi

. debian/appscale_install_functions.sh

DESTDIR=$2
APPSCALE_HOME=${DESTDIR}${APPSCALE_HOME_RUNTIME}
DIST=`lsb_release -c -s`

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
        installmatplotlib
        installPIL
        installpycrypto
        installlxml
	installappserverjava
	postinstallappserverjava
	installmonitoring
	postinstallmonitoring
	installthrift_fromsource
	postinstallthrift_fromsource
        installtornado_fromsource
        postinstalltornado
	installprotobuf
	postinstallprotobuf
        installflexmock
        installnose
	installhadoop
	postinstallhadoop
	installzookeeper
	postinstallzookeeper
        installrabbitmq
        postinstallrabbitmq
        installcelery
	installservice
	postinstallservice
	updatealternatives
        patchxmpp
	sethosts
        setulimits
	;;
    cassandra)
	installcassandra
	postinstallcassandra
	;;
    hbase)
	installhbase
	postinstallhbase
	;;
    hypertable)
	installhypertable
	postinstallhypertable
	;;
    mysql)
	installmysql
	postinstallmysql
	;;
    # for test only. this should be included in core and all.
    zookeeper)
	installzookeeper
	postinstallzookeeper
	;;
    hadoop)
	installhadoop
	postinstallhadoop
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
        installmatplotlib
        installPIL
        installpycrypto
        installlxml
	installappserverjava
	postinstallappserverjava
	installmonitoring
	postinstallmonitoring
	installthrift_fromsource
	postinstallthrift_fromsource
        installtornado_fromsource
        installflexmock
        installnose
        postinstalltornado
	installprotobuf
	postinstallprotobuf
	installhadoop
	postinstallhadoop
	installzookeeper
	postinstallzookeeper
        installcassandra
	postinstallcassandra
	installhbase
	postinstallhbase
	installhypertable
	postinstallhypertable
	installmysql
	postinstallmysql
        installrabbitmq
        postinstallrabbitmq
        install celery
	installservice
	postinstallservice
	updatealternatives
        patchxmpp
	sethosts
        setulimits
	;;
esac
