$:.unshift File.join(File.dirname(__FILE__), "lib")
require 'fileutils'

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
    `rm -f /etc/nginx/sites-enabled/appscale-*.conf`
    `rm -f /etc/haproxy/sites-enabled/*.cfg`
    `service nginx reload`
    while system("monit summary | grep Running > /dev/null") do
      # Stop and then remove the service we configured with monit.
      `monit stop all`
      puts "Waiting for monit to stop services ..."
      Kernel.sleep(10)
    end

    `rm -f /etc/monit/conf.d/appscale*.cfg`
    `rm -f /etc/monit/conf.d/controller-17443.cfg`

    `rm -f /etc/logrotate.d/appscale-*`

    # Let's make sure we restart any non-appscale service.
    `service monit restart`
    `/usr/bin/python2 /root/appscale/scripts/stop_service.py /root/appscale/AppController/djinnServer.rb /usr/bin/ruby`
    `monit start all`
    `rm -f #{APPSCALE_CONFIG_DIR}/port-*.txt`

    # Remove location files.
    FileUtils.rm_f("#{APPSCALE_CONFIG_DIR}/all_ips")
    FileUtils.rm_f("#{APPSCALE_CONFIG_DIR}/load_balancer_ips")
    FileUtils.rm_f("#{APPSCALE_CONFIG_DIR}/login_ip")
    FileUtils.rm_f("#{APPSCALE_CONFIG_DIR}/masters")
    FileUtils.rm_f("#{APPSCALE_CONFIG_DIR}/memcache_ips")
    FileUtils.rm_f("#{APPSCALE_CONFIG_DIR}/my_private_ip")
    FileUtils.rm_f("#{APPSCALE_CONFIG_DIR}/my_public_ip")
    FileUtils.rm_f("#{APPSCALE_CONFIG_DIR}/num_of_nodes")
    FileUtils.rm_f("#{APPSCALE_CONFIG_DIR}/search_ip")
    FileUtils.rm_f("#{APPSCALE_CONFIG_DIR}/slaves")
    FileUtils.rm_f("#{APPSCALE_CONFIG_DIR}/taskqueue_nodes")

    # TODO: Use the constant in djinn.rb (ZK_LOCATIONS_FILE)
    `rm -rf #{APPSCALE_CONFIG_DIR}/zookeeper_locations.json`
    `rm -f /opt/appscale/appcontroller-state.json`
    `rm -f /opt/appscale/appserver-state.json`
    print "OK"
  end

  # This functions does erase more of appscale state: used in combination
  # with 'clean'.
  def self.erase_appscale_full_state
    # Delete logs.
    `rm -rf /var/log/appscale/*`
    `rm -rf /var/log/rabbitmq/*`
    `rm -rf /var/log/zookeeper/*`
    `rm -rf /var/log/nginx/appscale-*`

    # Delete running state.
    `rm -rf /var/apps/`
    `rm -rf #{APPSCALE_CONFIG_DIR}/*.pid`
    `rm -rf /tmp/ec2/*`
    `rm -rf /tmp/*started`

    # Delete stored data.
    `rm -rf /opt/appscale/cassandra`
    `rm -rf /opt/appscale/zookeeper`
    `rm -rf /opt/appscale/apps`
    `rm -rf /opt/appscale/solr`
    `rm -rf /var/lib/rabbitmq/*`
    `rm -rf /etc/appscale/celery/`
    `rm -rf /opt/appscale/celery`
    print "OK"
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

    # Make sure we have cassandra running, otherwise nodetool may get
    # stuck.
    if system("monit summary | grep cassandra | grep Running > /dev/null")
      `/opt/cassandra/cassandra/bin/nodetool -h #{ip} -p 7199 drain`
    end

    # Next, stop ZooKeeper politely: we stop it with both new and old
    # script to be sure.
    `service zookeeper-server stop`
    `service zookeeper stop`
  end
end


if __FILE__ == $0
  TerminateHelper.disable_database_writes
  TerminateHelper.erase_appscale_state

  if ARGV.length == 1 and ARGV[0] == "clean"
    TerminateHelper.erase_appscale_full_state
  end
end
