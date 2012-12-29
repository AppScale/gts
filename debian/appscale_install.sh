
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
    voldemort)
	installprotobuf
	installvoldemort
        postinstallvoldemort
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
    mongodb)
	installmongodb
	postinstallmongodb
	;;
    memcachedb)
	installmemcachedb
	postinstallmemcachedb
	;;
    redisdb)
	installredisdb
        postinstallredisdb
	;;
    timesten)
	installtimesten
	postinstalltimesten
	;;
    simpledb)
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
	installvoldemort
	postinstallvoldemort
	installhbase
	postinstallhbase
	installhypertable
	postinstallhypertable
	installmysql
	postinstallmysql
	installmongodb
	postinstallmongodb
        installredisdb
        postinstallredisdb
	installmemcachedb
	postinstallmemcachedb
	installtimesten
	postinstalltimesten
        installrabbitmq
        postinstallrabbitmq
	installservice
	postinstallservice
	updatealternatives
        patchxmpp
	sethosts
        setulimits
	;;
esac
