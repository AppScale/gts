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

export APPSCALE_VERSION=2.0.0

pip_wrapper () 
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

increaseconnections()
{
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
}

sethosts()
{
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
}

setupntp()
{
    # Let's make sure time is tightly synchronized (64s poll).
    echo -e "\nmaxpoll 6" >> /etc/ntp.conf

    # This ensure that we synced first, to allow ntpd to stay
    # synchronized. We have seen temporary failures in reaching out to the
    # ntp pool, so we'll make sure we try few times.
    service ntp stop
    for x in {1..5} ; do
        if ntpdate pool.ntp.org ; then
                break
        fi
    done
    if [ $x -ge 5 ]; then
        echo "Cannot sync clock: you may have issues!"
    fi
    service ntp start
}

installPIL()
{
    pip uninstall -y PIL
    pip_wrapper pillow
}

installlxml()
{
    pip_wrapper lxml
}

installxmpppy()
{
    pip_wrapper xmpppy
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
JAVA_HOME: /usr/lib/jvm/java-7-openjdk-amd64
EOF
    mkdir -pv /var/log/appscale
    mkdir -pv /var/appscale/
}

installthrift()
{
    pip_wrapper thrift
}

installjavajdk()
{
    # This makes jdk-7 the default JVM.
    update-alternatives --set java /usr/lib/jvm/java-7-openjdk-amd64/jre/bin/java
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
    pip_wrapper tornado
    DISTP=/usr/local/lib/python2.7/dist-packages
    if [ -z "$(find ${DISTP} -name tornado-*.egg*)" ]; then
	echo "Fail to install python tornado. Please retry."
	exit 1
    fi
    if [ -n "$DESTDIR" ]; then
	mkdir -pv ${DESTDIR}${DISTP}
	cp -rv ${DISTP}/tornado-*.egg* ${DESTDIR}${DISTP}
    fi
}

installflexmock()
{
    pip_wrapper flexmock
}

postinstalltornado()
{
    pip_wrapper tornado
}

postinstallhaproxy()
{
    cp -v ${APPSCALE_HOME}/AppDashboard/setup/haproxy.cfg /etc/haproxy/
    sed -i 's/^ENABLED=0/ENABLED=1/g' /etc/default/haproxy

    # AppScale starts/stop the service.
    service haproxy stop || true
    update-rc.d -f haproxy remove || true
}

installgems()
{
    GEMOPT="--no-rdoc --no-ri"
    # Rake 10.0 depecates rake/rdoctask - upgrade later.
    gem install -v=0.9.2.2 rake ${GEMOPT} 
    sleep 1
    # ZK 1.0 breaks our existing code - upgrade later.
    gem install -v=0.9.3 zookeeper
    sleep 1
    gem install json ${GEMOPT}
    sleep 1
    gem install -v=0.8.3 httparty ${GEMOPT}
    # This is for the unit testing framework.
    gem install -v=1.0.4 flexmock ${GEMOPT}
    gem install -v=1.0.0 rcov ${GEMOPT}
}

postinstallnginx()
{
    cp -v ${APPSCALE_HOME}/AppDashboard/setup/load-balancer.conf /etc/nginx/sites-enabled/
    rm -fv /etc/nginx/sites-enabled/default
    chmod +x /root

    # apache2 is a dependency pulled in by php5: make sure it doesn't use
    # port 80.
    service apache2 stop || true
    update-rc.d -f apache2 remove || true
}

portinstallmonit()
{
    # Let's use our configuration.
    cp ${APPSCALE_HOME}/monitrc /etc/monit/monitrc
    chmod 0700 /etc/monit/monitrc
    service monit stop
    update-rc.d -f monit remove
}

installcassandra()
{
    CASSANDRA_VER=2.0.7
    PYCASSA_VER=1.9.1
    
    mkdir -p ${APPSCALE_HOME}/AppDB/cassandra
    cd ${APPSCALE_HOME}/AppDB/cassandra
    rm -rfv cassandra
    wget $APPSCALE_PACKAGE_MIRROR/apache-cassandra-${CASSANDRA_VER}-bin.tar.gz
    tar xzvf apache-cassandra-${CASSANDRA_VER}-bin.tar.gz
    mv -v apache-cassandra-${CASSANDRA_VER} cassandra
    rm -fv apache-cassandra-${CASSANDRA_VER}-bin.tar.gz
    cd cassandra
    chmod -v +x bin/cassandra
    cp -v ${APPSCALE_HOME}/AppDB/cassandra/templates/cassandra.in.sh ${APPSCALE_HOME}/AppDB/cassandra/cassandra/bin
    mkdir -p /var/lib/cassandra
    # TODO only grant the cassandra user access.
    chmod 777 /var/lib/cassandra

    pip_wrapper  setuptools
    pip_wrapper  pycassa
    pip_wrapper  thrift

    cd ${APPSCALE_HOME}/AppDB/cassandra/cassandra/lib
    wget $APPSCALE_PACKAGE_MIRROR/jamm-0.2.2.jar
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
    ln -sfv ${APPSCALE_HOME_RUNTIME}/appscale-controller.sh ${DESTDIR}/etc/init.d/appscale-controller
    chmod -v a+x ${APPSCALE_HOME}/appscale-controller.sh
    ln -sfv ${APPSCALE_HOME_RUNTIME}/appscale-progenitor.sh ${DESTDIR}/etc/init.d/appscale-progenitor
    chmod -v a+x ${APPSCALE_HOME}/appscale-progenitor.sh

    # Make the progenitor start up when AppScale starts, so that it can start
    # the AppController on system reboots.
    update-rc.d -f appscale-progenitor defaults
}

postinstallservice()
{
    # First, stop all services that don't need to be running at boot.
    service memcached stop || true

    # Next, remove them from the boot list.
    update-rc.d -f memcached remove || true

    ejabberdctl stop || true
    update-rc.d -f ejabberd remove || true
}

installpythonmemcache()
{
  VERSION=1.53

  mkdir -pv ${APPSCALE_HOME}/downloads
  cd ${APPSCALE_HOME}/downloads
  wget $APPSCALE_PACKAGE_MIRROR/python-memcached-${VERSION}.tar.gz
  tar zxvf python-memcached-${VERSION}.tar.gz
  cd python-memcached-${VERSION}
  python setup.py install
  cd ..
  rm -fr python-memcached-${VERSION}.tar.gz
  rm -fr python-memcached-${VERSION}
}

installzookeeper()
{
  ZK_REPO_PKG=cdh4-repository_1.0_all.deb
  wget -O  /tmp/${ZK_REPO_PKG} http://archive.cloudera.com/cdh4/one-click-install/precise/amd64/${ZK_REPO_PKG}
  dpkg -i /tmp/${ZK_REPO_PKG}
  apt-get update 
  apt-get install -y zookeeper-server 

  pip_wrapper kazoo
}

installpycrypto()
{
  pip_wrapper pycrypto
}

postinstallzookeeper()
{
    # Need conf/environment to stop service.
    cp -v /etc/zookeeper/conf_example/* /etc/zookeeper/conf || true
    service zookeeper-server stop || true
    update-rc.d -f zookeeper-server remove || true
}

keygen()
{
    test -e /root/.ssh/id_rsa || ssh-keygen -q -t rsa -f /root/.ssh/id_rsa -N ""
    touch /root/.ssh/authorized_keys
    cat /root/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys
    chmod -v go-r /root/.ssh/authorized_keys
}

installcelery()
{
    pip_wrapper Celery
    pip_wrapper Flower
}

postinstallrabbitmq()
{
    # After install it starts up, shut it down.
    rabbitmqctl stop || true
    update-rc.d -f rabbitmq-server remove || true
}
