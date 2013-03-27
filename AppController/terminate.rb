$:.unshift File.join(File.dirname(__FILE__), "lib")

begin
  require 'cron_helper'
  CronHelper.clear_crontab
rescue Exception
  puts "Problem with cronhelper, moving on"
end

begin
  require 'load_balancer'
  LoadBalancer.stop
rescue Exception
  puts "Problem with loadbalancer, moving on"
end

begin
  require 'monitoring'
  Monitoring.stop
rescue Exception
  puts "Problem with monitoring, moving on"
end

begin
  require 'haproxy'
  HAProxy.clear_sites_enabled
  HAProxy.stop
rescue Exception
  puts "Problem with haproxy, moving on"
end

begin
  require 'collectd'
  Collectd.clear_sites_enabled
  Collectd.clear_monitoring_data
  Collectd.stop
rescue Exception
  puts "Problem with collectd, moving on"
end

begin
  require 'nginx'
  Nginx.clear_sites_enabled
  Nginx.stop
rescue Exception
  puts "Problem with nginx, moving on"
end

begin
  require 'godinterface'
  GodInterface.shutdown()
rescue Exception
  puts "Problem with god, moving on"
end

APPSCALE_HOME = ENV['APPSCALE_HOME']

begin
  require 'datastore_server'
  tree = YAML.load_file("#{APPSCALE_HOME}/.appscale/database_info.yaml")
  DatastoreServer.stop(tree[:table])
rescue Exception
  puts "Problem with datastore server, moving on"
end

`bash #{APPSCALE_HOME}/AppController/killDjinn.sh`
# we should not call appscale-controller because it is parent.
#`service appscale-controller stop`

`rm -f #{APPSCALE_HOME}/.appscale/secret.key`
#`rm -rf /tmp/*.log`
#`rm -rf /tmp/h*`
`rm -f #{APPSCALE_HOME}/.appscale/status-*`
`rm -f #{APPSCALE_HOME}/.appscale/database_info`
`rm -f #{APPSCALE_HOME}/.appscale/neptune_info.txt`
`rm -f /tmp/uploaded-apps`
`rm -f ~/.appscale_cookies`
`rm -f /var/log/appscale/*.log`
`rm -rdf /var/log/appscale/celery_workers`
`rm -f /var/appscale/*.pid`
`rm -f /etc/appscale/appcontroller-state.json`

#Ejabberd.stop
#Ejabberd.clear_online_users

# klogd is installed on jaunty but not karmic
klogd = "/etc/init.d/klogd"
if File.exists?(klogd)
  `#{klog} stop`
end

# TODO(cgb): Use FileUtils.rm_rf
# I remember it had some problems with *s, so look into that
# maybe glob it with Dir.glob? to alleviate this?
`rm -rf /var/apps/`
`rm -rf #{APPSCALE_HOME}/.appscale/*.pid`
`rm -rf /tmp/ec2/*`
`rm -rf /tmp/*started`
`rm -rf #{APPSCALE_HOME}/appscale/`

`rm -rf /var/appscale/cassandra/commitlog/*`
`rm -rf /var/appscale/cassandra/data/system/*`

`rm -rf /var/appscale/zookeeper/*`
# TODO(cgb): Use the constant in djinn.rb (ZK_LOCATIONS_FILE)
`rm -rf /etc/appscale/zookeeper_locations.json`

`rm -rf /var/cache/neptune/*`

`echo "" > /root/.ssh/known_hosts` # empty it out but leave the file there

`iptables -F`  # turn off the firewall

# force kill processes

["memcached",
 "nginx", "haproxy", "collectd", "collectdmon",
 "soap_server", "appscale_server", "app_manager_server", "datastore_server",
 "taskqueue_server", "AppLoadBalancer", "AppMonitoring",
 # AppServer
 "dev_appserver", "DevAppServerMain",
 #Blobstore
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
 # MySQL
 "ndb_mgmd", "ndbd", "mysqld",
 "rabbitmq",
 "thin", "god", "djinn", "xmpp_receiver", 
 "InfrastructureManager", "Neptune",
 # RabbitMQ, ejabberd
 "epmd", "beam", "ejabberd_auth.py", "celery",
 # Last resort
 "ruby", "python", "java", "/usr/bin/python"
].each do |program|
  `ps ax | grep #{program} | grep -v grep | awk '{ print $1 }' | xargs -d '\n' kill -9`
end
