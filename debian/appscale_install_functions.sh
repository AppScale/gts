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

JAVA_VERSION="java-8-openjdk"

export UNAME_MACHINE=$(uname -m)
if [ -z "${JAVA_HOME_DIRECTORY-}" ]; then
    if [ "$UNAME_MACHINE" = "x86_64" ]; then
        export JAVA_HOME_DIRECTORY=/usr/lib/jvm/${JAVA_VERSION}-amd64
    elif [ "$UNAME_MACHINE" = "armv7l" ] || [ "$UNAME_MACHINE" = "armv6l" ]; then
        export JAVA_HOME_DIRECTORY=/usr/lib/jvm/${JAVA_VERSION}-armhf
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
    remote_file="${APPSCALE_PACKAGE_MIRROR}/$1"
    mkdir -p ${PACKAGE_CACHE}
    if [ -f ${CACHED_FILE} ]; then
        MD5=($(md5sum ${CACHED_FILE}))
        if [ "$MD5" = "$2" ]; then
            return 0
        else
            echo "Incorrect md5sum for ${CACHED_FILE}. Removing it."
            rm ${CACHED_FILE}
        fi
    fi

    echo "Fetching ${remote_file}"
    if ! curl ${CURL_OPTS} -o ${CACHED_FILE} --retry 5 -C - "${remote_file}";
    then
        echo "Error while downloading ${remote_file}"
        return 1
    fi

    MD5=($(md5sum ${CACHED_FILE}))
    if [ "$MD5" = "$2" ]; then
        return 0
    else
        echo "Unable to download ${remote_file}. Try downloading it "\
             "manually, copying it to ${CACHED_FILE}, and re-running the "\
             "build."
        rm ${CACHED_FILE}
        return 1
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

        SYSCTL_CONFIG="/etc/sysctl.d/10-appscale.conf"
        cat << EOF > ${SYSCTL_CONFIG}
net.netfilter.nf_conntrack_max = 262144
net.core.somaxconn = 20240
net.ipv4.tcp_tw_reuse = 0
net.ipv4.tcp_orphan_retries = 1
net.ipv4.tcp_fin_timeout = 25
net.ipv4.tcp_max_orphans = 8192
net.ipv4.ip_local_port_range = 32768 61000
EOF

        sysctl -p ${SYSCTL_CONFIG}
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

    # On distros with systemd, the open file limit must be adjusted for each
    # service.
    if which systemctl > /dev/null && [ "${IN_DOCKER}" != "yes" ]; then
        mkdir -p /etc/systemd/system/monit.service.d
        cat <<EOF > /etc/systemd/system/monit.service.d/override.conf
[Service]
LimitNOFILE=200000
EOF
        mkdir -p /etc/systemd/system/nginx.service.d
        cat <<EOF > /etc/systemd/system/nginx.service.d/override.conf
[Service]
LimitNOFILE=200000
EOF
        systemctl daemon-reload
    fi
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

    mkdir -pv /var/appscale/version_assets

    # This puts in place the logrotate rules.
    if [ -d /etc/logrotate.d/ ]; then
        cp ${APPSCALE_HOME}/common/appscale/common/templates/appscale-logrotate.conf \
            /etc/logrotate.d/appscale
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
    # This sets the default JVM.
    update-alternatives --set java ${JAVA_HOME_DIRECTORY}/jre/bin/java
}

installappserverjava()
{
    JAVA_SDK_DIR="${APPSCALE_HOME}/AppServer_Java"

    JAVA_SDK_PACKAGE="appengine-java-sdk-1.8.4.zip"
    JAVA_SDK_PACKAGE_MD5="f5750b0c836870a3089096fd537a1272"
    cachepackage ${JAVA_SDK_PACKAGE} ${JAVA_SDK_PACKAGE_MD5}

    # Remove older build target to prevent jar conflicts.
    (cd ${JAVA_SDK_DIR} && ant clean-all)

    echo "Extracting Java SDK"
    unzip -q "${PACKAGE_CACHE}/${JAVA_SDK_PACKAGE}" -d ${JAVA_SDK_DIR}
    EXTRACTED_SDK="${JAVA_SDK_DIR}/appengine-java-sdk-1.8.4"

    # The jar included in the 1.8.4 SDK cannot compile JSP files under Java 8.
    JSP_JAR="repackaged-appengine-eclipse-jdt-ecj.jar"
    JSP_JAR_MD5="e85db8329dccbd18b8174a3b99513393"
    cachepackage ${JSP_JAR} ${JSP_JAR_MD5}
    OLD_JAR="repackaged-appengine-jasper-jdt-6.0.29.jar"
    rm ${EXTRACTED_SDK}/lib/tools/jsp/${OLD_JAR}
    cp ${PACKAGE_CACHE}/${JSP_JAR} ${EXTRACTED_SDK}/lib/tools/jsp/${JSP_JAR}

    # Compile source file.
    (cd ${JAVA_SDK_DIR} && ant install && ant clean-build)

    if [ -n "$DESTDIR" ]; then
        # Delete unnecessary files.
        rm -rf ${JAVA_SDK_DIR}/src ${JAVA_SDK_DIR}/lib
    fi

    # Install Java 8 runtime.
    JAVA8_RUNTIME_PACKAGE="appscale-java8-runtime-1.9.75-1.zip"
    JAVA8_RUNTIME_MD5="aac2c857ac61d5506dc75e18367aa779"
    cachepackage ${JAVA8_RUNTIME_PACKAGE} ${JAVA8_RUNTIME_MD5}

    rm -rf /opt/appscale_java8_runtime

    echo "Extracting Java 8 runtime"
    unzip -q "${PACKAGE_CACHE}/${JAVA8_RUNTIME_PACKAGE}" -d /opt
}

installtornado()
{
    pipwrapper tornado==4.2.0
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

    # Rake >= 12.3.0 requires Ruby >= 2.
    ruby_major_version=$(ruby --version | awk '{print $2}' | head -c 1)
    if [ "${ruby_major_version}" -lt "2" ]; then
        gem install rake ${GEMOPT} -v 12.2.1
    else
        gem install rake ${GEMOPT}
    fi

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
    if [ "${ruby_major_version}" -lt "2" ]; then
        gem install json ${GEMOPT} -v 1.8.3
    else
        gem install json ${GEMOPT}
    fi
    sleep 1
    gem install soap4r-ng ${GEMOPT} -v 2.0.3
    gem install httparty ${GEMOPT} -v 0.14.0
    gem install httpclient ${GEMOPT}
    gem install posixpsutil ${GEMOPT}
    # This is for the unit testing framework.
    gem install simplecov ${GEMOPT}
}

postinstallnginx()
{
    rm -fv /etc/nginx/sites-enabled/default
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

installsolr7()
{
    SOLR_VER=7.6.0
    SOLR_PACKAGE="solr-${SOLR_VER}.tgz"
    SOLR_PACKAGE_MD5="6363337322523b68c377177b1232c49e"
    cachepackage ${SOLR_PACKAGE} ${SOLR_PACKAGE_MD5}

    SOLR_EXTRACT_DIR=/opt/
    SOLR_VAR_DIR=/opt/appscale/solr7/
    SOLR_ARCHIVE="${PACKAGE_CACHE}/${SOLR_PACKAGE}"

    tar xzf "${SOLR_ARCHIVE}" solr-${SOLR_VER}/bin/install_solr_service.sh --strip-components=2

    echo "Installing Solr ${SOLR_VER}."
    # -n  Do not start solr service after install.
    # -f  Upgrade Solr. Overwrite symlink and init script of previous installation.
    bash ./install_solr_service.sh "${SOLR_ARCHIVE}" \
              -d ${SOLR_VAR_DIR} \
              -i ${SOLR_EXTRACT_DIR} \
              -n -f
    update-rc.d solr disable
}

installcassandra()
{
    CASSANDRA_VER=3.11.2

    # The following is a Cassandra package built from source with the inclusion
    # of https://issues.apache.org/jira/browse/CASSANDRA-12942.
    CASSANDRA_PACKAGE="apache-cassandra-${CASSANDRA_VER}-w-12942-bin.tar.gz"
    CASSANDRA_PACKAGE_MD5="25a9039dba8fe7ffe5e5e560e65c1f6f"
    cachepackage ${CASSANDRA_PACKAGE} ${CASSANDRA_PACKAGE_MD5}

    # Remove old Cassandra environment directory.
    rm -rf ${APPSCALE_HOME}/AppDB/cassandra

    CASSANDRA_DIR="/opt/cassandra"
    CASSANDRA_DATA_DIR="/opt/appscale/cassandra"
    mkdir -p ${CASSANDRA_DIR}
    mkdir -p ${CASSANDRA_DATA_DIR}
    rm -rf ${CASSANDRA_DIR}/cassandra
    tar xzf "${PACKAGE_CACHE}/${CASSANDRA_PACKAGE}" -C ${CASSANDRA_DIR}
    mv -v ${CASSANDRA_DIR}/apache-cassandra-${CASSANDRA_VER} \
        ${CASSANDRA_DIR}/cassandra

    if ! id -u cassandra &> /dev/null ; then
        useradd cassandra
    fi
    chown -R cassandra ${CASSANDRA_DIR}
    chown -R cassandra ${CASSANDRA_DATA_DIR}
}

postinstallcassandra()
{
    mkdir -p ${CONFIG_DIR}/${APPSCALE_VERSION}
    touch ${CONFIG_DIR}/${APPSCALE_VERSION}/cassandra
}


installservice()
{
    # This must be absolute path of runtime.
    mkdir -pv ${DESTDIR}/etc/init.d/
    cp ${APPSCALE_HOME_RUNTIME}/AppController/scripts/appcontroller ${DESTDIR}/etc/init.d/appscale-controller
    chmod -v a+x ${DESTDIR}/etc/init.d/appscale-controller

    # Make sure the init script runs each time, so that it can start the
    # AppController on system reboots.
    update-rc.d -f appscale-controller defaults

    # Prevent monit from immediately restarting services at boot.
    cp ${APPSCALE_HOME}/AppController/scripts/appscale-unmonit.sh \
      /etc/init.d/appscale-unmonit
    chmod -v a+x /etc/init.d/appscale-unmonit
    update-rc.d appscale-unmonit defaults 19 21
}

postinstallservice()
{
    # Stop services shouldn't run at boot, then disable them.
    service memcached stop || true
    disableservice memcached

    ejabberdctl stop || true
    disableservice ejabberd
}

installzookeeper()
{
    # Use 2.4.0 to avoid NoNodeError for ChildrenWatches with no parents.
    pipwrapper "kazoo==2.4.0"
}

installpycrypto()
{
    pipwrapper pycrypto
}

postinstallzookeeper()
{
    service zookeeper stop || true
    disableservice zookeeper
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
    # Allow guest users to connect from other machines.
    if [ "${DIST}" = "xenial" ]; then
        RMQ_CONFIG="[{rabbit, [{loopback_users, []}]}]."
        echo ${RMQ_CONFIG} > /etc/rabbitmq/rabbitmq.config
    fi

    # Enable the management API.
    echo "[rabbitmq_management]." > /etc/rabbitmq/enabled_plugins

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

    # Set up template for formatting combined application log messages.
    cp ${APPSCALE_HOME}/common/appscale/common/templates/rsyslog-template.conf\
        /etc/rsyslog.d/09-appscale.conf

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

    # Monitor cron.
    if [ -e /etc/monit/conf-available/cron ] &&
            [ -e /etc/monit/conf-enabled ] &&
            [ ! -e /etc/monit/conf-enabled/cron ]; then
        ln -s /etc/monit/conf-available/cron /etc/monit/conf-enabled
    fi

    # Monit cannot start at boot time: in case of accidental reboot, it
    # would start processes out of order. The controller will restart
    # monit as soon as it starts.
    service monit stop
    disableservice monit
}

postinstallejabberd()
{
    # Install ejabberd authentication script.
    cp ${APPSCALE_HOME}/AppController/scripts/ejabberd_auth.py /etc/ejabberd
    chown ejabberd:ejabberd /etc/ejabberd/ejabberd_auth.py
    chmod +x /etc/ejabberd/ejabberd_auth.py

    # Disable ejabberd's apparmor profile.
    EJABBERD_PROFILE="/etc/apparmor.d/usr.sbin.ejabberdctl"
    if apparmor_status 2> /dev/null | grep "ejabberdctl" > /dev/null; then
        ln -s ${EJABBERD_PROFILE} /etc/apparmor.d/disable/
        apparmor_parser -R ${EJABBERD_PROFILE}
    fi
}

installapiclient()
{
    # The InfrastructureManager requires the Google API client.
    pipwrapper google-api-python-client==1.5.4
}

installgosdk()
{
    EXTRAS_DIR="/opt"
    GO_RUNTIME_DIR="${EXTRAS_DIR}/go_appengine"
    if [ ${UNAME_MACHINE} = "x86_64" ]; then
        GO_SDK_PACKAGE="go_appengine_sdk_linux_amd64-1.9.48.zip"
        GO_SDK_PACKAGE_MD5="b5c1a3eab1ba69993c3a35661ec3043d"
    elif [ ${UNAME_MACHINE} = "i386" ]; then
        GO_SDK_PACKAGE="go_appengine_sdk_linux_386-1.9.48.zip"
        GO_SDK_PACKAGE_MD5="b6aad6a3cb2506dfe1067e06fb93f9fb"
    else
        echo "Warning: There is no binary appscale-go-runtime package"
        echo "available for ${UNAME_MACHINE}. If you need support for Go"
        echo "applications, compile github.com/AppScale/appscale-go-runtime"
        echo "and install in ${GO_RUNTIME_DIR}/goroot."
        return 0
    fi

    cachepackage ${GO_SDK_PACKAGE} ${GO_SDK_PACKAGE_MD5}

    echo "Extracting Go SDK"
    # Remove existing SDK directory in case it's old.
    rm -rf ${GO_RUNTIME_DIR}
    unzip -q ${PACKAGE_CACHE}/${GO_SDK_PACKAGE} -d ${EXTRAS_DIR}
}

installpycapnp()
{
    pipwrapper pycapnp
}

installpymemcache()
{
    pipwrapper pymemcache
}

installpyyaml()
{
    # The python-yaml package on Xenial uses over 30M of memory.
    if [ "${DIST}" = "xenial" ]; then
        pipwrapper PyYAML
    fi
}

installsoappy()
{
    # This particular version is needed for
    # google.appengine.api.xmpp.unverified_transport, which imports
    # SOAPpy.HTTPWithTimeout.
    pipwrapper SOAPpy==0.12.22
}

preplogserver()
{
    LOGSERVER_DIR="/opt/appscale/logserver"
    mkdir -p ${LOGSERVER_DIR}
    FILE_SRC="$APPSCALE_HOME_RUNTIME/LogService/logging.capnp"
    FILE_DEST="$APPSCALE_HOME_RUNTIME/AppServer/google/appengine/api/logservice/logging.capnp"
    cp ${FILE_SRC} ${FILE_DEST}
}

installacc()
{
    pip install --upgrade --no-deps ${APPSCALE_HOME}/AppControllerClient
    pip install ${APPSCALE_HOME}/AppControllerClient
}

installcommon()
{
    pip install --upgrade --no-deps ${APPSCALE_HOME}/common
    pip install ${APPSCALE_HOME}/common
}

installadminserver()
{
    pip install --upgrade --no-deps ${APPSCALE_HOME}/AdminServer
    pip install ${APPSCALE_HOME}/AdminServer
}

installhermes()
{
    pip install --upgrade --no-deps ${APPSCALE_HOME}/Hermes
    pip install ${APPSCALE_HOME}/Hermes
}

installinfrastructuremanager()
{
    pip install --upgrade --no-deps ${APPSCALE_HOME}/InfrastructureManager
    pip install ${APPSCALE_HOME}/InfrastructureManager
}

installtaskqueue()
{
    rm -rf /opt/appscale_venvs/appscale_taskqueue/
    python -m virtualenv /opt/appscale_venvs/appscale_taskqueue/

    TASKQUEUE_PIP=/opt/appscale_venvs/appscale_taskqueue/bin/pip

    "${APPSCALE_HOME}/AppTaskQueue/appscale/taskqueue/protocols/compile_protocols.sh"

    TQ_DIR="${APPSCALE_HOME}/AppTaskQueue/"
    COMMON_DIR="${APPSCALE_HOME}/common"

    echo "Upgrading appscale-common.."
    "${TASKQUEUE_PIP}" install --upgrade --no-deps "${COMMON_DIR}"
    echo "Installing appscale-common dependencies if any missing.."
    "${TASKQUEUE_PIP}" install "${COMMON_DIR}"
    echo "Upgrading appscale-taskqueue.."
    "${TASKQUEUE_PIP}" install --upgrade --no-deps "${TQ_DIR}[celery_gui]"
    echo "Installing appscale-taskqueue dependencies if any missing.."
    "${TASKQUEUE_PIP}" install "${TQ_DIR}[celery_gui]"

    echo "appscale-taskqueue has been successfully installed."
}

installdatastore()
{
    pip install --upgrade --no-deps ${APPSCALE_HOME}/AppDB
    pip install ${APPSCALE_HOME}/AppDB
}

installapiserver()
{
    (cd APIServer && protoc --python_out=./appscale/api_server *.proto)
    # This package needs to be installed in a virtualenv because the protobuf
    # library conflicts with the google namespace in the SDK.
    mkdir -p /opt/appscale_venvs
    rm -rf /opt/appscale_venvs/api_server
    virtualenv /opt/appscale_venvs/api_server

    # The activate script fails under `set -u`.
    unset_opt=$(shopt -po nounset)
    set +u
    (source /opt/appscale_venvs/api_server/bin/activate && \
     pip install -U pip && \
     pip install ${APPSCALE_HOME}/AppControllerClient ${APPSCALE_HOME}/common \
     ${APPSCALE_HOME}/APIServer)
    eval ${unset_opt}
}

installsearch2()
{
    ANTLR_VER=4.7.2
    ANTLR_JAR="antlr-${ANTLR_VER}-complete.jar"
    ANTLR_JAR_MD5="58c9cdda732eabd9ea3e197fa7d8f2d6"
    cachepackage ${ANTLR_JAR} ${ANTLR_JAR_MD5}
    cp "${PACKAGE_CACHE}/${ANTLR_JAR}" "/usr/local/lib/${ANTLR_JAR}"

    # Create virtual environment based on Python 3
    rm -rf /opt/appscale_venvs/search2
    python3 -m venv /opt/appscale_venvs/search2/

    # Let the script compile protocols and parser and install package using pip.
    "${APPSCALE_HOME}/SearchService2/build-scripts/ensure_searchservice2.sh" \
        /opt/appscale_venvs/search2/bin/pip
}

prepdashboard()
{
    rm -rf ${APPSCALE_HOME}/AppDashboard/vendor
    pip install -t ${APPSCALE_HOME}/AppDashboard/vendor wstools==0.4.3
    pip install -t ${APPSCALE_HOME}/AppDashboard/vendor SOAPpy
    pip install -t ${APPSCALE_HOME}/AppDashboard/vendor python-crontab
    pip install -t ${APPSCALE_HOME}/AppDashboard/vendor \
        ${APPSCALE_HOME}/AppControllerClient
}

upgradepip()
{
    # Versions older than Pip 7 did not correctly parse install commands for
    # local packages with optional dependencies. Versions greater than Pip 9
    # do not allow replacing packages installed by the distro.
    case "$DIST" in
        jessie)
            # The system's pip does not allow updating itself.
            easy_install --upgrade 'pip<10.0.0b1'
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
