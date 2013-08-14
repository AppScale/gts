$:.unshift File.join(File.dirname(__FILE__), "lib")
APPSCALE_HOME = ENV['APPSCALE_HOME']

module TerminateHelper


  # Erases all AppScale-related files (except database state) from the local
  # filesystem.
  # TODO(cgb): Use FileUtils.rm_rf instead of backticks throughout this
  # method.
  # I remember it had some problems with *s, so look into that
  # maybe glob it with Dir.glob? to alleviate this?
  def self.erase_appscale_state
    `rm -f #{APPSCALE_HOME}/.appscale/secret.key`
    `rm -f #{APPSCALE_HOME}/.appscale/status-*`
    `rm -f #{APPSCALE_HOME}/.appscale/database_info`
    `rm -f #{APPSCALE_HOME}/.appscale/neptune_info.txt`
    `rm -f /tmp/uploaded-apps`
    `rm -f ~/.appscale_cookies`
    `rm -f /var/log/appscale/*.log`
    `rm -rdf /var/log/appscale/celery_workers`
    `rm -f /var/appscale/*.pid`
    `rm -f /etc/appscale/appcontroller-state.json`

    # TODO(cgb): It may be wise to save the apps for when AppScale starts up
    # later.
    `rm -rf /var/apps/`
    `rm -rf #{APPSCALE_HOME}/.appscale/*.pid`
    `rm -rf /tmp/ec2/*`
    `rm -rf /tmp/*started`

    # TODO(cgb): Use the constant in djinn.rb (ZK_LOCATIONS_FILE)
    `rm -rf /etc/appscale/zookeeper_locations.json`
    `rm -rf /var/cache/neptune/*`
  end


  def self.disable_cassandra_writes()
    ifconfig = `ifconfig`
    bound_addrs = ifconfig.scan(/inet addr:(\d+.\d+.\d+.\d+)/).flatten
    bound_addrs.delete("127.0.0.1")
    ip = bound_addrs[0]

    `/root/appscale/AppDB/cassandra/cassandra/bin/nodetool -h #{ip} -p 7070 drain`
  end


  # Erases all data stored in the Datastore (Cassandra + ZooKeeper).
  def self.erase_database_state
    `rm -rf /var/appscale/cassandra`
    `rm -rf /opt/appscale/cassandra`
    `rm -rf /opt/appscale/zookeeper`
    `rm -rf /opt/appscale/apps`
  end


  # Restores AppScale back to a pristine state by killing any service that is
  # associated with AppScale.
  def self.force_kill_processes
    `iptables -F`  # turn off the firewall

    ["memcached",
     "nginx", "haproxy", "collectd", "collectdmon",
     "soap_server", "appscale_server", "app_manager_server", "datastore_server",
     "taskqueue_server", "AppDashboard", "AppMonitoring",

     # AppServer
     "dev_appserver", "DevAppServerMain",

     # Blobstore
     "blobstore_server",

     # Cassandra
     "CassandraDaemon",

     # Hadoop
     "NameNode", "DataNode", "JobTracker", "TaskTracker",

     # HBase, ZooKeeper
     "HMaster", "HRegionServer", "HQuorumPeer", "QuorumPeerMain",
     "ThriftServer",

     # Hypertable
     "Hyperspace", "Hypertable.Master", "Hypertable.RangeServer", "ThriftBroker",
     "DfsBroker",
     "rabbitmq",
     "thin", "god", "djinn", "xmpp_receiver",
     "InfrastructureManager", "Neptune",

     # RabbitMQ, ejabberd
     "epmd", "beam", "ejabberd_auth.py", "celery",

     # Last resort
     "python", "java", "/usr/bin/python"
    ].each do |program|
      # grep out appscale-tools here since the user could be running the tools
      # on this machine, and that would otherwise cause this command to kill
      # itself.
      `ps ax | grep #{program} | grep -v grep | grep -v 'appscale-tools/bin/appscale' | awk '{ print $1 }' | xargs -d '\n' kill -9`
    end
  end


  # Kills all Ruby processes on this machine, except for this one.
  def self.kill_ruby
    `ps ax | grep ruby | grep -v terminate | grep -v grep | awk '{ print $1 }' | xargs -d '\n' kill -9`
  end


end

if __FILE__ == $0
  TerminateHelper.erase_appscale_state

  TerminateHelper.disable_cassandra_writes
  if ARGV.length == 1 and ARGV[0] == "clean"
    TerminateHelper.erase_database_state
  end

  TerminateHelper.force_kill_processes
  TerminateHelper.kill_ruby
end
