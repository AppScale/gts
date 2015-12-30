require 'djinn'


# The location on the local filesystem where we should store ZooKeeper data.
DATA_LOCATION = "/opt/appscale/zookeeper"

ZOOKEEPER_PORT="2181"

# The path in ZooKeeper where the deployment ID is stored.
DEPLOYMENT_ID_PATH = '/appscale/deployment_id'

def configure_zookeeper(nodes, my_index)
  # TODO: create multi node configuration
  zoocfg = <<EOF
# The number of milliseconds of each tick.
tickTime=2000
# The number of ticks that the initial synchronization phase can take.
initLimit=10
# The number of ticks that can pass between sending a request and getting
# an acknowledgement.
syncLimit=5
# The directory where the snapshot is stored.
dataDir=#{DATA_LOCATION}
# The port at which the clients will connect.
clientPort=2181
# Number of concurrent connections (at the socket level) that a single
# client, can have. Setting this to 0 or omitting it entirely removes the
# limit on concurrent connections.
maxClientCnxns=0
# Leader accepts client connections. Default value is "yes".
leaderServes=yes
# Requires updates to be synced to media of the transaction log before
# finishing processing the update.
forceSync=no
# Skips ACL checks. This results in a boost in throughput, but opens up
# full access to the data tree to everyone.
skipACL=yes
# The number of snapshots to retain in dataDir
autopurge.snapRetainCount=3
# Purge task interval in hours
# Set to "0" to disable auto purge feature
autopurge.purgeInterval=1
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
end

def start_zookeeper(clear_datastore)
  Djinn.log_info("Starting ZooKeeper")
  if clear_datastore
    Djinn.log_run("rm -rfv /var/lib/zookeeper")
    Djinn.log_run("rm -rfv #{DATA_LOCATION}")
  end

  # Detect which version of zookeeper script we have.
  zk_server="zookeeper-server"
  if system("service --status-all|grep zookeeper$")
    zk_server="zookeeper"
  end

  if !File.directory?("#{DATA_LOCATION}")
    Djinn.log_info("Initializing ZooKeeper")
    # Let's stop zookeeper in case it is still running.
    system("/usr/sbin/service #{zk_server} stop")

    # Let's create the new location for zookeeper.
    Djinn.log_run("mkdir -pv #{DATA_LOCATION}")
    Djinn.log_run("chown -Rv zookeeper:zookeeper #{DATA_LOCATION}")

    # Only precise (and zookeeper-server) has an init function.
    if zk_server == "zookeeper-server"
      if not system("/usr/sbin/service #{zk_server} init")
        Djinn.log_error("Failed to start zookeeper!")
        raise Exception FailedZooKeeperOperationException.new("Failed to" +
          " start zookeeper!")
      end
    end
  end

  # myid is needed for multi node configuration.
  Djinn.log_run("ln -sfv /etc/zookeeper/conf/myid #{DATA_LOCATION}/myid")

  start_cmd = "/usr/sbin/service #{zk_server} start"
  stop_cmd = "/usr/sbin/service #{zk_server} stop"
  match_cmd = "org.apache.zookeeper.server.quorum.QuorumPeerMain"
  MonitInterface.start(:zookeeper, start_cmd, stop_cmd, ports=ZOOKEEPER_PORT, env_vars=nil,
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

