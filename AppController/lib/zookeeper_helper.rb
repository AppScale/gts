require 'djinn'


# The location on the local filesystem where we should store ZooKeeper data.
DATA_LOCATION = "/opt/appscale/zookeeper"


ZOOKEEPER_PORT="2181"


def configure_zookeeper(nodes, my_index)
  # TODO: create multi node configuration
  zoocfg = <<EOF
tickTime=2000
initLimit=10
syncLimit=5
dataDir=#{DATA_LOCATION}
clientPort=2181
leaderServes=yes
maxClientsCnxns=0
forceSync=no
skipACL=yes
autopurge.snapRetainCount=5
autopurge.purgeInterval=12
EOF
  myid = ""

  zoosize = nodes.count { |node| node.is_zookeeper? }

  if zoosize > 1
    # from 3.4.0, server settings is valid only in two or more nodes.
    zooid = 1
    nodes.each_with_index { |node,index|
      if node.is_zookeeper?
        zoocfg += <<EOF
server.#{zooid}=#{node.private_ip}:2888:3888
EOF
        if index == my_index
          myid = zooid.to_s
        end
        zooid += 1
      end
    }
  end

  Djinn.log_debug("zookeeper configuration=#{zoocfg}")
  File.open("/etc/zookeeper/conf/zoo.cfg", "w+") { |file| file.write(zoocfg) }

  Djinn.log_debug("zookeeper myid=#{myid}")
  File.open("/etc/zookeeper/conf/myid", "w+") { |file| file.write(myid) }

  # set max heap memory
  Djinn.log_run("sed -i s/^JAVA_OPTS=.*/JAVA_OPTS=\"-Xmx1024m\"/ /etc/zookeeper/conf/environment")
end

def start_zookeeper(clear_datastore)
  Djinn.log_info("Starting ZooKeeper")
  if clear_datastore
    Djinn.log_run("rm -rfv /var/lib/zookeeper")
    Djinn.log_run("rm -rfv #{DATA_LOCATION}")
  end

  if !File.directory?("#{DATA_LOCATION}")
    Djinn.log_info("Initializing ZooKeeper")
    Djinn.log_run("mkdir -pv #{DATA_LOCATION}")
    Djinn.log_run("chown -Rv zookeeper:zookeeper #{DATA_LOCATION}")
    result = system("service --status-all 2> /dev/null|grep zookeeper-server")
    if result == 0
      Djinn.log_run("/usr/sbin/service zookeeper-server init")
    else
      Djinn.log_run("/usr/sbin/service zookeeper init")
    end
  end

  # myid is needed for multi node configuration.
  Djinn.log_run("ln -sfv /etc/zookeeper/conf/myid #{DATA_LOCATION}/myid")

  result = system("service --status-all 2> /dev/null|grep zookeeper-server")
  if result == 0
    start_cmd = "/usr/sbin/service zookeeper-server start"
    stop_cmd = "/usr/sbin/service zookeeper-server stop"
  else
    start_cmd = "/usr/sbin/service zookeeper start"
    stop_cmd = "/usr/sbin/service zookeeper stop"
  end
  match_cmd = "org.apache.zookeeper.server.quorum.QuorumPeerMain"
  MonitInterface.start(:zookeeper, start_cmd, stop_cmd, ports=9999, env_vars=nil,
    remote_ip=nil, remote_key=nil, match_cmd=match_cmd)
  Djinn.log_info("Started ZooKeeper")
end

def stop_zookeeper
  Djinn.log_info("Stopping ZooKeeper")
  MonitInterface.stop(:zookeeper)
end

# This method returns ZooKeeper connection string like:
# server1:2181,server2:2181

def get_zk_connection_string(nodes)
  zlist = []
  nodes.each { |node|
    zlist.push("#{node.private_ip}:#{ZOOKEEPER_PORT}") if node.is_zookeeper?
  }
  return zlist.join(",")
end

