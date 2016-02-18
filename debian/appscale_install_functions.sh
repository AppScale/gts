#!/bin/bash
#
# Common functions for build and installer
#
# This should work in bourne shell (/bin/sh)
# The function name should not include non alphabet character.

set -e

if [ -z "$APPSCALE_HOME_RUNTIME" ]; then
    export APPSCALE_HOME_RUNTIME=/opt/appscale
fi

if [ -z "$APPSCALE_PACKAGE_MIRROR" ]; then
    export APPSCALE_PACKAGE_MIRROR=http://s3.amazonaws.com/appscale-build
fi

export UNAME_MACHINE=$(uname -m)
if [ -z "$JAVA_HOME_DIRECTORY" ]; then
	if [ "$UNAME_MACHINE" = "x86_64" ]; then
		export JAVA_HOME_DIRECTORY=/usr/lib/jvm/java-7-openjdk-amd64
	elif [ "$UNAME_MACHINE" = "armv7l" ] || [ "$UNAME_MACHINE" = "armv6l" ]; then
		export JAVA_HOME_DIRECTORY=/usr/lib/jvm/java-7-openjdk-armhf
	fi
fi

VERSION_FILE="$APPSCALE_HOME_RUNTIME"/VERSION
export APPSCALE_VERSION=$(grep AppScale "$VERSION_FILE" | sed 's/AppScale version \(.*\)/\1/')


pipwrapper ()
{
    # We have seen quite a few network/DNS issues lately, so much so that
    # it takes a couple of tries to install packages with pip. This
    # wrapper ensure that we are a bit more persitent.
    if [ -n "$1" ] ; then
        for x in {1..5} ; do
            if pip install --upgrade $1 ; then
                return
            else
                echo "Failed to install $1: retrying ..."
                sleep $x
            fi
        done
        echo "Failed to install $1: giving up."
        exit 1
    else
        echo "Need an argument for pip!"
        exit 1
    fi
}

# This function is to disable the specify service so that it won't start
# at next boot. AppScale manages those services.
disableservice() {
    if [ -n "$1" ]; then
      update-rc.d "${1}" disable || true
      # The following to make sure we disable it for upstart.
      if [ -d "/etc/init" ]; then
          echo "manual" > /etc/init/"${1}".override
      fi
    else
        echo "Need a service name to disable!"
        exit 1
    fi
}

increaseconnections()
{
    if [ "${IN_DOCKER}" != "yes" ]; then
        echo "ip_conntrack" >> /etc/modules

        # Google Compute Engine doesn't allow users to use modprobe, so it's ok if
        # the modprobe command fails.
        modprobe ip_conntrack || true

        echo "net.netfilter.nf_conntrack_max = 262144" >> /etc/sysctl.conf
        echo "net.core.somaxconn = 20240" >> /etc/sysctl.conf
        echo "net.ipv4.tcp_tw_recycle = 0" >> /etc/sysctl.conf
        echo "net.ipv4.tcp_tw_reuse = 0" >> /etc/sysctl.conf
        echo "net.ipv4.tcp_orphan_retries = 1" >> /etc/sysctl.conf
        echo "net.ipv4.tcp_fin_timeout = 25" >> /etc/sysctl.conf
        echo "net.ipv4.tcp_max_orphans = 8192" >> /etc/sysctl.conf
        echo "net.ipv4.ip_local_port_range = 32768    61000" >> /etc/sysctl.conf

        /sbin/sysctl -p /etc/sysctl.conf
    fi
}

sethosts()
{
    if [ "${IN_DOCKER}" != "yes" ]; then
        cp -v /etc/hosts /etc/hosts.orig
        HOSTNAME=`hostname`
        echo "Generating /etc/hosts"
        cat <<EOF | tee /etc/hosts
127.0.0.1       localhost localhost.localdomain
127.0.1.1 $HOSTNAME
::1     ip6-localhost ip6-loopback
fe00::0 ip6-localnet
ff00::0 ip6-mcastprefix
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
ff02::3 ip6-allhosts
EOF
    fi
}

installPIL()
{
    if [ "$DIST" = "precise" ]; then
        pip uninstall -y PIL
        # The behavior of the rotate function changed in pillow 3.0.0.
        # The system package in trusty is version 2.3.0.
        pipwrapper "pillow==2.3.0"
    fi
}

installlxml()
{
    if [ "$DIST" = "precise" ]; then
        pipwrapper lxml
    fi
}

installxmpppy()
{
    if [ "$DIST" = "precise" ]; then
        pipwrapper xmpppy
    fi
}

setulimits()
{
    cat <<EOF | tee /etc/security/limits.conf
root            hard    nofile           200000
root            soft    nofile           200000
*               hard    nofile           200000
*               soft    nofile           200000
EOF
}

installappscaleprofile()
{
    DESTFILE=${DESTDIR}/etc/profile.d/appscale.sh
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE
export APPSCALE_HOME=${APPSCALE_HOME_RUNTIME}
export PYTHON_EGG_CACHE=/tmp/.python_eggs
export EC2_PRIVATE_KEY=\${APPSCALE_HOME}/.appscale/certs/mykey.pem
export EC2_CERT=\${APPSCALE_HOME}/.appscale/certs/mycert.pem
export LC_ALL='en_US.UTF-8'
EOF
# This enables to load AppServer and AppDB modules. It must be before the python-support.
    DESTFILE=${DESTDIR}/usr/lib/python2.7/dist-packages/appscale_appserver.pth
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE
${APPSCALE_HOME_RUNTIME}/AppDB
${APPSCALE_HOME_RUNTIME}/AppServer
EOF
# Enable to load site-packages of Python.
    DESTFILE=${DESTDIR}/usr/local/lib/python2.7/dist-packages/site_packages.pth
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE
/usr/lib/python2.7/site-packages
EOF

    # This create link to appscale settings.
    rm -rfv ${DESTDIR}/etc/appscale
    mkdir -pv ~/.appscale
    mkdir -pv ${APPSCALE_HOME_RUNTIME}/.appscale
    ln -sfv ${APPSCALE_HOME_RUNTIME}/.appscale ${DESTDIR}/etc/appscale

    cat <<EOF | tee /etc/appscale/home || exit
${APPSCALE_HOME_RUNTIME}
EOF
    # Create the global AppScale environment file.
    DESTFILE=${DESTDIR}/etc/appscale/environment.yaml
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE
APPSCALE_HOME: ${APPSCALE_HOME_RUNTIME}
EC2_HOME: /usr/local/ec2-api-tools
JAVA_HOME: ${JAVA_HOME_DIRECTORY}
EOF
    mkdir -pv /var/log/appscale
    # Allow rsyslog to write to appscale log directory.
    chgrp adm /var/log/appscale
    chmod g+rwx /var/log/appscale

    mkdir -pv /var/appscale/

    # This puts in place the logrotate rules.
    if [ -d /etc/logrotate.d/ ]; then
        cp ${APPSCALE_HOME}/lib/templates/appscale-logrotate.conf /etc/logrotate.d/appscale
    fi

    # Logrotate AppScale logs hourly.
    LOGROTATE_HOURLY=/etc/cron.hourly/logrotate-hourly
    cat <<EOF | tee $LOGROTATE_HOURLY
#!/bin/sh
/usr/sbin/logrotate /etc/logrotate.d/appscale*
EOF
    chmod +x $LOGROTATE_HOURLY
}

installthrift()
{
    case ${DIST} in
        precise|wheezy) pipwrapper thrift ;;
    esac
}

installjavajdk()
{
    # This makes jdk-7 the default JVM.
    update-alternatives --set java ${JAVA_HOME_DIRECTORY}/jre/bin/java
}

installappserverjava()
{
    # Compile source file.
    cd ${APPSCALE_HOME}/AppServer_Java
    ant install
    ant clean-build

    if [ -n "$DESTDIR" ]; then
        # Delete unnecessary files.
	rm -rfv src lib
    fi
}

installtornado()
{
    if [ "$DIST" = "precise" ]; then
        pipwrapper tornado
        DISTP=/usr/local/lib/python2.7/dist-packages
        if [ -z "$(find ${DISTP} -name tornado-*.egg*)" ]; then
            echo "Fail to install python tornado. Please retry."
            exit 1
        fi
        if [ -n "$DESTDIR" ]; then
            mkdir -pv ${DESTDIR}${DISTP}
            cp -rv ${DISTP}/tornado-*.egg* ${DESTDIR}${DISTP}
        fi
    fi
}

installflexmock()
{
    if [ "$DIST" = "precise" ]; then
        pipwrapper flexmock
    fi
}

postinstalltornado()
{
    if [ "$DIST" = "precise" ]; then
        pipwrapper tornado
    fi
}

postinstallhaproxy()
{
    cp -v ${APPSCALE_HOME}/AppDashboard/setup/haproxy.cfg /etc/haproxy/
    sed -i 's/^ENABLED=0/ENABLED=1/g' /etc/default/haproxy

    # AppScale starts/stop the service.
    service haproxy stop || true
    disableservice haproxy
}

installgems()
{
    GEMOPT="--no-rdoc --no-ri"
    # Rake 10.0 depecates rake/rdoctask - upgrade later.
    gem install rake ${GEMOPT}
    sleep 1
    # ZK 1.0 breaks our existing code - upgrade later.
    if [ "$UNAME_MACHINE" = "x86_64" ]; then
		gem install zookeeper
	elif [ "$UNAME_MACHINE" = "armv7l" ] || [ "$UNAME_MACHINE" = "armv6l" ]; then
		# If machine is Raspberry Pi, then go to patched version.
	    export PWD_TEMP=$(pwd)
		cd /root
		git clone https://github.com/lmandres/zookeeper-raspberry-pi.git
		cd zookeeper-raspberry-pi
		gem build zookeeper.gemspec
		gem install --local zookeeper-1.4.11.gem
		cd ${PWD_TEMP}
	fi
    sleep 1
    gem install json ${GEMOPT}
    sleep 1
    gem install soap4r-ruby1.9 ${GEMOPT}
    gem install httparty ${GEMOPT}
    gem install httpclient ${GEMOPT}
    # This is for the unit testing framework.
    gem install simplecov ${GEMOPT}
}

installphp54()
{
    # In Precise we have a too old version of php. We need at least 5.4.
    if [ "$DIST" = "precise" ]; then
        add-apt-repository -y ppa:ondrej/php5-oldstable
        apt-get update
        # We need to pull also php5-cgi to ensure apache2 won't be pulled
        # in.
        apt-get install --force-yes -y php5-cgi php5
    fi
}

postinstallnginx()
{
    cp -v ${APPSCALE_HOME}/AppDashboard/setup/load-balancer.conf /etc/nginx/sites-enabled/
    rm -fv /etc/nginx/sites-enabled/default
    chmod +x /root
}

installsolr()
{
    SOLR_VER=4.10.2
    mkdir -p ${APPSCALE_HOME}/SearchService/solr
    cd ${APPSCALE_HOME}/SearchService/solr
    rm -rfv solr
    curl ${CURL_OPTS} -o solr-${SOLR_VER}.tgz $APPSCALE_PACKAGE_MIRROR/solr-${SOLR_VER}.tgz
    tar zxvf solr-${SOLR_VER}.tgz
    mv -v solr-${SOLR_VER} solr
    rm -fv solr-${SOLR_VER}.tgz
}

installcassandra()
{
    CASSANDRA_VER=2.0.7
    PYCASSA_VER=1.9.1
    
    mkdir -p ${APPSCALE_HOME}/AppDB/cassandra
    cd ${APPSCALE_HOME}/AppDB/cassandra
    rm -rfv cassandra
    curl ${CURL_OPTS} -o apache-cassandra-${CASSANDRA_VER}-bin.tar.gz $APPSCALE_PACKAGE_MIRROR/apache-cassandra-${CASSANDRA_VER}-bin.tar.gz
    tar xzvf apache-cassandra-${CASSANDRA_VER}-bin.tar.gz
    mv -v apache-cassandra-${CASSANDRA_VER} cassandra
    rm -fv apache-cassandra-${CASSANDRA_VER}-bin.tar.gz
    cd cassandra
    chmod -v +x bin/cassandra
    cp -v ${APPSCALE_HOME}/AppDB/cassandra/templates/cassandra.in.sh ${APPSCALE_HOME}/AppDB/cassandra/cassandra/bin
    cp -v ${APPSCALE_HOME}/AppDB/cassandra/templates/cassandra-env.sh ${APPSCALE_HOME}/AppDB/cassandra/cassandra/conf
    mkdir -p /var/lib/cassandra
    # TODO only grant the cassandra user access.
    chmod 777 /var/lib/cassandra

    if [ "$DIST" = "precise" ]; then
        pipwrapper  thrift
    fi
    pipwrapper  pycassa

    cd ${APPSCALE_HOME}/AppDB/cassandra/cassandra/lib
    curl ${CURL_OPTS} -o jamm-0.2.2.jar $APPSCALE_PACKAGE_MIRROR/jamm-0.2.2.jar

    # Create separate log directory.
    mkdir -pv /var/log/appscale/cassandra
}

postinstallcassandra()
{
    mkdir -p ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}
    touch ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}/cassandra
}


installservice()
{
    # This must be absolete path of runtime.
    mkdir -pv ${DESTDIR}/etc/init.d/
    cp ${APPSCALE_HOME_RUNTIME}/AppController/scripts/appcontroller ${DESTDIR}/etc/init.d/appscale-controller
    chmod -v a+x ${DESTDIR}/etc/init.d/appscale-controller

    # Make sure the init script runs each time, so that it can start the
    # AppController on system reboots.
    update-rc.d -f appscale-controller defaults
}

postinstallservice()
{
    # Stop services shouldn't run at boot, then disable them.
    service memcached stop || true
    disableservice memcached

    ejabberdctl stop || true
    disableservice ejabberd
}

installpythonmemcache()
{
    if [ "$DIST" = "precise" ]; then
        VERSION=1.53

        mkdir -pv ${APPSCALE_HOME}/downloads
        cd ${APPSCALE_HOME}/downloads
        curl ${CURL_OPTS} -o python-memcached-${VERSION}.tar.gz $APPSCALE_PACKAGE_MIRROR/python-memcached-${VERSION}.tar.gz
        tar zxvf python-memcached-${VERSION}.tar.gz
        cd python-memcached-${VERSION}
        python setup.py install
        cd ..
        rm -fr python-memcached-${VERSION}.tar.gz
        rm -fr python-memcached-${VERSION}
    fi
}

installzookeeper()
{
    if [ "$DIST" = "precise" ]; then
        ZK_REPO_PKG=cdh4-repository_1.0_all.deb
        curl ${CURL_OPTS} -o /tmp/${ZK_REPO_PKG} http://archive.cloudera.com/cdh4/one-click-install/precise/amd64/${ZK_REPO_PKG}
        dpkg -i /tmp/${ZK_REPO_PKG}
        apt-get update
        apt-get install -y zookeeper-server
    else
        apt-get install -y zookeeper zookeeperd zookeeper-bin
    fi

    # Trusty's kazoo version is too old, so use the version in Xenial.
    case "$DIST" in
        precise|trusty|wheezy) pipwrapper "kazoo==2.2.1" ;;
        *) apt-get install python-kazoo ;;
    esac
}

installpycrypto()
{
    pipwrapper pycrypto
}

postinstallzookeeper()
{
    if [ "$DIST" = "precise" ]; then
        service zookeeper-server stop || true
        disableservice zookeeper-server
    else
        service zookeeper stop || true
        disableservice zookeeper
    fi
    if [ ! -d /etc/zookeeper/conf ]; then
        echo "Cannot find zookeeper configuration!"
        exit 1
    fi

    # Make sure we do logrotate the zookeeper logs.
    if grep -v "^#" /etc/zookeeper/conf/log4j.properties|grep -i MaxBackupIndex > /dev/null ; then
        # Let's make sure we don't keep more than 3 backups.
        sed -i 's/\(.*[mM]ax[bB]ackup[iI]ndex\)=.*/\1=3/' /etc/zookeeper/conf/log4j.properties
    else
        # Let's add a rotation directive.
        echo "log4j.appender.ROLLINGFILE.MaxBackupIndex=3" >> /etc/zookeeper/conf/log4j.properties
    fi
}

installcelery()
{
    if [ "$DIST" = "precise" ]; then
        pipwrapper Celery
    fi
    pipwrapper Flower
}

postinstallrabbitmq()
{
    # After install it starts up, shut it down.
    rabbitmqctl stop || true
    disableservice rabbitmq-server
}

installVersion()
{
    # Install the VERSION file. We should sign it to ensure the version is
    # correct.
    if [ -e /etc/appscale/VERSION ]; then
        mv /etc/appscale/VERSION /etc/appscale/VERSION-$(date --rfc-3339=date)
    fi
    cp ${APPSCALE_HOME}/VERSION /etc/appscale/
}

installrequests()
{
    if [ "$DIST" = "precise" ]; then
        pipwrapper requests
    fi
}

postinstallrsyslog()
{
    # We need to enable remote logging capability. We have found 2
    # different version to configure UDP and TCP: we try both.
    sed -i 's/#$ModLoad imudp/$ModLoad imudp/' /etc/rsyslog.conf
    sed -i 's/#$UDPServerRun 514/$UDPServerRun 514/' /etc/rsyslog.conf
    sed -i 's/#$ModLoad imtcp/$ModLoad imtcp/' /etc/rsyslog.conf
    sed -i 's/#$InputTCPServerRun 514/$InputTCPServerRun 514/' /etc/rsyslog.conf
    # This seems the newer version.
    sed -i 's/#module(load="imudp")/module(load="imudp")/' /etc/rsyslog.conf
    sed -i 's/#input(type="imudp" port="514")/input(type="imudp" port="514")/' /etc/rsyslog.conf
    sed -i 's/#module(load="imtcp")/module(load="imtcp")/' /etc/rsyslog.conf
    sed -i 's/#input(type="imtcp" port="514")/input(type="imtcp" port="514")/' /etc/rsyslog.conf

    # Restart the service
    service rsyslog restart || true
}

postinstallmonit()
{
    # We need to have http connection enabled to talk to monit.
    if ! grep -v '^#' /etc/monit/monitrc |grep httpd > /dev/null; then
        cat <<EOF | tee -a /etc/monit/monitrc

# Added by AppScale: this is needed to have a working monit command
set httpd port 2812 and
   use address localhost  # only accept connection from localhost
   allow localhost
EOF
    fi

    # Check services every 5 seconds
    sed -i 's/set daemon.*/set daemon 5/' /etc/monit/monitrc

    # Monit cannot start at boot time: in case of accidental reboot, it
    # would start processes out of order. The controller will restart
    # monit as soon as it starts.
    service monit stop
    disableservice monit
}
