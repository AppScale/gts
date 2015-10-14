$:.unshift File.join(File.dirname(__FILE__), "lib")
APPSCALE_HOME = ENV['APPSCALE_HOME']

module TerminateHelper


  # Erases all AppScale-related files (except database state) from the local
  # filesystem. This is used when appscale is shutdown.
  # TODO: Use FileUtils.rm_rf instead of backticks throughout this
  # method.
  def self.erase_appscale_state
    `rm -f #{APPSCALE_HOME}/.appscale/secret.key`
    `rm -f #{APPSCALE_HOME}/.appscale/database_info`
    `rm -f /tmp/uploaded-apps`
    `rm -f ~/.appscale_cookies`
    `rm -f /var/appscale/*.pid`
    `rm -f /etc/nginx/sites-enabled/*.conf`
    `service monit stop`
    `rm -f /etc/monit/conf.d/appscale*.cfg`
    `service monit start`
    `rm -f /etc/appscale/port-*.txt`
    `rm -f /etc/appscale/search_ip`

    # TODO: Use the constant in djinn.rb (ZK_LOCATIONS_FILE)
    `rm -rf /etc/appscale/zookeeper_locations.json`
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
    `rm -rf #{APPSCALE_HOME}/.appscale/*.pid`
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


  # Restores AppScale back to a pristine state by killing any service that is
  # associated with AppScale.
  def self.force_kill_processes
    `iptables -F`  # turn off the firewall
    `service monit stop`

    ["memcached",
     "nginx", "haproxy", "hermes",
     "soap_server", "appscale_server", "app_manager_server", "datastore_server",
     "taskqueue_server", "AppDashboard",

     # AppServer
     "dev_appserver", "DevAppServerMain",

     # Blobstore
     "blobstore_server",

     # Cassandra
     "CassandraDaemon",

     # ZooKeeper
     "ThriftServer",

     "rabbitmq",
     "monit", "djinn", "xmpp_receiver",
     "InfrastructureManager", "Neptune",

     # RabbitMQ, ejabberd
     "epmd", "beam", "ejabberd_auth.py", "celery",

     # Search API
     "solr",

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
  TerminateHelper.disable_database_writes

  if ARGV.length == 1 and ARGV[0] == "clean"
    TerminateHelper.erase_database_state
    TerminateHelper.erase_appscale_full_state
  end

  TerminateHelper.force_kill_processes
  TerminateHelper.kill_ruby
end
