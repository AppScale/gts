require 'djinn'
require 'godinterface'


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
  Djinn.log_debug(`sed -i s/^JAVA_OPTS=.*/JAVA_OPTS=\"-Xmx1024m\"/ /etc/zookeeper/conf/environment`)
end

def start_zookeeper()
  Djinn.log_info("starting ZooKeeper")
  if @creds['clear_datastore']
    Djinn.log_debug(`rm -rfv /var/lib/zookeeper`)
    Djinn.log_debug(`rm -rfv #{DATA_LOCATION}`)
  end
  Djinn.log_debug(`mkdir -pv #{DATA_LOCATION}`)
  Djinn.log_debug(`chown -v zookeeper:zookeeper #{DATA_LOCATION}`)

  # myid is needed for multi node configuration.
  Djinn.log_debug(`ln -sfv /etc/zookeeper/conf/myid #{DATA_LOCATION}`)

  start_cmd = "service zookeeper start"
  stop_cmd = "service zookeeper stop"
  env = {'JAVA_HOME' => ENV['JAVA_HOME']}
  GodInterface.start(:zoo_keeper, start_cmd, 
                     stop_cmd, ZOOKEEPER_PORT, env)
  Djinn.log_info('Started ZooKeeper')
end

def stop_zookeeper
  Djinn.log_info("Stopping ZooKeeper")
  GodInterface.stop(:zoo_keeper)  
  # God has problems correctly shutting down processes, 
  # so we double up on stopping ZK here.
  Djinn.log_debug(`service zookeeper stop`)
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

