
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
	installappscaleprofile
	installgems
        installsetuptools
	installhaproxy
	installnginx
	installappserverjava
	installmonitoring
	installthrift_fromsource
        installtornado_fromsource
        installflexmock
        installnose
	installhadoop
#	if [ "$DIST" = "jaunty" -o "$DIST" = "karmic" ]; then
	installzookeeper
#	fi
	installservice
        patchxmpp
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
	#installhypertablemonitoring
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
	installhadoop
	postinstallhadoop
#	if [ "$DIST" = "jaunty" -o "$DIST" = "karmic" ]; then
	    installzookeeper
#	fi
	postinstallzookeeper

        installcassandra
	postinstallcassandra
	installvoldemort
	postinstallvoldemort
	installhbase
	postinstallhbase
	installhypertable
	postinstallhypertable
	#installhypertablemonitoring
	#postinstallhypertablemonitoring
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
#	keygen
	;;
esac
