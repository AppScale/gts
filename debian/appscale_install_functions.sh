#/bin/sh
# Common functions for build and installer
#
# This should work in bourne shell (/bin/sh)
# The function name should not include non alphabet character.
#
# Written by Yoshi <nomura@pobox.com>

if [ -z "$APPSCALE_HOME_RUNTIME" ]; then
    export APPSCALE_HOME_RUNTIME=/opt/appscale
fi
#if [ -z "$APPSCALE_HOME" ]; then
 #  export APPSCALE_HOME= /root/appscale/
#fi 
export APPSCALE_VERSION=1.6.4

increaseconnections()
{
    echo "net.core.somaxconn = 20240" >> /etc/sysctl.conf
    echo "net.ipv4.netfilter.ip_conntrack_max = 196608" >> /etc/sysctl.conf
    echo "net.core.somaxconn = 20240" >> /etc/sysctl.conf
    echo "net.ipv4.netfilter.ip_conntrack_max = 196608" >> /etc/sysctl.conf
    echo "net.ipv4.tcp_tw_recycle = 0" >> /etc/sysctl.conf
    echo "net.ipv4.tcp_tw_reuse = 0" >> /etc/sysctl.conf
    echo "net.ipv4.tcp_orphan_retries = 1" >> /etc/sysctl.conf
    echo "net.ipv4.tcp_fin_timeout = 25" >> /etc/sysctl.conf
    echo "net.ipv4.tcp_max_orphans = 8192" >> /etc/sysctl.conf
    echo "net.ipv4.ip_local_port_range = 32768    61000" >> /etc/sysctl.conf
    echo "net.netfilter.nf_conntrack_max = 262144" >> /etc/sysctl.conf

    /sbin/sysctl -p /etc/sysctl.conf 
}

sethosts()
{
    cp -v /etc/hosts /etc/hosts.orig
    HOSTNAME=`hostname`
    echo "Generating /etc/hosts"
    cat <<EOF | tee /etc/hosts || exit 1
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
patchxmpp()
{
    PYTHON26_XMPP=/usr/lib/python2.6/dist-packages/xmpp/
    PYTHON25_XMPP=/usr/lib/python2.5/site-packages/xmpp/
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    wget http://appscale.cs.ucsb.edu/appscale_files/xmpp/transports.py || exit 1
    cp transports.py ${PYTHON25_XMPP}/
    mv transports.py ${PYTHON26_XMPP}/
}
setulimits()
{
    cat <<EOF | tee /etc/security/limits.conf || exit 1
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
    cat <<EOF | tee $DESTFILE || exit 1
export APPSCALE_HOME=${APPSCALE_HOME_RUNTIME}
for jpath in\
 /usr/lib/jvm/java-6-openjdk\
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
export EC2_HOME=/usr/local/ec2-api-tools
EOF
# enable to load AppServer and AppDB modules. It must be before the python-support.
    echo "export EC2_HOME=/usr/local/ec2-api-tools" >> ~/.bashrc
    for jpath in\
 /usr/lib/jvm/java-6-openjdk\
 /usr/lib/jvm/default-java
    do
      if [ -e $jpath ]; then
        echo "export JAVA_HOME=$jpath" >> ~/.bashrc
        break
      fi
    done
    DESTFILE=${DESTDIR}/usr/lib/python2.6/dist-packages/appscale_appserver.pth
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE || exit 1
${APPSCALE_HOME_RUNTIME}/AppDB
${APPSCALE_HOME_RUNTIME}/AppServer
EOF
# enable to load site-packages of Python
    DESTFILE=${DESTDIR}/usr/local/lib/python2.6/dist-packages/site_packages.pth
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE || exit 1
/usr/lib/python2.6/site-packages
EOF

    # for lucid
    if [ "$DIST" = "lucid" ]; then
	# enable memcached api
	SITE_DIR=${DESTDIR}/usr/local/lib/python2.5/site-packages
	mkdir -pv ${SITE_DIR}
	DESTFILE=${SITE_DIR}/pyshared.pth
	echo "Generating $DESTFILE"
	cat <<EOF | tee $DESTFILE || exit 1
/usr/share/pyshared
EOF
	# enable python imaging native library
	DESTFILE=${SITE_DIR}/PIL-lib.pth
	echo "Generating $DESTFILE"
	cat <<EOF | tee $DESTFILE || exit 1
/usr/lib/python2.6/dist-packages/PIL
EOF
       # Add fpconst into python2.5
       cp /usr/lib/pymodules/python2.6/fpconst.py /usr/lib/python2.5/ || exit 1
    fi

    # create link to appscale settings
    rm -rfv ${DESTDIR}/etc/appscale
    mkdir -pv ~/.appscale
    mkdir -pv ${APPSCALE_HOME_RUNTIME}/.appscale
    ln -sfv ${APPSCALE_HOME_RUNTIME}/.appscale ${DESTDIR}/etc/appscale

    cat <<EOF | tee /etc/appscale/home || exit
${APPSCALE_HOME_RUNTIME}
EOF
    mkdir -pv /var/log/appscale
    mkdir -pv /var/appscale/
}

installthrift_fromsource()
{
    export THRIFT_VER=0.5.0

    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    # facebook version 1.0.
#    wget http://appscale.cs.ucsb.edu/appscale_files/thrift.tgz -O ${APPSCALE_HOME}/downloads/thrift.tgz
    # apache 0.1.0
#    wget http://appscale.cs.ucsb.edu/appscale_files/thrift-hypertable.tar.gz -O ${APPSCALE_HOME}/downloads/thrift-hypertable.tar.gz
    # apache 0.2.0
    wget http://appscale.cs.ucsb.edu/appscale_files/thrift-${THRIFT_VER}.tar.gz || exit 1
    #wget http://www.apache.org/dist/incubator/thrift/${THRIFT_VER}-incubating/thrift-${THRIFT_VER}.tar.gz || exit 1
    tar zxfv thrift-${THRIFT_VER}.tar.gz || exit 1
    rm -v thrift-${THRIFT_VER}.tar.gz
    pushd thrift-${THRIFT_VER}
    CONFIG_SHELL=/bin/bash /bin/bash ./configure --without-csharp --without-haskell --without-ocaml --without-php --prefix=/usr/local 
    make || exit 1
# install native library and include files to DESTDIR.
    make install || exit 1
# python library
    pushd lib/py
    python setup.py install --prefix=${DESTDIR}/usr || exit 1
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
    easy_install -U thrift || exit 1
    DISTP=/usr/local/lib/python2.6/dist-packages
    if [ -z "$(find ${DISTP} -name Thrift-*.egg)" ]; then
	echo "Fail to install python thrift client. Please retry."
	exit 1
    fi
    if [ -n "$DESTDIR" ]; then
	mkdir -pv ${DESTDIR}${DISTP}
	cp -rv ${DISTP}/Thrift-*.egg ${DESTDIR}${DISTP} || exit 1
    fi
}

postinstallthrift()
{
    # just enable thrift library.
    easy_install thrift
}

installappserverjava()
{
    # compile source file.
    cd ${APPSCALE_HOME}/AppServer_Java
    ant install || exit 1
    ant clean-build || exit 1

    if [ -n "$DESTDIR" ]; then
        # delete unnecessary files.
	rm -rfv src lib
    fi
}

postinstallappserverjava()
{
    :;
}

installtornado_fromsource()
{
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    rm -rfv tornado
    # download from official site
    # wget http://www.tornadoweb.org/static/tornado-0.2.tar.gz
    # download from appscale site
    wget http://appscale.cs.ucsb.edu/appscale_files/tornado-0.2.tar.gz || exit 1
    tar xvzf tornado-0.2.tar.gz || exit 1
    pushd tornado-0.2
    python setup.py build || exit 1
    python setup.py install --prefix=${DESTDIR}/usr || exit 1
    popd
    rm -rfv tornado-0.2
    rm -rfv tornado-0.2.tar.gz
}

# using egg

installtornado()
{
    easy_install -U tornado || exit 1
    DISTP=/usr/local/lib/python2.6/dist-packages
    if [ -z "$(find ${DISTP} -name tornado-*.egg)" ]; then
	echo "Fail to install python tornado. Please retry."
	exit 1
    fi
    if [ -n "$DESTDIR" ]; then
	mkdir -pv ${DESTDIR}${DISTP}
	cp -rv ${DISTP}/tornado-*.egg ${DESTDIR}${DISTP} || exit 1
    fi
}

installnose()
{
  easy_install nose || exit 1
}

installflexmock()
{
    easy_install flexmock || exit 1
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
# download from official site
#    wget http://haproxy.1wt.eu/download/1.4/src/haproxy-${HAPROXY_VER}.tar.gz || exit 1
# download from appscale site
    wget http://appscale.cs.ucsb.edu/appscale_packages/pool/haproxy-${HAPROXY_VER}.tar.gz || exit 1
    tar zxvf haproxy-${HAPROXY_VER}.tar.gz || exit 1
    rm -v haproxy-${HAPROXY_VER}.tar.gz

    pushd haproxy-${HAPROXY_VER}
    # All Ubuntu is linux26 now
    make TARGET=linux26 || exit 1
    make install-bin PREFIX=/usr || exit 1
    if [ ! -e ${DESTDIR}/usr/sbin/haproxy ]; then
	echo "Fail to install haproxy. Please retry."
	exit 1
    fi
    popd
    rm -rv haproxy-${HAPROXY_VER} || exit 1

    # install service script
    mkdir -pv ${DESTDIR}/etc/init.d
    cp -v ${APPSCALE_HOME}/AppLoadBalancer/config/haproxy-init.sh ${DESTDIR}/etc/init.d/haproxy || exit 1
    chmod -v a+x ${DESTDIR}/etc/init.d/haproxy || exit 1
    mkdir -pv ${DESTDIR}/etc/haproxy
    cp -v ${APPSCALE_HOME}/AppLoadBalancer/config/haproxy.cfg ${DESTDIR}/etc/haproxy/ || exit 1
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
    wget http://appscale.cs.ucsb.edu/appscale_files/tmux-1.6.tar.gz
    tar zxvf tmux-1.6.tar.gz
    cd tmux-1.6
    ./configure
    make
    make install
    cd ${APPSCALE_HOME}
    rm -rf tmux-1.6 tmux-1.6.tar.gz
    
    # Finally, grab our tmux config file and put it in the right place
    cd
    wget http://appscale.cs.ucsb.edu/appscale_files/tmux.conf -O .tmux.conf
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
    #wget http://www.hypertable.com/download/packages/${HT_VER}/hypertable-${HT_VER}-linux-${ARCH}.deb -O hypertable-${HT_VER}.deb || exit 1
    #wget http://cdn.hypertable.com/packages/${HT_VER}/hypertable-${HT_VER}-linux-${ARCH}.deb -O hypertable-${HT_VER}.deb || exit 1
    wget http://appscale.cs.ucsb.edu/appscale_files/hypertable-${HT_VER}-linux-${ARCH}.deb -O hypertable-${HT_VER}.deb || exit 1
    dpkg-deb --vextract hypertable-${HT_VER}.deb ${DESTDIR}/ || exit 1
    rm hypertable-${HT_VER}.deb

    # enable to load hypertable client of python
    DESTFILE=${DESTDIR}/usr/local/lib/python2.6/dist-packages/hypertable_client.pth
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE || exit 1
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
    gem install sinatra rack thin json ${GEMOPT} || exit 1
    cd ${APPSCALE_HOME}/downloads
    wget http://appscale.cs.ucsb.edu/appscale_files/rrdtool-1.4.4.tar.gz || exit 1
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
    wget http://appscale.cs.ucsb.edu/appscale_files/rubygems-1.3.7.tgz || exit 1
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
    gem install neptune right_aws ${GEMOPT} || exit 1
    sleep 1
    gem install god redgreen Ruby-MemCache ${GEMOPT} || exit 1
    sleep 1
    #if [ ! -e ${DESTDIR}/usr/bin/god ]; then
    #	echo "Fail to install god. Please Retry."
    #	exit 1
    #fi
    gem install -v=2.3.4 rails ${GEMOPT} || exit 1
    sleep 1
    gem install gem_plugin mongrel ${GEMOPT} || exit 1
    sleep 1
    gem install mongrel_cluster ${GEMOPT} || exit 1
    #sleep 1
    #if [ ! -e ${DESTDIR}/usr/bin/mongrel_rails ]; then
    #	echo "Fail to install mongrel rails. Please Retry."
    #	exit 1
    #fi
    # This is for the Hypertable.
    gem install capistrano ${GEMOPT} || exit 1
    sleep 1
    gem install json ${GEMOPT} || exit 1
    sleep 1
    #if [ ! -e ${DESTDIR}/usr/bin/cap ]; then
    #	echo "Fail to install capistrano. Please Retry."
    #	exit 1
    #fi

    # This is for Neptune's Babel App Engine pull queue interface
    # which is just REST, but httparty does such a nice job compared
    # to previously used things
    gem install -v=0.8.3 httparty ${GEMOPT} || exit 1

    # This is for the unit testing framework
    gem install -v=1.0.4 flexmock ${GEMOPT} || exit 1
    gem install -v=1.0.0 rcov ${GEMOPT} || exit 1

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
    RAILS_ENV=production rake gems:build:force || exit 1
    RAILS_ENV=production rake db:migrate || exit 1
}

postinstallmonitoring()
{
    :;
}

installnginx_fromsource()
{
#    apt-get install -y libpcre3 libpcre3-dev
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    wget http://appscale.cs.ucsb.edu/appscale_files/nginx-0.6.39.tar.gz || exit 1
    tar zxvf nginx-0.6.39.tar.gz || exit 1
    rm -v nginx-0.6.39.tar.gz
    pushd nginx-0.6.39
    ./configure --with-http_ssl_module || exit 1
    make || exit 1
    make install || exit 1
    popd
    rm -rv nginx-0.6.39
}

installnginx()
{
    # we could install using deb package.
    :;
}

# This function is called from postinst.core, so we don't need to use DESTDIR

postinstallnginx()
{
    service nginx stop || true
    update-rc.d -f nginx remove || true

    cd ${APPSCALE_HOME}
    cp -v AppLoadBalancer/config/load-balancer.conf /etc/nginx/sites-enabled/
    rm -fv /etc/nginx/sites-enabled/default
}

installhadoop()
{
    HADOOP_VER=0.20.2-cdh3u3
  
    mkdir -pv ${APPSCALE_HOME}/AppDB
    cd ${APPSCALE_HOME}/AppDB
    rm -rfv hadoop-${HADOOP_VER}
    wget http://appscale.cs.ucsb.edu/appscale_files/hadoop-${HADOOP_VER}.tar.gz -O hadoop-${HADOOP_VER}.tar.gz || exit 1
    tar xvzf hadoop-${HADOOP_VER}.tar.gz || exit 1
    rm -v hadoop-${HADOOP_VER}.tar.gz
    cd hadoop-${HADOOP_VER}
    DESTFILE=./conf/hadoop-env.sh
    echo "Appending $DESTFILE"
    cat <<EOF | tee -a $DESTFILE || exit 1
. /etc/profile.d/appscale.sh
export HADOOP_HOME=\${APPSCALE_HOME}/AppDB/hadoop-${HADOOP_VER}
export HADOOP_HEAPSIZE=2000
export HADOOP_NAMENODE_USER=root
EOF

    # This patch fixes WrongFS issue
    patch -p0 -i ../hadoop/patch/hadoop-hbase.patch || exit 1

    # build new jar
    ant clean || exit 1
    ant jar || exit 1
    # Use the new jar 
    cp -v build/hadoop-core-${HADOOP_VER}.jar ./hadoop-core-${HADOOP_VER}.jar || exit 1
    rm -rfv build

    # Replace the main script with one that allows hadoop to be run as root
    cp ../hadoop/templates/hadoop ./bin/ || exit 1

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
    wget http://appscale.cs.ucsb.edu/appscale_files/hbase-${HBASE_VER}-rebuilt.tar.gz -O hbase-${HBASE_VER}.tar.gz || exit 1

    tar zxvf hbase-${HBASE_VER}.tar.gz || exit 1
    rm -v hbase-${HBASE_VER}.tar.gz
    # Clean out the maven repository
    rm -rfd ~/.m2/
    cd
    wget http://appscale.cs.ucsb.edu/appscale_files/maven_repos.tar.gz || exit 1
    tar zxvf maven_repos.tar.gz  || exit 1
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
    CASSANDRA_VER=1.0.7
    PYCASSA_VER=1.3.0
    cd /lib 
    wget http://appscale.cs.ucsb.edu/appscale_files/jamm-0.2.2.jar || exit 1
    
    mkdir -p ${APPSCALE_HOME}/AppDB/cassandra
    cd ${APPSCALE_HOME}/AppDB/cassandra
    rm -rfv cassandra
    wget http://appscale.cs.ucsb.edu/appscale_files/apache-cassandra-${CASSANDRA_VER}-bin.tar.gz || exit 1
    tar xzvf apache-cassandra-${CASSANDRA_VER}-bin.tar.gz || exit 1
    mv -v apache-cassandra-${CASSANDRA_VER} cassandra
    rm -fv apache-cassandra-${CASSANDRA_VER}-bin.tar.gz
    cd cassandra
    chmod -v +x bin/cassandra
    cp -v ${APPSCALE_HOME}/AppDB/cassandra/templates/cassandra.in.sh ${APPSCALE_HOME}/AppDB/cassandra/cassandra/bin || exit 1
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
    wget http://appscale.cs.ucsb.edu/appscale_files/pycassa-${PYCASSA_VER}.tar.gz || exit 1
    tar zxvf pycassa-${PYCASSA_VER}.tar.gz  
    cd pycassa-${PYCASSA_VER}
    python setup.py install || exit 1
    cd ..
    rm -fdr pycassa-${PYCASSA_VER}
    rm -fdr pycassa-${PYCASSA_VER}.tar.gz 
}

postinstallcassandra()
{
    mkdir -p ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}
    touch ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}/cassandra
}

installvoldemort()
{
    VOLDEMORT_VER=0.80

    mkdir -p ${APPSCALE_HOME}/AppDB/voldemort

    cd ${APPSCALE_HOME}/AppDB/voldemort
    rm -rfv voldemort
    wget http://appscale.cs.ucsb.edu/appscale_files/voldemort-${VOLDEMORT_VER}.tar.gz || exit 1
    tar xzvf voldemort-${VOLDEMORT_VER}.tar.gz || exit 1
    mv -v voldemort-${VOLDEMORT_VER} voldemort
    rm -v voldemort-${VOLDEMORT_VER}.tar.gz
    cd voldemort
    ant clean || exit 1
    ant jar || exit 1
    chmod -v +x bin/voldemort-server.sh
    if [ -n "${DESTDIR}" ]; then
	# remove unnecessary files.
	rm -rfv contrib docs example src test dist/classes dist/resources
    fi

    mkdir -p ${DESTDIR}/var/voldemort
    mkdir -p ${APPSCALE_HOME}/AppDB/voldemort/voldemort/config/appscale/config
}

postinstallvoldemort()
{
    mkdir -p ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}
    touch ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}/voldemort
}

installredisdb()
{
   REDIS_VER=2.2.11
   mkdir -p /var/appscale/
   cd /var/appscale/
   rm -rfv redisdb
   wget http://appscale.cs.ucsb.edu/appscale_files/redis-${REDIS_VER}.tar.gz || exit 1
   tar xzvf redis-${REDIS_VER}.tar.gz || exit 1
   mv -v redis-${REDIS_VER} redisdb
   rm -v redis-${REDIS_VER}.tar.gz
   
   cd redisdb
   make || exit 1 
   easy_install redis || exit 1
}

postinstallredisdb()
{
   mkdir -p ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}
   touch ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}/redisdb
} 

  
installprotobuf_fromsource()
{
    PROTOBUF_VER=2.3.0
    # install protobuf 2.3.0. we need egg version for python.
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    wget http://appscale.cs.ucsb.edu/appscale_files/protobuf-${PROTOBUF_VER}.tar.gz || exit 1
    tar zxvf protobuf-${PROTOBUF_VER}.tar.gz || exit 1
    rm -v protobuf-${PROTOBUF_VER}.tar.gz
    pushd protobuf-${PROTOBUF_VER}
    ./configure --prefix=/usr || exit 1
    make || exit 1
    make check || exit 1
    make install || exit 1
    pushd python
# protobuf could not be installed in the different root
#    python setup.py install --prefix=${DESTDIR}/usr
    python setup.py bdist_egg || exit 1
# copy the egg file
    DISTP=${DESTDIR}/usr/local/lib/python2.6/dist-packages
    mkdir -pv ${DISTP}
    cp -v dist/protobuf-*.egg ${DISTP} || exit 1
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

installmysql()
{
    :;
}

postinstallmysql()
{
    # stop previous service
    service mysql stop || true
    service mysql-ndb stop || true
    service mysql-ndb-mgm stop || true

    # uninstall mysql services
    update-rc.d -f mysql remove || true
    update-rc.d -f mysql-ndb remove || true
    update-rc.d -f mysql-ndb-mgm remove || true
#    mkdir -p /var/lib/mysql-cluster/backup
    mysqladmin shutdown

    mkdir -p ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}
    touch ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}/mysql
}

installmongodb()
{
    # we can install mongodb from deb package now.
    # previous version is no longer located in the official repository.
    # should we store it our own server?
    MONGO_VER=20100326

    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    ARCH=`uname -m`
    if [ "$ARCH" = "x86_64" ]; then
	ARCH="amd64"
    fi
    if [ "$ARCH" = "i686" ]; then
	ARCH="i386"
    fi

    # only for jaunty and karmic. we don't need this from lucid.
    # download from official site
#    if [ "$DIST" = "jaunty" ]; then
#	wget http://downloads.mongodb.org/distros/ubuntu/dists/9.4/10gen/binary-${ARCH}/mongodb-stable_${MONGO_VER}_${ARCH}.deb -O mongodb-stable.deb || exit 1
#    elif [ "$DIST" = "karmic" ]; then
#	wget http://downloads.mongodb.org/distros/ubuntu/dists/9.10/10gen/binary-${ARCH}/mongodb-stable_${MONGO_VER}_${ARCH}.deb -O mongodb-stable.deb || exit 1
#    fi
    # download from appscale server
    if [ "$DIST" = "jaunty" -o "$DIST" = "karmic" ]; then
	wget http://appscale.cs.ucsb.edu/appscale_packages/pool/mongodb-stable_${MONGO_VER}_${DIST}_${ARCH}.deb -O mongodb-stable.deb || exit 1
    fi

    if [ -e mongodb-stable.deb ]; then
        # extract deb package and repackage it.
	dpkg-deb --vextract mongodb-stable.deb ${DESTDIR}/ || exit 1
	rm -v mongodb-stable.deb
    fi

#    mkdir -p ${APPSCALE_HOME}/AppDB/mongodb
#    cd ${APPSCALE_HOME}/AppDB/mongodb
#    rm -rf mongodb
#    wget http://appscale.cs.ucsb.edu/appscale_files/mongodb-linux-x86_64-1.2.2.tgz
#    if [ $? -ne 0 ]; then echo "FAILURE: UNABLE TO DOWNLOAD." ; exit 1; fi
#    tar zxvf mongodb-linux-x86_64-1.2.2.tgz
#    rm mongodb-linux-x86_64-1.2.2.tgz
#    mv mongodb-linux-x86_64-1.2.2 mongodb
#    chmod +x mongodb/bin/mongo mongodb/bin/mongod
# easy_install could not specify prefix, so we must install it in postinst
    # pymongo
#    mkdir -p ${DESTDIR}/usr/lib/python2.6/site-packages

    easy_install -U pymongo || exit 1
    if [ -n "$DESTDIR" ]; then
	DISTP=/usr/local/lib/python2.6/dist-packages
	mkdir -pv ${DESTDIR}${DISTP}
	cp -rv ${DISTP}/pymongo-*.egg ${DESTDIR}${DISTP} || exit 1
    fi
}

postinstallmongodb()
{
    # just enable pymongo egg
    #easy_install pymongo


    # from mongodb deb package
    # create a mongodb group and user
    if ! grep -q mongodb /etc/passwd; then
	adduser --system --no-create-home mongodb
	addgroup --system mongodb
	adduser mongodb mongodb
    fi

    # create db -- note: this should agree with dbpath in mongodb.conf
    mkdir -pv /var/lib/mongodb
    chown -v -R mongodb:mongodb /var/lib/mongodb

    # create logdir -- note: this should agree with logpath in mongodb.conf
    mkdir -pv /var/log/mongodb
    chown -v -R mongodb:mongodb /var/log/mongodb

    # we need remove from lucid
    update-rc.d -f mongodb remove || true
    killall mongod
    mkdir -p ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}
    touch ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}/mongodb

    update-rc.d -f mongodb remove
}

installmemcachedb()
{
    # we can install memcachedb from package.
    :;
}

postinstallmemcachedb()
{
    # stop memcachedb
    service memcachedb stop || true
    # remove service
    update-rc.d -f memcachedb remove || true
    killall memcachedb
    mkdir -p ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}
    touch ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}/memcachedb
}

# only for dependencies
installtimesten()
{
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    wget http://pyodbc.googlecode.com/files/pyodbc-2.1.6.zip || exit 1
    unzip pyodbc-2.1.6.zip || exit 1
    rm -v pyodbc-2.1.6.zip
    pushd pyodbc-2.1.6
    python setup.py install --prefix=${DESTDIR}/usr || exit 1
    popd
    rm -rfv pyodbc-2.1.6
    DESTFILE=${DESTDIR}/etc/profile.d/timesten.sh
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE || exit 1
. /etc/profile.d/appscale.sh
if [ -e /opt/TimesTen/tt70/bin/ttenv.sh ]; then
  . /opt/TimesTen/tt70/bin/ttenv.sh
fi
export ODBCINI=\$APPSCALE_HOME/AppDB/timesten/.odbc.ini
EOF
}

postinstalltimesten()
{
    if [ -e /etc/init.d/tt_tt70 ]; then
        # ignore error
	service tt_tt70 stop || true
	update-rc.d -f tt_tt70 remove || true
    fi
}

installpig()
{
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    wget http://apache.deathculture.net/hadoop/pig/pig-0.5.0/pig-0.5.0.tar.gz || exit 1
    tar zxvf pig-0.5.0.tar.gz || exit 1
    rm -v pig-0.5.0.tar.gz
    cd pig-0.5.0
    mkdir tmp
    cp -v pig-0.5.0-core.jar tmp/
    cd tmp
    jar xvf pig-0.5.0-core.jar || exit 1
    rm -rfv pig-0.5.0-core.jar
    /bin/cp -fv ~/appscale/AppDB/hadoop-0.20.2/build/classes/org/apache/hadoop/hdfs/* ${APPSCALE_HOME}/downloads/pig-0.5.0/tmp/org/apache/hadoop/hdfs/
    jar cvf ../pig-0.5.0-core.jar ./*
    rm -rfv ./*
    wget http://appscale.cs.ucsb.edu/appscale_files/pigtutorial.tar.gz || exit 1
    tar zxvf pigtutorial.tar.gz || exit 1
    DESTFILE=${DESTDIR}/etc/profile.d/pig.sh
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE || exit 1
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
    ln -sfv ${APPSCALE_HOME_RUNTIME}/appscale-loadbalancer.sh ${DESTDIR}/etc/init.d/appscale-loadbalancer
    chmod -v a+x ${APPSCALE_HOME}/appscale-loadbalancer.sh
    ln -sfv ${APPSCALE_HOME_RUNTIME}/appscale-controller.sh ${DESTDIR}/etc/init.d/appscale-controller
    chmod -v a+x ${APPSCALE_HOME}/appscale-controller.sh
    ln -sfv ${APPSCALE_HOME_RUNTIME}/appscale-monitoring.sh ${DESTDIR}/etc/init.d/appscale-monitoring
    chmod -v a+x ${APPSCALE_HOME}/appscale-monitoring.sh
}

postinstallservice()
{
# we don't need to start load balancer as daemon
#    update-rc.d appscale-loadbalancer defaults

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

    ejabberdctl stop
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

    wget http://appscale.cs.ucsb.edu/appscale_files/zookeeper-${ZK_VER}.tar.gz || exit 1
    tar zxvf zookeeper-${ZK_VER}.tar.gz

    cd zookeeper-${ZK_VER}
    # build java library
    ant || exit 1
    ant compile_jute || exit 1
    #if [ ! -e build/zookeeper-${ZK_VER}.jar ]; then
    #   echo "Fail to make zookeeper java jar. Please retry."
    #   exit 1
    #fi

    # build c library
    #pushd src/c
    cd src/c
#    sed -i 's/AM_PATH_CPPUNIT/:;#AM_PATH_CPPUNIT/g' configure.ac || exit 1
    autoreconf -if || exit 1
    ./configure --prefix=/usr || exit 1
    make || exit 1
    make install || exit 1
    if [ ! -e ${DESTDIR}/usr/lib/libzookeeper_mt.a ]; then
        echo "Fail to install libzookeeper. Please retry."
        exit 1
    fi
    cd ../..

    # apply memory leak patch of zkpython TODO check if 3.3.4-cdh3u3 needs it
    #patch -p0 -i ${APPSCALE_HOME}/AppDB/zkappscale/patch/zkpython-memory.patch || exit 1

    # python library
    cd src/contrib/zkpython
    ant install || exit 1
    if [ ! -e /usr/local/lib/python2.6/dist-packages/zookeeper.so ]; then
        echo "Fail to install libzookeeper. Please retry."
        exit 1
    fi
    if [ -n "${DESTDIR}" ]; then
        mkdir -pv ${DESTDIR}/usr/local/lib/python2.6/dist-packages
        cp -v /usr/local/lib/python2.6/dist-packages/zookeeper.so ${DESTDIR}/usr/local/lib/python2.6/dist-packages/ || exit 1
        cp -v /usr/local/lib/python2.6/dist-packages/ZooKeeper-* ${DESTDIR}/usr/local/lib/python2.6/dist-packages/ || exit 1
    fi
    cd ../../..

    # install java library
    mkdir -pv ${DESTDIR}/usr/share/java
    cp -v build/zookeeper-${ZK_VER2}.jar ${DESTDIR}/usr/share/java || exit 1
    ln -sfv zookeeper-${ZK_VER2}.jar ${DESTDIR}/usr/share/java/zookeeper.jar || exit 1

    # install config files and service.
    BASEURL=http://appscale.cs.ucsb.edu/appscale_packages/pool/zookeeper
    wget ${BASEURL}/zookeeper_3.2.2+dfsg3-3_all.deb -O zookeeper.deb || exit 1
    dpkg-deb --vextract zookeeper.deb ${DESTDIR}/ || exit 1
    rm -v zookeeper.deb
    wget ${BASEURL}/zookeeperd_3.2.2+dfsg3-3_all.deb -O zookeeperd.deb || exit 1
    dpkg-deb --vextract zookeeperd.deb ${DESTDIR}/ || exit 1
    rm -v zookeeperd.deb

    cd ${APPSCALE_HOME}/downloads
    rm -rv zookeeper-${ZK_VER} || exit 1
    rm -fdr zookeeper-${ZK_VER}.tar.gz || exit 1

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
    BASEURL=http://appscale.cs.ucsb.edu/appscale_packages/pool/zookeeper
    wget ${BASEURL}/liblog4j1.2-java_1.2.15-11_all.deb -O liblog4j.deb || exit 1
    dpkg-deb --vextract liblog4j.deb ${DESTDIR}/ || exit 1
    rm -v liblog4j.deb
    wget ${BASEURL}/libzookeeper-java_3.2.2+dfsg3-3_all.deb -O libzookeeper-java.deb || exit 1
    dpkg-deb --vextract libzookeeper-java.deb ${DESTDIR}/ || exit 1
    rm -v libzookeeper-java.deb
    wget ${BASEURL}/libzookeeper2_3.2.2+dfsg3-3_${ARCH}.deb -O libzookeeper2.deb || exit 1
    dpkg-deb --vextract libzookeeper2.deb ${DESTDIR}/ || exit 1
    rm -v libzookeeper2.deb
    wget ${BASEURL}/python-zookeeper_3.2.2+dfsg3-3_${ARCH}.deb -O python-zookeeper.deb || exit 1
    dpkg-deb --vextract python-zookeeper.deb ${DESTDIR}/ || exit 1
    rm -v python-zookeeper.deb

    wget ${BASEURL}/zookeeper-bin_3.2.2+dfsg3-3_${ARCH}.deb -O zookeeper-bin.deb || exit 1
    dpkg-deb --vextract zookeeper-bin.deb ${DESTDIR}/ || exit 1
    rm -v zookeeper-bin.deb
    wget ${BASEURL}/zookeeper_3.2.2+dfsg3-3_all.deb -O zookeeper.deb || exit 1
    dpkg-deb --vextract zookeeper.deb ${DESTDIR}/ || exit 1
    rm -v zookeeper.deb
    wget ${BASEURL}/zookeeperd_3.2.2+dfsg3-3_all.deb -O zookeeperd.deb || exit 1
    dpkg-deb --vextract zookeeperd.deb ${DESTDIR}/ || exit 1
    rm -v zookeeperd.deb

    mkdir -pv ${DESTDIR}/var/run/zookeeper
    mkdir -pv ${DESTDIR}/var/lib/zookeeper
    mkdir -pv ${DESTDIR}/etc/zookeeper/conf
# enable to load python-zookeeper
    DESTFILE=${DESTDIR}/usr/local/lib/python2.6/dist-packages/pyshared2.6.pth
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE || exit 1
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
    wget http://appscale.cs.ucsb.edu/appscale_files/setuptools-0.6c11.tar.gz || exit 1
    tar zxvf setuptools-0.6c11.tar.gz
    pushd setuptools-0.6c11
    python setup.py install  || exit 1
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

postinstallsimpledb()
{
    mkdir -p ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}
    touch ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}/simpledb
}

installrabbitmq()
{
   # RabbitMQ is installed via apt-get
   # Install the python client for rabbitmq
   mkdir -pv ${APPSCALE_HOME}/downloads
   cd ${APPSCALE_HOME}/downloads
   wget http://appscale.cs.ucsb.edu/appscale_files/pika-0.9.5.tar.gz || exit 1
   tar zxvf pika-0.9.5.tar.gz
   cd pika-0.9.5
   python2.5 setup.py install
   cd ..
   rm -fr pika-0.9.5*
}
postinstallrabbitmq()
{
    # After install it starts up, shut it down
    rabbitmqctl stop
    update-rc.d -f rabbitmq remove || true
    update-rc.d -f rabbitmq-server remove || true
}
