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

export APPSCALE_VERSION=1.14.0

increaseconnections()
{
    echo "ip_conntrack" >> /etc/modules

    # Google Compute Engine doesn't allow users to use modprobe, so it's ok if
    # the modprobe command fails.
    set +e
    modprobe ip_conntrack
    set -e

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

setupntpcron()
{
    # make sure we are time synced at start and that ntp is running
    service ntp stop
    ntpdate pool.ntp.org
    service ntp start
}

installphp()
{
    :;
}

installnumpy()
{
    :;
}

installPIL()
{
    pip uninstall -y PIL
    /usr/bin/yes | pip install --upgrade pillow
}

installpycrypto()
{
    cd ${APPSCALE_HOME}/downloads
    wget $APPSCALE_PACKAGE_MIRROR/pycrypto-2.6.tar.gz
    tar zxvf pycrypto-2.6.tar.gz
    cd pycrypto-2.6
    python setup.py install
    cd ..
    rm -fr pycrypto-2.6*
}

installlxml()
{
    easy_install lxml
}

installxmpppy()
{
    easy_install xmpppy
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
# enable to load AppServer and AppDB modules. It must be before the python-support.
    DESTFILE=${DESTDIR}/usr/lib/python2.7/dist-packages/appscale_appserver.pth
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE
${APPSCALE_HOME_RUNTIME}/AppDB
${APPSCALE_HOME_RUNTIME}/AppServer
EOF
# enable to load site-packages of Python
    DESTFILE=${DESTDIR}/usr/local/lib/python2.7/dist-packages/site_packages.pth
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE
/usr/lib/python2.7/site-packages
EOF

    # create link to appscale settings
    rm -rfv ${DESTDIR}/etc/appscale
    mkdir -pv ~/.appscale
    mkdir -pv ${APPSCALE_HOME_RUNTIME}/.appscale
    ln -sfv ${APPSCALE_HOME_RUNTIME}/.appscale ${DESTDIR}/etc/appscale

    cat <<EOF | tee /etc/appscale/home || exit
${APPSCALE_HOME_RUNTIME}
EOF
    # create the global AppScale environment file
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
    easy_install -U thrift
}

installjavajdk()
{
    :;
    # make jdk-7 the default
    update-alternatives --set java /usr/lib/jvm/java-7-openjdk-amd64/jre/bin/java
}

installappserverjava()
{
    # compile source file.
    cd ${APPSCALE_HOME}/AppServer_Java
    ant install
    ant clean-build

    if [ -n "$DESTDIR" ]; then
        # delete unnecessary files.
	rm -rfv src lib
    fi
}

postinstallappserverjava()
{
    :;
}

installtornado()
{
    easy_install -U tornado
    DISTP=/usr/local/lib/python2.7/dist-packages
    if [ -z "$(find ${DISTP} -name tornado-*.egg)" ]; then
	echo "Fail to install python tornado. Please retry."
	exit 1
    fi
    if [ -n "$DESTDIR" ]; then
	mkdir -pv ${DESTDIR}${DISTP}
	cp -rv ${DISTP}/tornado-*.egg ${DESTDIR}${DISTP}
    fi
}

installnose()
{
    easy_install nose
}

installflexmock()
{
    easy_install flexmock
}

postinstalltornado()
{
    easy_install tornado
}

installhaproxy()
{
    # download from appscale site
    HAPROXY_VER=1.4.4
    wget $APPSCALE_PACKAGE_MIRROR/haproxy-${HAPROXY_VER}.tar.gz
    tar zxvf haproxy-${HAPROXY_VER}.tar.gz
    rm -v haproxy-${HAPROXY_VER}.tar.gz

    # install service script
    mkdir -pv ${DESTDIR}/etc/init.d
    cp -v ${APPSCALE_HOME}/AppDashboard/setup/haproxy-init.sh ${DESTDIR}/etc/init.d/haproxy 
    chmod -v a+x ${DESTDIR}/etc/init.d/haproxy 
    mkdir -pv ${DESTDIR}/etc/haproxy
    cp -v ${APPSCALE_HOME}/AppDashboard/setup/haproxy.cfg ${DESTDIR}/etc/haproxy/ 
    mkdir -pv ${DESTDIR}/etc/default
    echo "ENABLED=1" > ${DESTDIR}/etc/default/haproxy
}

postinstallhaproxy()
{
    service haproxy stop || true
    update-rc.d -f haproxy remove || true
}

installgems()
{
    # install gem here
    cd
    wget $APPSCALE_PACKAGE_MIRROR/rubygems-1.3.7.tgz
    tar zxvf rubygems-1.3.7.tgz
    cd rubygems-1.3.7
    ruby setup.rb
    cd
    ln -sf /usr/bin/gem1.8 /usr/bin/gem
    rm -rf rubygems-1.3.7.tgz
    rm -rf rubygems-1.3.7

    # gem update
    GEMOPT="--no-rdoc --no-ri"
    # Rake 10.0 depecates rake/rdoctask - upgrade later
    gem install -v=0.9.2.2 rake ${GEMOPT} 
    sleep 1
    # ZK 1.0 breaks our existing code - upgrade later
    gem install -v=0.9.3 zookeeper
    sleep 1
    gem install json ${GEMOPT}
    sleep 1
    gem install -v=0.8.3 httparty ${GEMOPT}
    # This is for the unit testing framework
    gem install -v=1.0.4 flexmock ${GEMOPT}
    gem install -v=1.0.0 rcov ${GEMOPT}

}

postinstallgems()
{
    :;
}

installnginx()
{
    :;
}

# This function is called from postinst.core, so we don't need to use DESTDIR
postinstallnginx()
{
    cd ${APPSCALE_HOME}
    cp -v AppDashboard/setup/load-balancer.conf /etc/nginx/sites-enabled/
    rm -fv /etc/nginx/sites-enabled/default
    chmod +x /root
}

installmonit()
{
    # let's use our configuration
    cd ${APPSCALE_HOME}
    cp monitrc /etc/monitrc
    chmod 0700 /etc/monitrc

}

installcassandra()
{
    CASSANDRA_VER=2.0.6
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
    # TODO only grant the cassandra user access
    chmod 777 /var/lib/cassandra

    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    wget $APPSCALE_PACKAGE_MIRROR/pycassa-${PYCASSA_VER}.tar.gz
    tar zxvf pycassa-${PYCASSA_VER}.tar.gz  
    cd pycassa-${PYCASSA_VER}
    python setup.py install
    cd ..
    rm -fr pycassa-${PYCASSA_VER}
    rm -fr pycassa-${PYCASSA_VER}.tar.gz 
    
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
    # this must be absolete path of runtime
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
  mkdir -pv ${APPSCALE_HOME}/downloads
  cd ${APPSCALE_HOME}/downloads
  wget http://archive.cloudera.com/cdh4/one-click-install/precise/amd64/cdh4-repository_1.0_all.deb
  dpkg -i cdh4-repository_1.0_all.deb 
  apt-get update
  apt-get install -y zookeeper-server 
  cd ..
  rm -rf ${APPSCALE_HOME}/downloads

  easy_install kazoo
}

postinstallzookeeper()
{
    if ! grep -q zookeeper /etc/passwd; then
	adduser --system --no-create-home zookeeper
	addgroup --system zookeeper
	adduser zookeeper zookeeper
    fi
    chown -v zookeeper:zookeeper /var/run/zookeeper || true
    chown -v zookeeper:zookeeper /var/lib/zookeeper || true

    # need conf/environment to stop service
    cp -v /etc/zookeeper/conf_example/* /etc/zookeeper/conf || true

    service zookeeper stop || true
    update-rc.d -f zookeeper remove || true
}

installsetuptools()
{
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    wget $APPSCALE_PACKAGE_MIRROR/setuptools-0.6c11.tar.gz
    tar zxvf setuptools-0.6c11.tar.gz
    pushd setuptools-0.6c11
    python setup.py install
    popd
    rm -fr  setuptools-0.6c11*
}

postinstallsetuptools()
{
    :;
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
    easy_install Celery==3.0.24
    easy_install Flower
}

installrabbitmq()
{
    :;
}
postinstallrabbitmq()
{
    # After install it starts up, shut it down
    rabbitmqctl stop || true
    update-rc.d -f rabbitmq remove || true
    update-rc.d -f rabbitmq-server remove || true
}
