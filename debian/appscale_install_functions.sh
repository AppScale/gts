#/bin/sh
# Common functions for build and installer
#
# This should work in bourne shell (/bin/sh)
# The function name should not include non alphabet charactor.
#
# Written by Yoshi <nomura@pobox.com>

if [ -z "$APPSCALE_HOME_RUNTIME" ]; then
    export APPSCALE_HOME_RUNTIME=/opt/appscale
fi

export APPSCALE_VERSION=1.5

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

updatealternatives()
{
# we don't need to set for sh
#update-alternatives --install /bin/sh sh /bin/dash 1
#update-alternatives --install /bin/sh sh /bin/bash 1
#update-alternatives --set sh /bin/bash
    if [ -e /usr/lib/jvm/java-6-sun ]; then
	update-java-alternatives --set java-6-sun || true
    fi
}

installappscaleprofile()
{
#    mkdir -p ${APPSCALE_HOME}
#    cat > ${APPSCALE_HOME}/appscale.env <<EOF
#export APPSCALE_HOME=${APPSCALE_HOME_RUNTIME}
#export HOME=\$APPSCALE_HOME
#export JAVA_HOME=/usr/lib/jvm/java-6-sun
#EOF
    DESTFILE=${DESTDIR}/etc/profile.d/appscale.sh
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE || exit 1
export APPSCALE_HOME=${APPSCALE_HOME_RUNTIME}
for jpath in\
 /usr/lib/jvm/java-6-sun\
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
EOF
# enable to load AppServer and AppDB modules. It must be before the python-support.
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
    fi

    # create link to appscale settings
    rm -rfv ${DESTDIR}/etc/appscale
    ln -sfv ${APPSCALE_HOME_RUNTIME}/.appscale ${DESTDIR}/etc/appscale
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
    wget http://www.apache.org/dist/incubator/thrift/${THRIFT_VER}-incubating/thrift-${THRIFT_VER}.tar.gz || exit 1
    tar zxfv thrift-${THRIFT_VER}.tar.gz || exit 1
    rm -v thrift-${THRIFT_VER}.tar.gz
    pushd thrift-${THRIFT_VER}
    CONFIG_SHELL=/bin/bash /bin/bash ./configure --without-csharp --without-php --prefix=/usr/local 
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

# scratch install version

installhypertable_old()
{
# 1.6.0 for hypertable 0.9.2.5, 1.6.3 for 0.9.2.7
    export SIGAR_VER=1.6.3
# 0.9.2.5, 0.9.2.7 requires *apache* thrift >=0.1
    export HT_VER=0.9.2.7

    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    rm -v hyperic-sigar-${SIGAR_VER}*
#    wget http://appscale.cs.ucsb.edu/appscale_files/hyperic-sigar-1.6.0.tar.gz
    wget http://internap.dl.sourceforge.net/sourceforge/sigar/hyperic-sigar-${SIGAR_VER}.tar.gz || exit 1

    tar -xzvf hyperic-sigar-${SIGAR_VER}.tar.gz || exit 1
    rm -v hyperic-sigar-${SIGAR_VER}.tar.gz
    cd hyperic-sigar-${SIGAR_VER}
    mkdir -pv ${DESTDIR}/usr/local/include
    cp -v sigar-bin/include/*.h ${DESTDIR}/usr/local/include
# 64 BIT
    mkdir -pv ${DESTDIR}/usr/local/lib
    cp -v sigar-bin/lib/libsigar-amd64-linux.so sigar-bin/lib/libsigar-ia64-linux.so ${DESTDIR}/usr/local/lib/
# 32 BIT (use the above line)
#    cp sigar-bin/lib/libsigar-x86-linux.so ${DESTDIR}/usr/local/lib/
#ldconfig

    cd ${APPSCALE_HOME}/AppDB/hypertable
    rm -rfv src build ${HT_VER} hypertable-${HT_VER}*
    mkdir -pv src
    cd ${APPSCALE_HOME}/AppDB/hypertable/src
    wget http://hypertable.org/download.php?v=${HT_VER}-alpha || exit 1
#wget http://appscale.cs.ucsb.edu/appscale_files/hypertable-${HT_VERSION}-alpha-src.tar.gz -O ${APPSCALE_HOME}/AppDB/hypertable/src/hypertable-0.9.2.5-alpha-src.tar.gz
    tar xvzf hypertable-${HT_VER}-alpha-src.tar.gz || exit 1
    rm -v hypertable-${HT_VER}-alpha-src.tar.gz

# replace lib path for debian
    sed -i -e "s/\/usr\/local\/lib/\/usr\/lib/g" hypertable-${HT_VER}-alpha/cmake/FindLibEvent.cmake
    sed -i -e "s/\/usr\/local\/include/\/usr\/include/g" hypertable-${HT_VER}-alpha/cmake/FindLibEvent.cmake

    export HYPERTABLE=${APPSCALE_HOME}/AppDB/hypertable
    export HADOOP=${APPSCALE_HOME}/AppDB/hadoop-0.20.0
    mkdir -pv ${APPSCALE_HOME}/AppDB/hypertable/src/build
    cd ${APPSCALE_HOME}/AppDB/hypertable/src/build
    cmake -DHADOOP_INCLUDE_PATH=${HADOOP}/src/c++/install/include/\
      -DHADOOP_LIB_PATH=${HADOOP}/src/c++/install/lib/\
      -DBUILD_SHARED_LIBS=ON\
      -DCMAKE_INSTALL_PREFIX=${HYPERTABLE}\
      -DJAVA_INCLUDE_PATH=/usr/lib/jvm/java-6-sun/include/\
      -DJAVA_INCLUDE_PATH2=/usr/lib/jvm/java-6-sun/include/linux/\
      ../hypertable-${HT_VER}-alpha

# this works for 0.9.2.5 and 0.9.2.7
    cp ../../hypertablefix/TableRangeMap.cc\
    ../hypertable-${HT_VER}-alpha/contrib/cc/MapReduce/
    cp ../../hypertablefix/TableReader.cc\
    ../hypertable-${HT_VER}-alpha/contrib/cc/MapReduce/

    make || exit 1
    make install || exit 1

# we must copy the python library in 0.9.2.5 alpha
#    mkdir -p ${HYPERTABLE}/${HT_VER}/lib/py
#    cp ../hypertable-${HT_VER}-alpha/src/py/ThriftClient/*.py\
#      ${HYPERTABLE}/${HT_VER}/lib/py/
#    cp ../hypertable-${HT_VER}-alpha/src/py/ThriftClient/gen-py\
#      ${HYPERTABLE}/${HT_VER}/lib/py/

    rm -rv ${APPSCALE_HOME}/AppDB/hypertable/src

    DESTFILE=${DESTDIR}/etc/ld.so.conf.d/hypertable.conf
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    echo "${APPSCALE_HOME_RUNTIME}/AppDB/hypertable/${HT_VER}/lib" | tee $DESTFILE || exit 1
#ldconfig

# enable to load hypertable client of python
    DESTFILE=${DESTDIR}/usr/local/lib/python2.6/dist-packages/hypertable_client.pth
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE || exit 1
${APPSCALE_HOME_RUNTIME}/AppDB/hypertable/${HT_VER}/lib/py
${APPSCALE_HOME_RUNTIME}/AppDB/hypertable/${HT_VER}/lib/py/gen-py
EOF
}

# deb package version

installhypertable()
{
    HT_VER=0.9.4.3
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    ARCH=`uname -m`
    if [ "$ARCH" = "i686" ]; then
	ARCH="i386"
    fi
    # extract binary files and repackage it when making deb
    wget http://www.hypertable.com/download/packages/${HT_VER}/hypertable-${HT_VER}-linux-${ARCH}.deb -O hypertable-${HT_VER}.deb || exit 1
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
    ln -s /usr/bin/thin1.8 /usr/bin/thin
    ln -s /opt/hypertable/${HT_VER}  /opt/hypertable/current
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
    gem install sinatra rack thin json titleize ${GEMOPT} || exit 1
    cd ${APPSCALE_HOME}/downloads
    wget http://kings.cs.ucsb.edu/appscale_files/rrdtool-1.4.4.tar.gz || exit 1
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
#    gem update
    GEMDEST=${DESTDIR}/var/lib/gems/1.8
    GEMOPT="--no-rdoc --no-ri --bindir ${DESTDIR}/usr/bin --install-dir ${GEMDEST}"
    gem install rake zookeeper neptune right_aws ${GEMOPT} || exit 1
    if [ ! -e ${DESTDIR}/usr/bin/rake ]; then
	echo "Fail to install rake. Please Retry."
	exit 1
    fi
    gem install god redgreen Ruby-MemCache ${GEMOPT} || exit 1
    if [ ! -e ${DESTDIR}/usr/bin/god ]; then
	echo "Fail to install god. Please Retry."
	exit 1
    fi
    if [ -z "${DESTDIR}" ]; then
	# avoid gems reinstall problem
	RAILS_EXISTS=`gem list -l | grep rails | wc -l`
	if [ $RAILS_EXISTS -eq 0 ]; then
	    gem install -v=2.3.4 rails ${GEMOPT} || exit 1
	fi
    else
	gem install -v=2.3.4 rails ${GEMOPT} || exit 1
    fi
    gem install mongrel mongrel_cluster ${GEMOPT} || exit 1
    if [ ! -e ${DESTDIR}/usr/bin/mongrel_rails ]; then
	echo "Fail to install mongrel rails. Please Retry."
	exit 1
    fi
    # This is for the Hypertable.
    gem install capistrano ${GEMOPT} || exit 1
    if [ ! -e ${DESTDIR}/usr/bin/cap ]; then
	echo "Fail to install capistrano. Please Retry."
	exit 1
    fi
}

postinstallgems()
{
    ln -s /var/lib/gems/1.8/bin/neptune /usr/bin/neptune
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
    wget http://kings.cs.ucsb.edu/appscale_files/nginx-0.6.39.tar.gz || exit 1
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
    HADOOP_VER=0.20.2

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
EOF
    # This patch fails for 0.20.2
    #patch -p0 -i ../hadoop/patch/hadoop-includes-2.patch || exit 1
    # patch for karmic compiler
    #patch -p0 -i ../hadoop/patch/hadoop-karmic.patch || exit 1
    # patch for hbase
    patch -p0 -i ../hadoop/patch/hadoop-hbase.patch || exit 1

    # build new jar
    ant clean || exit 1
    ant jar || exit 1
    cp -v build/hadoop-0.20.3-dev-core.jar ./hadoop-${HADOOP_VER}-core.jar || exit 1
    rm -rfv build

    BUILD_CLIB=0
    if [ $BUILD_CLIB -ne 0 ]; then
        # build c++ library
	pushd src/c++/utils
	sh configure --prefix=${APPSCALE_HOME_RUNTIME}/AppDB/hadoop-${HADOOP_VER}/c++/install || exit 1

	make
	sed -i "s/CXXFLAGS = -g/CXXFLAGS = -fPIC -g/g" ./Makefile
	make clean
	make || exit 1
	make install || exit 1
	if [ ! -e ${APPSCALE_HOME}/AppDB/hadoop-${HADOOP_VER}/c++/install/lib/libhadooputils.a ]; then
	    echo "Fail to install Hadoop Util. Please retry."
	    exit 1
	fi
	popd

	pushd src/c++/pipes
	sh configure --prefix=${APPSCALE_HOME_RUNTIME}/AppDB/hadoop-${HADOOP_VER}/c++/install || exit 1
	make || exit 1
	make install || exit 1
	if [ ! -e ${APPSCALE_HOME}/AppDB/hadoop-${HADOOP_VER}/c++/install/lib/libhadooppipes.a ]; then
	    echo "Fail to install Hadoop Pipes. Please retry."
	    exit 1
	fi
	popd

	DESTFILE=${DESTDIR}/etc/ld.so.conf.d/hadoop.conf
	mkdir -pv $(dirname $DESTFILE)
	echo "Generating $DESTFILE"
	cat <<EOF | tee $DESTFILE || exit 1
${APPSCALE_HOME_RUNTIME}/AppDB/hadoop-${HADOOP_VER}/c++/install/lib
EOF
    else
	# just use precompiled binary
	ARCH=`uname -m`
	if [ "$ARCH" = "x86_64" ]; then
	    HADOOP_CLIB="Linux-amd64-64"
	elif [ "$ARCH" = "i686" -o "$ARCH" = "i386" ]; then
	    HADOOP_CLIB="Linux-i386-32"
	else
	    echo "$ARCH is not supported by Hadoop."
	    exit 1
	fi

	# to avoid ldconfig warnings
	pushd lib/native/${HADOOP_CLIB}
	ln -sfv libhadoop.so.1.0.0 libhadoop.so
	ln -sfv libhadoop.so.1.0.0 libhadoop.so.1
	popd

	DESTFILE=${DESTDIR}/etc/ld.so.conf.d/hadoop.conf
	mkdir -pv $(dirname $DESTFILE)
	echo "Generating $DESTFILE"
	cat <<EOF | tee $DESTFILE || exit 1
${APPSCALE_HOME_RUNTIME}/AppDB/hadoop-${HADOOP_VER}/c++/${HADOOP_CLIB}/lib
${APPSCALE_HOME_RUNTIME}/AppDB/hadoop-${HADOOP_VER}/lib/native/${HADOOP_CLIB}
EOF
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
    HBASE_VER=0.89.20100924
    HADOOP_VER=0.20.2

    mkdir -pv ${APPSCALE_HOME}/AppDB/hbase
    cd ${APPSCALE_HOME}/AppDB/hbase
    rm -rfv hbase-${HBASE_VER}
    wget http://appscale.cs.ucsb.edu/appscale_files/hbase-${HBASE_VER}.tar.gz -O hbase-${HBASE_VER}.tar.gz || exit 1

    tar zxvf hbase-${HBASE_VER}.tar.gz || exit 1
    rm -v hbase-${HBASE_VER}.tar.gz
    # Clean out the maven repository
    rm -rfd ~/.m2/
    # create link to hadoop core
    rm -rv ${APPSCALE_HOME}/AppDB/hbase/hbase-${HBASE_VER}/lib/hadoop-*.jar || true
    pushd hbase-${HBASE_VER}
    # using ip address instead of host name.
    patch -p0 -i ../patch/hbase-defaultip.patch || exit 1
    # Skipping this patch, and using the above applied hack
    # patch -p0 -i ../patch/hadoop_version.patch || exit 1 
    export MAVEN_OPTS=-Xmx1024m
    mvn -DskipTests install || exit 1
    if [ ! -e target/hbase-${HBASE_VER}.jar ]; then
	echo "Fail to compile HBase. Please try again."
	exit 1
    fi
    cp -vf target/hbase-${HBASE_VER}.jar . || exit 1
    if [ -n "${DESTDIR}" ]; then
	# remove unnecessary files.
	rm -rv build docs src
    fi

    # This is a hack, we overwrite the hadoop core jar 
    # Unable to get it done the right way with the hadoop_version.patch
    # We must overwrite it in the maven repository 
    # Very version sensitive and very much a hack
    #ln -sfv ${APPSCALE_HOME_RUNTIME}/AppDB/hadoop-${HADOOP_VER}/hadoop-${HADOOP_VER}-core.jar ${APPSCALE_HOME}/AppDB/hbase/hbase-${HBASE_VER}/lib/hadoop-0.20.3-append-r964955-1240-core.jar
    cp ${APPSCALE_HOME}/AppDB/hadoop-${HADOOP_VER}/hadoop-${HADOOP_VER}-core.jar  ~/.m2/repository/org/apache/hadoop/hadoop-core/0.20.3-append-r964955-1240/hadoop-core-0.20.3-append-r964955-1240.jar || exit 1
    # Need to update the zookeeper jar which was patched
    #cp zookeeper-${ZK_VER}.jar ~/.m2/repository/org/apache/hadoop/zookeeper/3.3.1/zookeeper-3.3.1.jar || exit 1
    DESTFILE=./conf/hbase-env.sh
    echo "Appending $DESTFILE"
    cat <<EOF | tee -a $DESTFILE || exit 1
. /etc/profile.d/appscale.sh
export HBASE_HEAPSIZE=2000
export HBASE_MANAGES_ZK=FALSE
export HBASE_OPTS="-Djava.net.preferIPv4Stack=true"
EOF
    popd

}

postinstallhbase()
{
    mkdir -p ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}
    touch ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}/hbase
}

installcassandra()
{
    CASSANDRA_VER=0.6.8

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
    mkdir -p ${DESTDIR}/var/lib/cassandra
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
    ln -sv /var/lib/python-support/python2.6/google/protobuf ${APPSCALE_HOME}/AppServer/google/
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
    easy_install pymongo

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

    mkdir -p ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}
    touch ${APPSCALE_HOME}/.appscale/${APPSCALE_VERSION}/mongodb
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

# install from source

installscalaris_fromsource()
{
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    wget http://scalaris.googlecode.com/files/scalaris-0.2.2.tar.bz2 || exit 1
    bzip2 -c -d scalaris-0.2.2.tar.bz2 | tar xv || exit 1
    if [ ! -e scalaris-0.2.2 ]; then
	echo "Fail to extract scalaris."
	exit 1
    fi

    rm -v scalaris-0.2.2.tar.bz2
    pushd scalaris-0.2.2
    # disable fqdn check
    patch -p0 -i ../../AppDB/scalaris/patch/scalarisctl.patch || exit 1
    patch -p0 -i ../../AppDB/scalaris/patch/scalaris-make.patch || exit 1
    ./configure --prefix=/usr || exit 1
    make || exit 1
    make docs
    make install || exit 1
    popd

    rm -rfv scalaris-0.2.2
    installpythonjsonrpc
}

# install using deb files

installscalaris()
{
    SCALARIS_VER=0.2.3-1

    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads

    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
	ARCH="amd64"
    fi
    if [ "$ARCH" = "i686" ]; then
	ARCH="i386"
    fi

    case "$DIST" in
	jaunty)
	    BASEURL=http://widehat.opensuse.org/repositories/home:/tschuett/xUbuntu_9.04/
	    ;;
	karmic)
	    BASEURL=http://widehat.opensuse.org/repositories/home:/tschuett/xUbuntu_9.10/
	    ;;
	lucid)
	    BASEURL=http://widehat.opensuse.org/repositories/home:/tschuett/xUbuntu_10.04/
	    ;;
	*)
	    echo "$DIST is not supported by scalaris."
	    exit 1
    esac

    # repackage deb files
    wget ${BASEURL}/${ARCH}/scalaris_${SCALARIS_VER}_${ARCH}.deb -O scalaris.deb || exit 1
    dpkg-deb --vextract scalaris.deb ${DESTDIR}/ || exit 1
    rm -v scalaris.deb
    wget ${BASEURL}/${ARCH}/scalaris-java_${SCALARIS_VER}_${ARCH}.deb -O scalaris-java.deb || exit 1
    # we don't need java and native client?
    dpkg-deb --vextract scalaris-java.deb ${DESTDIR}/ || exit 1
    rm -v scalaris-java.deb
    wget ${BASEURL}/${ARCH}/scalaris-client_${SCALARIS_VER}_${ARCH}.deb -O scalaris-client.deb || exit 1
    dpkg-deb --vextract scalaris-client.deb ${DESTDIR}/ || exit 1
    rm -v scalaris-client.deb

    # patch script
    sed 's/exit -1/#exit -1/' -i.org ${DESTDIR}/usr/bin/scalarisctl || exit 1

    installpythonjsonrpc
}

# install python-jsonrpc for scalaris

installpythonjsonrpc()
{
    cd ${APPSCALE_HOME}/downloads
    SVN_VER=19
    svn checkout -r ${SVN_VER} http://svn.json-rpc.org/trunk/python-jsonrpc || exit 1

    pushd python-jsonrpc
    patch -p0 -i ../../AppDB/scalaris/patch/python-jsonrpc.patch || exit 1
    python setup.py install --prefix=${DESTDIR}/usr || exit 1
    popd

    rm -rfv python-jsonrpc
}

postinstallscalaris()
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

    ZK_VER=3.4.0

    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads

    wget http://kings.cs.ucsb.edu/appscale_files/zookeeper-3.4.0.tar.gz || exit 1
    tar zxvf zookeeper-3.4.0.tar.gz

    pushd zookeeper-src
    # build java library
    ant || exit 1
    ant compile_jute || exit 1
    if [ ! -e build/zookeeper-${ZK_VER}.jar ]; then
	echo "Fail to make zookeeper java jar. Please retry."
	exit 1
    fi

    # build c library
    pushd src/c
#    sed -i 's/AM_PATH_CPPUNIT/:;#AM_PATH_CPPUNIT/g' configure.ac || exit 1
    autoreconf -if || exit 1
    ./configure --prefix=/usr || exit 1
    make || exit 1
    make install || exit 1
    if [ ! -e ${DESTDIR}/usr/lib/libzookeeper_mt.a ]; then
	echo "Fail to install libzookeeper. Please retry."
	exit 1
    fi
    popd

    # apply memory leak patch of zkpython
    patch -p0 -i ${APPSCALE_HOME}/AppDB/zkappscale/patch/zkpython-memory.patch || exit 1

    # python library
    pushd src/contrib/zkpython
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
    popd

    # install java library
    mkdir -pv ${DESTDIR}/usr/share/java
    cp -v build/zookeeper-${ZK_VER}.jar ${DESTDIR}/usr/share/java || exit 1
    ln -sfv zookeeper-${ZK_VER}.jar ${DESTDIR}/usr/share/java/zookeeper.jar || exit 1

    # install config files and service.
    BASEURL=http://appscale.cs.ucsb.edu/appscale_packages/pool/zookeeper
    wget ${BASEURL}/zookeeper_3.2.2+dfsg3-3_all.deb -O zookeeper.deb || exit 1
    dpkg-deb --vextract zookeeper.deb ${DESTDIR}/ || exit 1
    rm -v zookeeper.deb
    wget ${BASEURL}/zookeeperd_3.2.2+dfsg3-3_all.deb -O zookeeperd.deb || exit 1
    dpkg-deb --vextract zookeeperd.deb ${DESTDIR}/ || exit 1
    rm -v zookeeperd.deb

    if [ "${DIST}" = "jaunty" -o "${DIST}" = "karmic" ]; then
        # we must use own log4j in jaunty and karmic,
	# because the package jar does not include jmx classes.
	LOG4J_VER=1.2.15
	mkdir -pv ${DESTDIR}/usr/share/zookeeper/lib
	cp -v build/lib/log4j-${LOG4J_VER}.jar ${DESTDIR}/usr/share/zookeeper/lib/log4j-1.2.jar || exit 1
#	ln -sfv log4j-${LOG4J_VER}.jar ${DESTDIR}/usr/share/zookeeper/lib/log4j-1.2.jar || exit 1
	# modify class path.
	sed -i 's/java\/log4j/zookeeper\/lib\/log4j/' ${DESTDIR}/etc/zookeeper/conf_example/environment || exit 1
    fi

    popd
    rm -rv zookeeper-src || exit 1

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

# cgb: extremely experimental
installneptune()
{
    #installmpi
    installx10
    installupc
    installnfs
    installactivecloud
    # remember to comment these out when releasing
    #installdfsp
    installcewssa
}

postinstallneptune()
{
    postinstallmpi
    postinstallx10
    postinstallupc
    postinstallnfs
    postinstallactivecloud
    #postinstalldfsp
    postinstallcewssa
}

installmpi()
{
    mkdir -pv ${APPSCALE_HOME}/downloads
    cd ${APPSCALE_HOME}/downloads
    wget http://appscale.cs.ucsb.edu/appscale_files/mpich2-1.2.1p1.tar.gz || exit 1
    tar zxvf mpich2-1.2.1p1.tar.gz || exit 1
    rm -v mpich2-1.2.1p1.tar.gz
    pushd mpich2-1.2.1p1
    # fix the installation problem for deb package.
    patch -p0 -i ${APPSCALE_HOME}/Neptune/patch/mpi-install.patch || exit 1
    ./configure --prefix=/usr/local/mpich2 || exit 1
    make || exit 1
    make install DESTDIR=$DESTDIR || exit 1
    popd
    rm -rfv mpich2-1.2.1p1
    DESTFILE=${DESTDIR}/etc/profile.d/mpi.sh
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE || exit 1
export PATH=/usr/local/mpich2/bin:\$PATH
EOF
    DESTFILE=${DESTDIR}/etc/ld.so.conf.d/mpi.conf
    mkdir -pv $(dirname $DESTFILE)
    echo "Generating $DESTFILE"
    cat <<EOF | tee $DESTFILE || exit 1
/usr/local/mpich2/lib
EOF
}

postinstallmpi()
{
#    echo "/usr/local/mpich2/bin" >> /etc/environment
    echo "MPD_SECRETWORD=something" >> /etc/mpd.conf
    chmod -v 600 /etc/mpd.conf
}

installx10()
{
    cd ${DESTDIR}/usr/local/
    wget http://appscale.cs.ucsb.edu/appscale_files/x10-2.1.0-prebuilt.tar.gz || exit 1
    tar zxvf x10-2.1.0-prebuilt.tar.gz || exit 1
    cd x10/x10.dist
    #ant dist -DX10RT_MPI=true # this will fail with a cvs message, but it actually gets
    # far enough to succeed
    chmod +x bin/x10c++ bin/x10c
    cd ${DESTDIR}/usr/local/
    rm -v x10-2.1.0-prebuilt.tar.gz
}

postinstallx10()
{
    :;
}

installupc()
{
    cd ${DESTDIR}/usr/local/
    wget http://kings.cs.ucsb.edu/appscale_files/berkeley_upc-2.12.1.tar.gz || exit 1
    tar zxvf berkeley_upc-2.12.1.tar.gz
    cd berkeley_upc-2.12.1
    ./configure MPI_CC='/usr/bin/mpicc  -O0 -UNDEBUG'
    make
    cd ${DESTDIR}/usr/local/
    rm -v berkeley_upc-2.12.1.tar.gz
}

postinstallupc()
{
    :;
}

installnfs()
{
# this should be in control.core
#    apt-get install -y nfs-kernel-server
    mkdir -pv ${DESTDIR}/mirrornfs
}

postinstallnfs()
{
    service nfs-kernel-server stop || true
    service nfs-common stop || true
    update-rc.d -f nfs-kernel-server remove || true
    if [ ! -e /etc/exports -o -z "$(grep mirrornfs /etc/exports)" ]; then
	echo "/mirrornfs *(rw,no_root_squash,sync)" >> /etc/exports
    fi
}

installdfsp()
{
# this should be in control.core
#    apt-get install -y gsl-bin libgsl0-dev libgsl0ldbl
    mkdir -pv ${DESTDIR}/usr/local
    cd ${DESTDIR}/usr/local
    rm -v dfsp-0.1-tar.gz
}

postinstalldfsp()
{
    mkdir -pv /usr/local/dfsp/output
}

installcewssa()
{
    wget http://kings.cs.ucsb.edu/appscale_files/cewSSA_0.5-1.tar.gz
    R CMD INSTALL cewSSA_0.5-1.tar.gz
    rm cewSSA_0.5-1.tar.gz
}

postinstallcewssa()
{
    mkdir -p /usr/local/cewssa/data
}

installactivecloud()
{
    mkdir -pv ${DESTDIR}/usr/local
    cd ${DESTDIR}/usr/local
    wget http://appscale.cs.ucsb.edu/appscale_files/active-cloud-0.1-tar.gz || exit 1
    tar zxvf active-cloud-0.1-tar.gz || exit 1
    rm -v active-cloud-0.1-tar.gz
}

postinstallactivecloud()
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
