#/bin/sh
# Common functions for build and installer
#
# This should work in bourne shell (/bin/sh)
# The function name should not include non alphabet character.
#
# Written by Yoshi <nomura@pobox.com>

set -e

if [ -z "$APPSCALE_HOME_RUNTIME" ]; then
    export APPSCALE_HOME_RUNTIME=/opt/appscale
fi

if [ -z "$APPSCALE_PACKAGE_MIRROR" ]; then
    export APPSCALE_PACKAGE_MIRROR=http://s3.amazonaws.com/appscale-build
fi

#if [ -z "$APPSCALE_HOME" ]; then
 #  export APPSCALE_HOME= /root/appscale/
#fi 
export APPSCALE_VERSION=1.9.0

increaseconnections()
{
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
    echo "MAILTO=\"\"" >> crontab.tmp
    echo "*/5 * * * * /root/appscale/ntp.sh" >> crontab.tmp
    crontab crontab.tmp
    rm crontab.tmp
}

installpython27()
{
    cd /usr/local
    wget $APPSCALE_PACKAGE_MIRROR/Python-2.7.3.tgz
    tar zxvf Python-2.7.3.tgz
    rm /usr/local/Python-2.7.3.tgz
}

installnumpy()
{
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    wget $APPSCALE_PACKAGE_MIRROR/appscale-numpy-1.7.0.tar.gz
    tar zxvf appscale-numpy-1.7.0.tar.gz
    cd numpy-1.7.0
    /usr/local/Python-2.7.3/python setup.py install
    cd ..
    rm appscale-numpy-1.7.0.tar.gz
    rm -fdr numpy-1.7.0
}

installmatplotlib()
{
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    wget $APPSCALE_PACKAGE_MIRROR/matplotlib-1.2.0.tar.gz
    tar zxvf matplotlib-1.2.0.tar.gz
    cd matplotlib-1.2.0
    /usr/local/Python-2.7.3/python setup.py install
    cd ..
    rm -fdr matplotlib-1.2.0*
}

installPIL()
{
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    wget $APPSCALE_PACKAGE_MIRROR/Imaging-1.1.7.tar.gz
    tar zxvf Imaging-1.1.7.tar.gz
    cd Imaging-1.1.7
    /usr/local/Python-2.7.3/python setup.py install
    cd ..
    rm -fdr Imaging-1.1.7*
}

installpycrypto()
{
    easy_install pycrypto
}

installlxml()
{
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    git clone git://github.com/lxml/lxml.git lxml
    cd lxml
    /usr/local/Python-2.7.3/python ez_setup.py lxml
    cd ..
    rm -fdr lxml
    rm -fdr /usr/local/lib/python2.7/site-packages/lxml-*-py2.7-linux-x86_64.egg/EGG-INFO/
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

updatealternatives()
{
# we don't need to set for sh
#update-alternatives --install /bin/sh sh /bin/dash 1
#update-alternatives --install /bin/sh sh /bin/bash 1
#update-alternatives --set sh /bin/bash
	:;
}

installappscaleprofile()
{
#    mkdir -p ${APPSCALE_HOME}
#    cat > ${APPSCALE_HOME}/appscale.env <<EOF
#export APPSCALE_HOME=${APPSCALE_HOME_RUNTIME}
#export HOME=\$APPSCALE_HOME
#EOF
    DESTFILE=${DESTDIR}/etc/profile.d/appscale.sh
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE
export APPSCALE_HOME=${APPSCALE_HOME_RUNTIME}
for jpath in\
 /usr/lib/jvm/java-7-oracle\
 /usr/lib/jvm/default-java
do
  if [ -e \$jpath ]; then
    export JAVA_HOME=\$jpath
    break
  fi
done
export PYTHON_EGG_CACHE=/tmp/.python_eggs
export EC2_PRIVATE_KEY=\${APPSCALE_HOME}/.appscale/certs/mykey.pem
export EC2_CERT=\${APPSCALE_HOME}/.appscale/certs/mycert.pem
EOF
# enable to load AppServer and AppDB modules. It must be before the python-support.
    DESTFILE=${DESTDIR}/usr/lib/python2.6/dist-packages/appscale_appserver.pth
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE
${APPSCALE_HOME_RUNTIME}/AppDB
${APPSCALE_HOME_RUNTIME}/AppServer
EOF
# enable to load site-packages of Python
    DESTFILE=${DESTDIR}/usr/local/lib/python2.6/dist-packages/site_packages.pth
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE
/usr/lib/python2.6/site-packages
EOF

    # for lucid
    if [ "$DIST" = "lucid" ]; then
	# enable memcached api
	SITE_DIR=${DESTDIR}/usr/local/lib/python2.5/site-packages
	mkdir -pv ${SITE_DIR}
	DESTFILE=${SITE_DIR}/pyshared.pth
	echo "Generating $DESTFILE"
	cat <<EOF | tee $DESTFILE
/usr/share/pyshared
EOF
	# enable python imaging native library
	DESTFILE=${SITE_DIR}/PIL-lib.pth
	echo "Generating $DESTFILE"
	cat <<EOF | tee $DESTFILE
/usr/lib/python2.6/dist-packages/PIL
EOF
       # Add fpconst into python2.5
       cp /usr/lib/pymodules/python2.6/fpconst.py /usr/lib/python2.5/
    fi

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
JAVA_HOME: /usr/lib/jvm/java-7-oracle
EOF
    mkdir -pv /var/log/appscale
    mkdir -pv /var/appscale/
}

installthrift_fromsource()
{
    export THRIFT_VER=0.5.0

    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    # apache 0.2.0
    wget $APPSCALE_PACKAGE_MIRROR/thrift-${THRIFT_VER}.tar.gz
    tar zxfv thrift-${THRIFT_VER}.tar.gz
    rm -v thrift-${THRIFT_VER}.tar.gz
    pushd thrift-${THRIFT_VER}
    CONFIG_SHELL=/bin/bash /bin/bash ./configure --without-csharp --without-haskell --without-ocaml --without-php --without-php_extension --prefix=/usr/local
    make
# install native library and include files to DESTDIR.
    make install
# python library
    pushd lib/py
    python setup.py install --prefix=${DESTDIR}/usr
    popd

    popd
    rm -rfv thrift-${THRIFT_VER}
}

postinstallthrift_fromsource()
{
  :;
}

# using egg

installthrift()
{
    easy_install -U thrift
    DISTP=/usr/local/lib/python2.6/dist-packages
    if [ -z "$(find ${DISTP} -name Thrift-*.egg)" ]; then
	echo "Fail to install python thrift client. Please retry."
	exit 1
    fi
    if [ -n "$DESTDIR" ]; then
	mkdir -pv ${DESTDIR}${DISTP}
	cp -rv ${DISTP}/Thrift-*.egg ${DESTDIR}${DISTP}
    fi
}

postinstallthrift()
{
    # just enable thrift library.
    easy_install thrift
}

installjavajdk()
{
    # Since Oracle requires you to accept terms and conditions, have to pull from webupd8team
    sudo echo oracle-java7-installer shared/accepted-oracle-license-v1-1 select true | sudo /usr/bin/debconf-set-selections
    sudo add-apt-repository ppa:webupd8team/java
    sudo apt-get update
    sudo apt-get install -y oracle-java7-installer
    export JAVA_HOME=/usr/lib/jvm/java-7-oracle
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
    DISTP=/usr/local/lib/python2.6/dist-packages
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
    # just enable tornado
    easy_install tornado
}

installhaproxy()
{
    # 1.4.4 or newer version of haproxy is needed for AppServer Java.
    # because there is jetty keep-alive issue.
    HAPROXY_VER=1.4.4

    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    rm -rfv haproxy*
# download from appscale site
    wget $APPSCALE_PACKAGE_MIRROR/haproxy-${HAPROXY_VER}.tar.gz
    tar zxvf haproxy-${HAPROXY_VER}.tar.gz
    rm -v haproxy-${HAPROXY_VER}.tar.gz

    pushd haproxy-${HAPROXY_VER}
    # All Ubuntu is linux26 now
    make TARGET=linux26
    make install-bin PREFIX=/usr
    if [ ! -e ${DESTDIR}/usr/sbin/haproxy ]; then
	echo "Fail to install haproxy. Please retry."
	exit 1
    fi
    popd
    rm -rv haproxy-${HAPROXY_VER}

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

installtmux()
{
    # First, install tmux (do it from source to get the newest features)
    cd ${APPSCALE_HOME}
    wget $APPSCALE_PACKAGE_MIRROR/tmux-1.6.tar.gz
    tar zxvf tmux-1.6.tar.gz
    cd tmux-1.6
    ./configure
    make
    make install
    cd ${APPSCALE_HOME}
    rm -rf tmux-1.6 tmux-1.6.tar.gz
    
    # Finally, grab our tmux config file and put it in the right place
    cd
    wget $APPSCALE_PACKAGE_MIRROR/tmux.conf -O .tmux.conf
}

postinstalltmux()
{
    :;
}

# deb package version
installhypertable()
{
    HT_VER=0.9.5.5
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    ARCH=`uname -m`
    if [ "$ARCH" = "i686" ]; then
	ARCH="i386"
    fi
    gem install titleize
    # extract binary files and repackage it when making deb
    wget $APPSCALE_PACKAGE_MIRROR/hypertable-${HT_VER}-linux-${ARCH}.deb -O hypertable-${HT_VER}.deb
    dpkg-deb --vextract hypertable-${HT_VER}.deb ${DESTDIR}/
    rm hypertable-${HT_VER}.deb

    # enable to load hypertable client of python
    DESTFILE=${DESTDIR}/usr/local/lib/python2.6/dist-packages/hypertable_client.pth
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE
/opt/hypertable/${HT_VER}/lib/py
/opt/hypertable/${HT_VER}/lib/py/gen-py
EOF
   # hypertable package conflicts appscale/AppDB/hypertable,
   # so we must place it in appscale.
   # this must be absolute path of runtime.
    ln -sfv /opt/hypertable/${HT_VER}/lib/py/hypertable/thriftclient.py ${APPSCALE_HOME}/AppDB/hypertable/
    ln -fsv /usr/bin/thin1.8 /usr/bin/thin
    ln -fsv /opt/hypertable/${HT_VER}  /opt/hypertable/current
}

postinstallhypertable()
{
    mkdir -p ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}
    touch ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}/hypertable
}

installhypertablemonitoring()
{
    ARCH=`uname -m`
    if [ "$ARCH" = "i686" ]; then
	ARCH="i386"
    fi
    GEMDEST=${DESTDIR}/var/lib/gems/1.8
    GEMOPT="--no-rdoc --no-ri --bindir ${DESTDIR}/usr/bin --install-dir ${GEMDEST}"
    # For hypertable monitoring
    gem install sinatra rack thin json ${GEMOPT}
    cd ${APPSCALE_HOME}/downloads
    wget $APPSCALE_PACKAGE_MIRROR/rrdtool-1.4.4.tar.gz
    tar zxvf rrdtool-1.4.4.tar.gz
    cd rrdtool-1.4.4/
    ./configure 
    make
    make install
    cd bindings/ruby/
    ARCHFLAGS="-arch ${ARCH}" ruby extconf.rb --with-rrd-dir=/opt/rrdtool-1.4.4/
    make
    make install
    cp RRD.so /usr/local/lib/site_ruby/1.8/${ARCH}-linux/RRD.so
}

posthypertablemonitoring()
{
  :;
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
    gem install neptune right_aws ${GEMOPT}
    sleep 1
    gem install god redgreen Ruby-MemCache ${GEMOPT}
    sleep 1
    #if [ ! -e ${DESTDIR}/usr/bin/god ]; then
    #	echo "Fail to install god. Please Retry."
    #	exit 1
    #fi
    gem install -v=2.3.4 rails ${GEMOPT}
    sleep 1
    gem install gem_plugin mongrel ${GEMOPT}
    sleep 1
    gem install mongrel_cluster ${GEMOPT}
    #sleep 1
    #if [ ! -e ${DESTDIR}/usr/bin/mongrel_rails ]; then
    #	echo "Fail to install mongrel rails. Please Retry."
    #	exit 1
    #fi
    # This is for the Hypertable.
    gem install capistrano ${GEMOPT}
    sleep 1
    gem install json ${GEMOPT}
    sleep 1
    #if [ ! -e ${DESTDIR}/usr/bin/cap ]; then
    #	echo "Fail to install capistrano. Please Retry."
    #	exit 1
    #fi

    # This is for Neptune's Babel App Engine pull queue interface
    # which is just REST, but httparty does such a nice job compared
    # to previously used things
    gem install -v=0.8.3 httparty ${GEMOPT}

    # This is for the unit testing framework
    gem install -v=1.0.4 flexmock ${GEMOPT}
    gem install -v=1.0.0 rcov ${GEMOPT}

}

postinstallgems()
{
    ln -sf /var/lib/gems/1.8/bin/neptune /usr/bin/neptune
#gem update
#gem install god redgreen
#gem install -v=2.3.4 rails
#gem install mongrel mongrel_cluster
#gem install -y capistrano
# create symbolic link
#test -e /usr/bin/mongrel_rails || ln -s /var/lib/gems/1.8/bin/mongrel_rails /usr/bin/
}

installmonitoring()
{
    cd ${APPSCALE_HOME}/AppMonitoring
    mkdir -p /var/lib/collectd/rrd
    RAILS_ENV=production rake gems:build:force
    RAILS_ENV=production rake db:migrate
}

postinstallmonitoring()
{
    :;
}

installnginx()
{
    NGINX_VERSION=1.2.6
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    wget $APPSCALE_PACKAGE_MIRROR/nginx-${NGINX_VERSION}.tar.gz
    tar zxvf nginx-${NGINX_VERSION}.tar.gz
    rm -v nginx-${NGINX_VERSION}.tar.gz
    pushd nginx-${NGINX_VERSION}
    wget $APPSCALE_PACKAGE_MIRROR/v0.23rc2.tar.gz
    tar zxvf v0.23rc2.tar.gz
    ./configure --add-module=./chunkin-nginx-module-0.23rc2/ --with-http_ssl_module --with-http_gzip_static_module
    make
    make install
    popd
    rm -rv nginx-${NGINX_VERSION}
}

# This function is called from postinst.core, so we don't need to use DESTDIR
postinstallnginx()
{
    cd ${APPSCALE_HOME}
    mkdir -p /usr/local/nginx/sites-enabled/
    cp -v AppDashboard/setup/load-balancer.conf /usr/local/nginx/sites-enabled/
    rm -fv /usr/local/nginx/sites-enabled/default
    chmod +x /root
}

installhadoop()
{
    HADOOP_VER=0.20.2-cdh3u3
  
    mkdir -pv ${APPSCALE_HOME}/AppDB
    cd ${APPSCALE_HOME}/AppDB
    rm -rfv hadoop-${HADOOP_VER}
    wget $APPSCALE_PACKAGE_MIRROR/hadoop-${HADOOP_VER}.tar.gz -O hadoop-${HADOOP_VER}.tar.gz
    tar xvzf hadoop-${HADOOP_VER}.tar.gz
    rm -v hadoop-${HADOOP_VER}.tar.gz
    cd hadoop-${HADOOP_VER}
    DESTFILE=./conf/hadoop-env.sh
    echo "Appending $DESTFILE"
    cat <<EOF | tee -a $DESTFILE
. /etc/profile.d/appscale.sh
export HADOOP_HOME=\${APPSCALE_HOME}/AppDB/hadoop-${HADOOP_VER}
export HADOOP_HEAPSIZE=2000
export HADOOP_NAMENODE_USER=root
EOF

    # This patch fixes WrongFS issue
    patch -p0 -i ../hadoop/patch/hadoop-hbase.patch

    # build new jar
    ant clean
    ant jar
    # Use the new jar 
    cp -v build/hadoop-core-${HADOOP_VER}.jar ./hadoop-core-${HADOOP_VER}.jar
    rm -rfv build

    # Replace the main script with one that allows hadoop to be run as root
    cp ../hadoop/templates/hadoop ./bin/

    # use precompiled binary
    ARCH=`uname -m`
    if [ "$ARCH" = "x86_64" ]; then
      HADOOP_CLIB="Linux-amd64-64"
    elif [ "$ARCH" = "i686" -o "$ARCH" = "i386" ]; then
      HADOOP_CLIB="Linux-i386-32"
    else
        echo "$ARCH is not supported by Hadoop."
        exit 1
    fi

    if [ -n "${DESTDIR}" ]; then
        # delete unnecessary files.
	rm -rv src docs
    fi
}

postinstallhadoop()
{
    :;
#    ldconfig
}

installhbase()
{
    HBASE_VER=0.90.4-cdh3u3
    HADOOP_VER=0.20.2-cdh3u3

    mkdir -pv ${APPSCALE_HOME}/AppDB/hbase
    cd ${APPSCALE_HOME}/AppDB/hbase
    rm -rfv hbase-${HBASE_VER}
    wget $APPSCALE_PACKAGE_MIRROR/hbase-${HBASE_VER}-rebuilt.tar.gz -O hbase-${HBASE_VER}.tar.gz

    tar zxvf hbase-${HBASE_VER}.tar.gz
    rm -v hbase-${HBASE_VER}.tar.gz
    # Clean out the maven repository
    rm -rfd ~/.m2/
    cd
    wget $APPSCALE_PACKAGE_MIRROR/maven_repos.tar.gz
    tar zxvf maven_repos.tar.gz
    rm -rv maven_repos.tar.gz 
    ######
    # What we did to create the tar'ed version of HBase: See AppScale 1.5 
    ####
    cd ~
}

postinstallhbase()
{
    mkdir -p ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}
    touch ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}/hbase
}

installcassandra()
{
    CASSANDRA_VER=1.2.5
    PYCASSA_VER=1.3.0
    cd /lib 
    wget $APPSCALE_PACKAGE_MIRROR/jamm-0.2.2.jar
    
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
   # directories where Cassandra should libstore data on disk.
    #data_file_directories:
    mkdir -p /var/appscale/cassandra/data
    chmod 777 /var/appscale/cassandra/data

    # commit log
    #commitlog_directory: 
    mkdir -p /var/appscale/cassandra/commitlog
    chmod 777 /var/appscale/cassandra/commitlog

    # saved caches
    #saved_caches_directory: 
    mkdir -p /var/appscale/cassandra/saved_caches
    chmod 777 /var/appscale/cassandra/saved_caches

    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    wget $APPSCALE_PACKAGE_MIRROR/pycassa-${PYCASSA_VER}.tar.gz
    tar zxvf pycassa-${PYCASSA_VER}.tar.gz  
    cd pycassa-${PYCASSA_VER}
    python setup.py install
    cd ..
    rm -fdr pycassa-${PYCASSA_VER}
    rm -fdr pycassa-${PYCASSA_VER}.tar.gz 
}

postinstallcassandra()
{
    mkdir -p ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}
    touch ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}/cassandra
}


installprotobuf_fromsource()
{
    PROTOBUF_VER=2.3.0
    # install protobuf 2.3.0. we need egg version for python.
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    wget $APPSCALE_PACKAGE_MIRROR/protobuf-${PROTOBUF_VER}.tar.gz
    tar zxvf protobuf-${PROTOBUF_VER}.tar.gz
    rm -v protobuf-${PROTOBUF_VER}.tar.gz
    pushd protobuf-${PROTOBUF_VER}
    ./configure --prefix=/usr
    make
    make check
    make install
    pushd python
# protobuf could not be installed in the different root
#    python setup.py install --prefix=${DESTDIR}/usr
    python setup.py bdist_egg
# copy the egg file
    DISTP=${DESTDIR}/usr/local/lib/python2.6/dist-packages
    mkdir -pv ${DISTP}
    cp -v dist/protobuf-*.egg ${DISTP}
    popd
    popd
    rm -rv protobuf-${PROTOBUF_VER}
}

installprotobuf()
{
# make protobuf module loadable
# this is not needed when we use egg to install protobuf.
    mkdir -pv ${APPSCALE_HOME}/AppServer/google
    # this should be absolute path of runtime.
    ln -sfv /var/lib/python-support/python2.6/google/protobuf ${APPSCALE_HOME}/AppServer/google/
}

postinstallprotobuf()
{
    :;
}

installpig()
{
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    wget http://apache.deathculture.net/hadoop/pig/pig-0.5.0/pig-0.5.0.tar.gz
    tar zxvf pig-0.5.0.tar.gz
    rm -v pig-0.5.0.tar.gz
    cd pig-0.5.0
    mkdir tmp
    cp -v pig-0.5.0-core.jar tmp/
    cd tmp
    jar xvf pig-0.5.0-core.jar
    rm -rfv pig-0.5.0-core.jar
    /bin/cp -fv ~/appscale/AppDB/hadoop-0.20.2/build/classes/org/apache/hadoop/hdfs/* ${APPSCALE_HOME}/downloads/pig-0.5.0/tmp/org/apache/hadoop/hdfs/
    jar cvf ../pig-0.5.0-core.jar ./*
    rm -rfv ./*
    wget $APPSCALE_PACKAGE_MIRROR/pigtutorial.tar.gz
    tar zxvf pigtutorial.tar.gz
    DESTFILE=${DESTDIR}/etc/profile.d/pig.sh
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE
. /etc/profile.d/appscale.sh
export PIG_CLASSPATH=\$APPSCALE_HOME/downloads/pig-0.5.0/pig-0.5.0-core.jar:\$APPSCALE_HOME/AppDB/hadoop-0.20.2/conf
EOF
}

postinstallpig()
{
    :;
}

installservice()
{
    # this must be absolete path of runtime
    mkdir -pv ${DESTDIR}/etc/init.d/
    ln -sfv ${APPSCALE_HOME_RUNTIME}/appscale-controller.sh ${DESTDIR}/etc/init.d/appscale-controller
    chmod -v a+x ${APPSCALE_HOME}/appscale-controller.sh
    ln -sfv ${APPSCALE_HOME_RUNTIME}/appscale-monitoring.sh ${DESTDIR}/etc/init.d/appscale-monitoring
    chmod -v a+x ${APPSCALE_HOME}/appscale-monitoring.sh
}

postinstallservice()
{

    # stop unnecessary services
#    service nginx stop || true
#    service haproxy stop || true
    service memcached stop || true
    service collectd stop || true

    # remove unnecessary service
#    update-rc.d -f nginx remove || true
#    update-rc.d -f haproxy remove || true
    update-rc.d -f memcached remove || true
    update-rc.d -f collectd remove || true

    ejabberdctl stop || true
    update-rc.d -f ejabberd remove || true
}

installzookeeper()
{
    # 3.3.0 or less has known problem, so we must use 3.3.1 or more.
    # https://issues.apache.org/jira/browse/ZOOKEEPER-742

    ZK_VER=3.3.4-cdh3u3
    ZK_VER2=3.3.4

    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads

    wget $APPSCALE_PACKAGE_MIRROR/zookeeper-${ZK_VER}.tar.gz
    tar zxvf zookeeper-${ZK_VER}.tar.gz

    cd zookeeper-${ZK_VER}
    # build java library, replace the compiliability to 1.7 since Java7 cannot compile to 1.5
    sed -i 's/1.5/1.7/g' build.xml
    ant
    ant compile_jute
    #if [ ! -e build/zookeeper-${ZK_VER}.jar ]; then
    #   echo "Fail to make zookeeper java jar. Please retry."
    #   exit 1
    #fi

    # build c library
    #pushd src/c
    cd src/c
#    sed -i 's/AM_PATH_CPPUNIT/:;#AM_PATH_CPPUNIT/g' configure.ac
    autoreconf -if
    ./configure --prefix=/usr
    make
    make install
    if [ ! -e ${DESTDIR}/usr/lib/libzookeeper_mt.a ]; then
        echo "Fail to install libzookeeper. Please retry."
        exit 1
    fi
    cd ../..

    # apply memory leak patch of zkpython TODO check if 3.3.4-cdh3u3 needs it
    #patch -p0 -i ${APPSCALE_HOME}/AppDB/zkappscale/patch/zkpython-memory.patch

    # python library
    easy_install kazoo

    # install java library
    mkdir -pv ${DESTDIR}/usr/share/java
    cp -v build/zookeeper-${ZK_VER2}.jar ${DESTDIR}/usr/share/java
    ln -sfv zookeeper-${ZK_VER2}.jar ${DESTDIR}/usr/share/java/zookeeper.jar

    # install config files and service.
    BASEURL=http://appscale-build.s3-website-us-east-1.amazonaws.com
    wget ${BASEURL}/zookeeper_3.2.2+dfsg3-3_all.deb -O zookeeper.deb
    dpkg-deb --vextract zookeeper.deb ${DESTDIR}/
    rm -v zookeeper.deb
    wget ${BASEURL}/zookeeperd_3.2.2+dfsg3-3_all.deb -O zookeeperd.deb
    dpkg-deb --vextract zookeeperd.deb ${DESTDIR}/
    rm -v zookeeperd.deb

    cd ${APPSCALE_HOME}/downloads
    rm -rv zookeeper-${ZK_VER}
    rm -fdr zookeeper-${ZK_VER}.tar.gz

    mkdir -pv ${DESTDIR}/var/run/zookeeper
    mkdir -pv ${DESTDIR}/var/lib/zookeeper
    mkdir -pv ${DESTDIR}/etc/zookeeper/conf
}

# only for jaunty and karmic

installzookeeper_deb()
{
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads

    ARCH=`uname -m`
    if [ "$ARCH" = "x86_64" ]; then
	ARCH="amd64"
    fi
    if [ "$ARCH" = "i686" ]; then
	ARCH="i386"
    fi

    # repackage ZooKeeper binary
    BASEURL=http://appscale-build.s3-website-us-east-1.amazonaws.com
    wget ${BASEURL}/liblog4j1.2-java_1.2.15-11_all.deb -O liblog4j.deb
    dpkg-deb --vextract liblog4j.deb ${DESTDIR}/
    rm -v liblog4j.deb
    wget ${BASEURL}/libzookeeper-java_3.2.2+dfsg3-3_all.deb -O libzookeeper-java.deb
    dpkg-deb --vextract libzookeeper-java.deb ${DESTDIR}/
    rm -v libzookeeper-java.deb
    wget ${BASEURL}/libzookeeper2_3.2.2+dfsg3-3_${ARCH}.deb -O libzookeeper2.deb
    dpkg-deb --vextract libzookeeper2.deb ${DESTDIR}/
    rm -v libzookeeper2.deb
    wget ${BASEURL}/python-zookeeper_3.2.2+dfsg3-3_${ARCH}.deb -O python-zookeeper.deb
    dpkg-deb --vextract python-zookeeper.deb ${DESTDIR}/
    rm -v python-zookeeper.deb

    wget ${BASEURL}/zookeeper-bin_3.2.2+dfsg3-3_${ARCH}.deb -O zookeeper-bin.deb
    dpkg-deb --vextract zookeeper-bin.deb ${DESTDIR}/
    rm -v zookeeper-bin.deb
    wget ${BASEURL}/zookeeper_3.2.2+dfsg3-3_all.deb -O zookeeper.deb
    dpkg-deb --vextract zookeeper.deb ${DESTDIR}/
    rm -v zookeeper.deb
    wget ${BASEURL}/zookeeperd_3.2.2+dfsg3-3_all.deb -O zookeeperd.deb
    dpkg-deb --vextract zookeeperd.deb ${DESTDIR}/
    rm -v zookeeperd.deb

    mkdir -pv ${DESTDIR}/var/run/zookeeper
    mkdir -pv ${DESTDIR}/var/lib/zookeeper
    mkdir -pv ${DESTDIR}/etc/zookeeper/conf
# enable to load python-zookeeper
    DESTFILE=${DESTDIR}/usr/local/lib/python2.6/dist-packages/pyshared2.6.pth
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE
/usr/lib/pyshared/python2.6
EOF
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
    rm -fdr  setuptools-0.6c11*
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
#    ssh-copy-id -i /root/.ssh/id_rsa.pub root@localhost
}

installcelery()
{
  easy_install -U Celery
  easy_install -U Flower
}

installrabbitmq()
{
   # RabbitMQ is installed via apt-get
   # Install the python client for rabbitmq
   PIKA_VERSION=0.9.9p0
   mkdir -pv ${APPSCALE_HOME}/downloads
   cd ${APPSCALE_HOME}/downloads
   rm -fr pika-master
   wget $APPSCALE_PACKAGE_MIRROR/pika-${PIKA_VERSION}.zip
   unzip pika-${PIKA_VERSION}.zip
   cd pika-master
   cp -r pika /usr/share/pyshared
   cd ..
   rm pika-${PIKA_VERSION}.zip
   rm -fr pika-master
}
postinstallrabbitmq()
{
    # After install it starts up, shut it down
    rabbitmqctl stop || true
    update-rc.d -f rabbitmq remove || true
    update-rc.d -f rabbitmq-server remove || true
}
