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

if [ -z "${APPSCALE_PACKAGE_MIRROR-}" ]; then
    export APPSCALE_PACKAGE_MIRROR=http://s3.amazonaws.com/appscale-build
fi

export UNAME_MACHINE=$(uname -m)
if [ -z "${JAVA_HOME_DIRECTORY-}" ]; then
    if [ "$UNAME_MACHINE" = "x86_64" ]; then
        export JAVA_HOME_DIRECTORY=/usr/lib/jvm/java-7-openjdk-amd64
    elif [ "$UNAME_MACHINE" = "armv7l" ] || [ "$UNAME_MACHINE" = "armv6l" ]; then
        export JAVA_HOME_DIRECTORY=/usr/lib/jvm/java-7-openjdk-armhf
    fi
fi

VERSION_FILE="$APPSCALE_HOME_RUNTIME"/VERSION
export APPSCALE_VERSION=$(grep AppScale "$VERSION_FILE" | sed 's/AppScale version \(.*\)/\1/')

PACKAGE_CACHE="/var/cache/appscale"

# Default directory for external library jars
APPSCALE_EXT="/usr/share/appscale/ext/"

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

# Download a package from a mirror if it's not already cached.
cachepackage() {
    CACHED_FILE="${PACKAGE_CACHE}/$1"
    mkdir -p ${PACKAGE_CACHE}
    if [ -f ${CACHED_FILE} ]; then
        MD5=($(md5sum ${CACHED_FILE}))
        if [ "$MD5" = "$2" ]; then
            return 0
        fi
    fi

    echo "Fetching $1 from $APPSCALE_PACKAGE_MIRROR"
    curl ${CURL_OPTS} -o ${CACHED_FILE} "${APPSCALE_PACKAGE_MIRROR}/$1"
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
*               -       nproc            32768
EOF
}

installappscaleprofile()
{
    DESTFILE=${DESTDIR}/etc/profile.d/appscale.sh
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE
export APPSCALE_HOME=${APPSCALE_HOME_RUNTIME}
export EC2_PRIVATE_KEY=${CONFIG_DIR}/certs/mykey.pem
export EC2_CERT=${CONFIG_DIR}/certs/mycert.pem
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
    mkdir -pv ${DESTDIR}${CONFIG_DIR}

    cat <<EOF | tee ${CONFIG_DIR}/home || exit
${APPSCALE_HOME_RUNTIME}
EOF
    # Create the global AppScale environment file.
    DESTFILE=${DESTDIR}${CONFIG_DIR}/environment.yaml
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

installjavajdk()
{
    # This makes jdk-7 the default JVM.
    update-alternatives --set java ${JAVA_HOME_DIRECTORY}/jre/bin/java
}

installappserverjava()
{
    JAVA_SDK_DIR="${APPSCALE_HOME}/AppServer_Java"

    JAVA_SDK_PACKAGE="appengine-java-sdk-1.8.4.zip"
    JAVA_SDK_PACKAGE_MD5="f5750b0c836870a3089096fd537a1272"
    cachepackage ${JAVA_SDK_PACKAGE} ${JAVA_SDK_PACKAGE_MD5}

    echo "Extracting Java SDK"
    unzip -q "${PACKAGE_CACHE}/${JAVA_SDK_PACKAGE}" -d ${JAVA_SDK_DIR}

    # Compile source file.
    (cd ${JAVA_SDK_DIR} && ant install && ant clean-build)

    if [ -n "$DESTDIR" ]; then
        # Delete unnecessary files.
        rm -rf ${JAVA_SDK_DIR}/src ${JAVA_SDK_DIR}/lib
    fi
}

installtornado()
{
    pipwrapper tornado==4.2.0
}

installflexmock()
{
    if [ "$DIST" = "precise" ]; then
        pipwrapper flexmock
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
    if [ "${UNAME_MACHINE}" = "x86_64" ]; then
        gem install zookeeper
    else
        # The current zookeeper gem has x86-specific assembly code.
        CUSTOM_ZK_GEM="zookeeper-1.4.11.gem"
        cachepackage ${CUSTOM_ZK_GEM} 2117f0814722715a3c765211842337eb
        gem install --local ${PACKAGE_CACHE}/${CUSTOM_ZK_GEM}
    fi
    sleep 1
    gem install json ${GEMOPT} -v 1.8.3
    sleep 1
    gem install soap4r-ruby1.9 ${GEMOPT}
    gem install httparty ${GEMOPT} -v 0.13.7
    gem install httpclient ${GEMOPT}
    # This is for the unit testing framework.
    gem install simplecov ${GEMOPT}
}

installphp54()
{
    # In Precise we have a too old version of php. We need at least 5.4.
    if [ "$DIST" = "precise" ]; then
        LC_ALL=C.UTF-8 add-apt-repository ppa:ondrej/php
        apt-get update
        # php5-cgi is needed to ensure apache2 won't be installed.
        apt-get install --force-yes -y php5-cgi php5.5
    fi
}

postinstallnginx()
{
    rm -fv /etc/nginx/sites-enabled/default
    chmod +x /root
}

installsolr()
{
    SOLR_VER=4.10.2
    SOLR_DIR="${APPSCALE_HOME}/SearchService/solr"
    mkdir -p ${SOLR_DIR}
    rm -rf "${SOLR_DIR}/solr"

    SOLR_PACKAGE="solr-${SOLR_VER}.tgz"
    SOLR_PACKAGE_MD5="a24f73f70e3fcf6aa8fda67444981f78"
    cachepackage ${SOLR_PACKAGE} ${SOLR_PACKAGE_MD5}
    tar xzf "${PACKAGE_CACHE}/${SOLR_PACKAGE}" -C ${SOLR_DIR}
    mv -v ${SOLR_DIR}/solr-${SOLR_VER} ${SOLR_DIR}/solr
}

installcassandra()
{
    CASSANDRA_VER=3.7

    CASSANDRA_PACKAGE="apache-cassandra-${CASSANDRA_VER}-bin.tar.gz"
    CASSANDRA_PACKAGE_MD5="39968c48cbb2a333e525f852db59fb48"
    cachepackage ${CASSANDRA_PACKAGE} ${CASSANDRA_PACKAGE_MD5}

    # Remove old Cassandra environment directory.
    rm -rf ${APPSCALE_HOME}/AppDB/cassandra

    CASSANDRA_DIR="/opt/cassandra"
    mkdir -p ${CASSANDRA_DIR}
    rm -rf ${CASSANDRA_DIR}/cassandra
    tar xzf "${PACKAGE_CACHE}/${CASSANDRA_PACKAGE}" -C ${CASSANDRA_DIR}
    mv -v ${CASSANDRA_DIR}/apache-cassandra-${CASSANDRA_VER} \
        ${CASSANDRA_DIR}/cassandra

    if ! id -u cassandra &> /dev/null ; then
        useradd cassandra
    fi
    chown -R cassandra ${CASSANDRA_DIR}
}

postinstallcassandra()
{
    mkdir -p ${CONFIG_DIR}/${APPSCALE_VERSION}
    touch ${CONFIG_DIR}/${APPSCALE_VERSION}/cassandra
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
        pipwrapper "python-memcached==1.53"
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
    if [ -e ${CONFIG_DIR}/VERSION ]; then
        mv ${CONFIG_DIR}/VERSION ${CONFIG_DIR}/VERSION-$(date --rfc-3339=date)
    fi
    cp ${APPSCALE_HOME}/VERSION ${CONFIG_DIR}
}

installrequests()
{
    if [ "$DIST" = "precise" ]; then
        pipwrapper requests
    fi
}

# pyOpenSSL is required for client SNI support on Python < 2.7.9.
installpyopenssl()
{
    if [ "$DIST" = "precise" ]; then
        # A pyOpenSSL dependency (cryptography) requires distribute. After that
        # is upgraded, setuptools and pkg_resources need to be reinstalled.
        pipwrapper distribute
        apt-get install --reinstall python-setuptools
        apt-get install --reinstall python-pkg-resources
        pipwrapper pyopenssl
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

installpsutil()
{
    case ${DIST} in
        precise|wheezy) pipwrapper psutil ;;
    esac
}

installapiclient()
{
    # The InfrastructureManager requires the Google API client.
    pipwrapper google-api-python-client==1.5.4
}

installgosdk()
{
    if [ ${UNAME_MACHINE} = "x86_64" ]; then
        GO_SDK_PACKAGE="go_appengine_sdk_linux_amd64-1.9.48.zip"
        GO_SDK_PACKAGE_MD5="b5c1a3eab1ba69993c3a35661ec3043d"
    else
        GO_SDK_PACKAGE="go_appengine_sdk_linux_386-1.9.48.zip"
        GO_SDK_PACKAGE_MD5="b6aad6a3cb2506dfe1067e06fb93f9fb"
    fi

    EXTRAS_DIR="/opt"
    cachepackage ${GO_SDK_PACKAGE} ${GO_SDK_PACKAGE_MD5}

    echo "Extracting Go SDK"
    # Remove existing SDK directory in case it's old.
    rm -rf ${EXTRAS_DIR}/go_appengine
    unzip -q ${PACKAGE_CACHE}/${GO_SDK_PACKAGE} -d ${EXTRAS_DIR}
}

installpycapnp()
{
    pipwrapper pycapnp
}

preplogserver()
{
    LOGSERVER_DIR="/opt/appscale/logserver"
    mkdir -p ${LOGSERVER_DIR}
    FILE_SRC="$APPSCALE_HOME_RUNTIME/LogService/logging.capnp"
    FILE_DEST="$APPSCALE_HOME_RUNTIME/AppServer/google/appengine/api/logservice/logging.capnp"
    cp ${FILE_SRC} ${FILE_DEST}
}

installtaskqueue()
{
    pip install --upgrade --no-deps ${APPSCALE_HOME}/AppTaskQueue[celery_gui]
    # Fill in new dependencies.
    # See pip.pypa.io/en/stable/user_guide/#only-if-needed-recursive-upgrade.
    pip install ${APPSCALE_HOME}/AppTaskQueue[celery_gui]
}

installdatastore()
{
    pip install --upgrade --no-deps ${APPSCALE_HOME}/AppDB
    pip install ${APPSCALE_HOME}/AppDB
}

prepdashboard()
{
    rm -rf ${APPSCALE_HOME}/AppDashboard/vendor
    pip install -t ${APPSCALE_HOME}/AppDashboard/vendor wstools==0.4.3
    pip install -t ${APPSCALE_HOME}/AppDashboard/vendor SOAPpy
    pip install -t ${APPSCALE_HOME}/AppDashboard/vendor python-crontab
}

upgradepip()
{
    # Versions older than Pip 7 did not correctly parse install commands for
    # local packages with optional dependencies.
    case "$DIST" in
        precise|wheezy|trusty)
            pipwrapper pip
            # Account for the change in the path to the pip binary.
            hash -r
            ;;
    esac
}

fetchclientjars()
{
    # This function fetches modified client jars for the MapReduce, Pipeline,
    # and GCS APIs. You can compile them using Maven from the following repos:
    # github.com/AppScale/appengine-mapreduce
    # github.com/AppScale/appengine-pipelines
    # github.com/AppScale/appengine-gcs-client
    mkdir -p ${APPSCALE_EXT}

    MAPREDUCE_JAR="appscale-mapreduce-0.8.5.jar"
    cachepackage ${MAPREDUCE_JAR} "93f5101fa6ec761b33f4bf2ac8449447"

    PIPELINE_JAR="appscale-pipeline-0.2.13.jar"
    cachepackage ${PIPELINE_JAR} "a6e4555c604a05897a48260429ce50c6"

    GCS_JAR="appscale-gcs-client-0.6.jar"
    cachepackage ${GCS_JAR} "a03671de058acc7ea41144976868765c"

    cp "${PACKAGE_CACHE}/${MAPREDUCE_JAR}" ${APPSCALE_EXT}
    cp "${PACKAGE_CACHE}/${PIPELINE_JAR}" ${APPSCALE_EXT}
    cp "${PACKAGE_CACHE}/${GCS_JAR}" ${APPSCALE_EXT}
}
