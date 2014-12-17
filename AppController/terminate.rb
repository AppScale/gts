$:.unshift File.join(File.dirname(__FILE__), "lib")
APPSCALE_HOME = ENV['APPSCALE_HOME']

module TerminateHelper


  # Erases all AppScale-related files (except database state) from the local
  # filesystem.
  # TODO: Use FileUtils.rm_rf instead of backticks throughout this
  # method.
  # I remember it had some problems with *s, so look into that
  # maybe glob it with Dir.glob? to alleviate this?
  def self.erase_appscale_state
    `rm -f #{APPSCALE_HOME}/.appscale/secret.key`
    `rm -f #{APPSCALE_HOME}/.appscale/status-*`
    `rm -f #{APPSCALE_HOME}/.appscale/database_info`
    `rm -f /tmp/uploaded-apps`
    `rm -f ~/.appscale_cookies`
    `rm -f /var/log/appscale/*.log.*`
    `rm -f /var/log/appscale/*.log`
    `rm -f /var/log/appscale/*.gz`
    `rm -rf /var/log/appscale/celery_workers`
    `rm -f /var/appscale/*.pid`
    `rm -f /etc/nginx/sites-enabled/*.conf`
    `rm -f /etc/monit/conf.d/*.cfg`
    `rm -f /etc/appscale/port-*.txt`
    `rm -f /etc/appscale/search_location`

    # TODO: It may be wise to save the apps for when AppScale starts up
    # later.
    `rm -rf /var/apps/`
    `rm -rf #{APPSCALE_HOME}/.appscale/*.pid`
    `rm -rf /tmp/ec2/*`
    `rm -rf /tmp/*started`

    # TODO: Use the constant in djinn.rb (ZK_LOCATIONS_FILE)
    `rm -rf /etc/appscale/zookeeper_locations.json`
    `rm -f /opt/appscale/appcontroller-state.json`
    `rm -f /opt/appscale/appserver-state.json`
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

    # Next, stop ZooKeeper politely.
    `service zookeeper-server stop`
  end


  # Erases all data stored in the Datastore (Cassandra + ZooKeeper).
  def self.erase_database_state
    `rm -rf /var/appscale/cassandra`
    `rm -rf /opt/appscale/cassandra`
    `rm -rf /opt/appscale/zookeeper`
    `rm -rf /opt/appscale/apps`
    `rm -rf /opt/appscale/celery`
    `rm -rf /opt/appscale/search`
  end


  # Restores AppScale back to a pristine state by killing any service that is
  # associated with AppScale.
  def self.force_kill_processes
    `iptables -F`  # turn off the firewall
    `monit stop all`
    `monit unmonitor all`
    `monit quit`

    ["memcached",
     "nginx", "haproxy",
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
  end

  TerminateHelper.force_kill_processes
  TerminateHelper.kill_ruby
end
