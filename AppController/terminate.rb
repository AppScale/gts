$:.unshift File.join(File.dirname(__FILE__), "lib")
APPSCALE_CONFIG_DIR = "/etc/appscale"

module TerminateHelper


  # Erases all AppScale-related files (except database state) from the local
  # filesystem. This is used when appscale is shutdown.
  # TODO: Use FileUtils.rm_rf instead of backticks throughout this
  # method.
  def self.erase_appscale_state
    `rm -f #{APPSCALE_CONFIG_DIR}/secret.key`
    `rm -f /tmp/uploaded-apps`
    `rm -f ~/.appscale_cookies`
    `rm -f /var/appscale/*.pid`
    `rm -f /etc/nginx/sites-enabled/*.conf`
    `service nginx reload`
    # Stop and then remove the service we configured with monit.
    `monit stop all`
    `rm -f /etc/monit/conf.d/appscale*.cfg`
    `rm -f /etc/monit/conf.d/controller-17443.cfg`
    `service monit restart`
    `killall -9 -g -r djinnServer`
    `monit start all`
    `rm -f #{APPSCALE_CONFIG_DIR}/port-*.txt`
    `rm -f #{APPSCALE_CONFIG_DIR}/search_ip`

    # TODO: Use the constant in djinn.rb (ZK_LOCATIONS_FILE)
    `rm -rf #{APPSCALE_CONFIG_DIR}/zookeeper_locations.json`
    `rm -f /opt/appscale/appcontroller-state.json`
    `rm -f /opt/appscale/appserver-state.json`
  end

  # This functions does erase more of appscale state: used in combination
  # with 'clean'.
  def self.erase_appscale_full_state
    `rm -rf /var/log/appscale/cassandra`
    `rm -rf /var/log/appscale/celery_workers`
    `rm -f /var/log/appscale/*`

    # TODO: It may be wise to save the apps for when AppScale starts up
    # later.
    `rm -rf /var/apps/`
    `rm -rf #{APPSCALE_CONFIG_DIR}/*.pid`
    `rm -rf /tmp/ec2/*`
    `rm -rf /tmp/*started`
  end


  # Tells any services that persist data across AppScale runs to stop writing
  # new data to the filesystem, since killing them is imminent.
  #
  # For right now, this is just Cassandra and ZooKeeper.
  def self.disable_database_writes
    # First, tell Cassandra that no more writes should be accepted on this node.
    ifconfig = `ifconfig`
    bound_addrs = ifconfig.scan(/inet addr:(\d+.\d+.\d+.\d+)/).flatten
    bound_addrs.delete("127.0.0.1")
    ip = bound_addrs[0]

    `/root/appscale/AppDB/cassandra/cassandra/bin/nodetool -h #{ip} -p 7070 drain`

    # Next, stop ZooKeeper politely: we stop it with both new and old
    # script to be sure.
    `service zookeeper-server stop`
    `service zookeeper stop`
  end


  # Erases all data stored in the Datastore (Cassandra + ZooKeeper).
  def self.erase_database_state
    `rm -rf /var/appscale/cassandra`
    `rm -rf /opt/appscale/cassandra`
    `rm -rf /opt/appscale/zookeeper`
    `rm -rf /opt/appscale/apps`
    `rm -rf /opt/appscale/celery`
    `rm -rf /opt/appscale/solr`
  end
end


if __FILE__ == $0
  TerminateHelper.disable_database_writes
  TerminateHelper.erase_appscale_state

  if ARGV.length == 1 and ARGV[0] == "clean"
    TerminateHelper.erase_database_state
    TerminateHelper.erase_appscale_full_state
  end
end
