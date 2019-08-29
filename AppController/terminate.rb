require 'find'
require 'pty'

$:.unshift File.join(File.dirname(__FILE__), "lib")
require 'fileutils'

APPSCALE_CONFIG_DIR = "/etc/appscale"

module TerminateHelper
  # Erases all AppScale-related files (except database state) from the local
  # filesystem. This is used when appscale is shutdown.
  # TODO: Use FileUtils.rm_rf instead of backticks throughout this
  # method.
  def self.erase_appscale_state
    `service appscale-controller stop`

    `rm -f #{APPSCALE_CONFIG_DIR}/secret.key`
    `rm -f /tmp/uploaded-apps`
    `rm -f ~/.appscale_cookies`
    `rm -f /etc/nginx/sites-enabled/appscale-*.conf`
    `rm -f /etc/haproxy/service-sites-enabled/*.cfg`
    `service nginx reload`

    begin
      PTY.spawn('appscale-stop-services') do |stdout, _, _|
        begin
          stdout.each { |line| print line }
        rescue Errno::EIO
          # The process has likely finished giving output.
        end
      end
    rescue PTY::ChildExited
      # The process has finished.
    end

    `rm -f /etc/monit/conf.d/appscale*.cfg`
    `rm -f /etc/monit/conf.d/controller-17443.cfg`

    # Stop datastore and search servers.
    for slice_name in ['appscale-datastore', 'appscale-search']
        slice = "/sys/fs/cgroup/systemd/appscale.slice/#{slice_name}.slice"
        begin
          Find.find(slice) do |path|
            next unless File.basename(path) == 'cgroup.procs'
            File.readlines(path).each do |pid|
              `kill #{pid}`
            end
          end
        rescue Errno::ENOENT
          # If there are no processes running, there is no need to stop them.
        end
    end

    `rm -f /etc/logrotate.d/appscale-*`

    # Let's make sure we restart any non-appscale service.
    `service monit restart`
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

    # TODO: Use the constant in djinn.rb (ZK_LOCATIONS_JSON_FILE)
    `rm -rf #{APPSCALE_CONFIG_DIR}/zookeeper_locations.json`
    `rm -rf #{APPSCALE_CONFIG_DIR}/zookeeper_locations`
    `rm -f /opt/appscale/appcontroller-state.json`
    `rm -f /opt/appscale/appserver-state.json`
    print "OK"
  end

  # This functions ensure that the services AppScale started that have a
  # PID in /var/run/appscale got terminated.
  def self.ensure_services_are_stopped
    Dir["/var/run/appscale/*.pid"].each { |pidfile|
      # Nothing should still be running after the controller got stopped,
      # so we unceremoniously kill them.
      begin
        pid = File.read(pidfile).chomp
        Process.kill("KILL", Integer(pid))
      rescue ArgumentError, Errno::EPERM, Errno::EINVAL, Errno::ENOENT
        next
      rescue Errno::ESRCH, RangeError
      end
      FileUtils.rm_f(pidfile)
    }
  end

  # This functions does erase more of appscale state: used in combination
  # with 'clean'.
  def self.erase_appscale_full_state
    # Delete logs.
    `rm -rf /var/log/appscale/*`

    # Restart rsyslog so that the combined app logs can be recreated.
    `service rsyslog restart`

    `rm -rf /var/log/rabbitmq/*`
    `rm -rf /var/log/zookeeper/*`
    `rm -rf /var/log/nginx/appscale-*`

    # Delete running state.
    `rm -rf /var/apps/`
    `rm -rf #{APPSCALE_CONFIG_DIR}/*.pid`
    `rm -rf /tmp/ec2/*`
    `rm -rf /tmp/*started`
    `rm -rf /etc/cron.d/appscale-*`

    # Delete stored data.
    `rm -rf /opt/appscale/cassandra`
    `rm -rf /opt/appscale/zookeeper`
    `rm -rf /opt/appscale/logserver/*`
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
  TerminateHelper.ensure_services_are_stopped

  if ARGV.length == 1 and ARGV[0] == "clean"
    TerminateHelper.erase_appscale_full_state
  end
end
