#!/usr/bin/ruby -w

require 'fileutils'

# A class to wrap all the interactions with the collectd monitoring system
class Collectd
  COLLECTD_PATH = File.join("/", "etc", "collectd")
  SITES_ENABLED_PATH = File.join(COLLECTD_PATH, "sites-enabled")

  CONFIG_EXTENSION = "conf"

  MAIN_CONFIG_FILE = File.join(COLLECTD_PATH, "collectd.#{CONFIG_EXTENSION}")

  def self.stop
    `/etc/init.d/collectd stop`
  end

  def self.restart
    `/etc/init.d/collectd stop`
    `/etc/init.d/collectd start`
  end

  # Creates a config file for the provided app name
  def self.write_app_config(app_name)
    config = <<CONFIG
<Plugin "tail">
  <File "/var/apps/#{app_name}/log/server.log">
    Instance "#{app_name}"
    <Match>
      Regex "APP_STAT .* status [2-4]0[0-9]"
      DSType "CounterInc"
      Type "counter"
      Instance "requests-success"
    </Match>
    <Match>
      Regex "APP_STAT .* status 50[0-9]"
      DSType "CounterInc"
      Type "counter"
      Instance "requests-error"
    </Match>
    <Match>
      Regex "APP_STAT .* time ([0-9.]*)"
      DSType "GaugeAverage"
      Type "delay"
      Instance "requests-response-time"
    </Match>

    Instance "#{app_name}-datastore"
    <Match>
      Regex "DS_STAT .* qtype .*"
      DSType "CounterInc"
      Type "counter"
      Instance "requests"
    </Match>
    <Match>
      Regex "DS_STAT .* qtype RunQuery"
      DSType "CounterInc"
      Type "counter"
      Instance "request-query"
    </Match>
    <Match>
      Regex "DS_STAT .* qtype Get"
      DSType "CounterInc"
      Type "counter"
      Instance "request-get"
    </Match>
    <Match>
      Regex "DS_STAT .* qtype Put"
      DSType "CounterInc"
      Type "counter"
      Instance "request-put"
    </Match>
    <Match>
      Regex "DS_STAT .* qtype Delete"
      DSType "CounterInc"
      Type "counter"
      Instance "request-delete"
    </Match>
    <Match>
      Regex "DS_STAT .* time ([0-9.]*)"
      DSType "GaugeAverage"
      Type "delay"
      Instance "requests-response-time"
    </Match>
    <Match>
      Regex "DS_STAT .* qtype RunQuery time ([0-9.]*)"
      DSType "GaugeAverage"
      Type "delay"
      Instance "requests-response-time-query"
    </Match>
    <Match>
      Regex "DS_STAT .* qtype Get time ([0-9.]*)"
      DSType "GaugeAverage"
      Type "delay"
      Instance "requests-response-time-get"
    </Match>
    <Match>
      Regex "DS_STAT .* qtype Put time ([0-9.]*)"
      DSType "GaugeAverage"
      Type "delay"
      Instance "requests-response-time-put"
    </Match>
    <Match>
      Regex "DS_STAT .* qtype Delete time ([0-9.]*)"
      DSType "GaugeAverage"
      Type "delay"
      Instance "requests-response-time-delete"
    </Match>
  </File>
  <File "/var/log/nginx/#{app_name}.access.log">
    Instance "#{app_name}-nginx"
    <Match>
      Regex " status [2-4]0[0-9] "
      DSType "CounterInc"
      Type "counter"
      Instance "requests-success"
    </Match>
    <Match>
      Regex " status 50[0-9] "
      DSType "CounterInc"
      Type "counter"
      Instance "requests-error"
    </Match>
    <Match>
      Regex " upstream ([0-9.]*) "
      DSType GaugeAverage
      Type delay
      Instance "response-time"
    </Match>
  </File>
</Plugin>
CONFIG

    config_path = File.join(SITES_ENABLED_PATH, "#{app_name}.#{CONFIG_EXTENSION}")
    File.open(config_path, "w+") { |dest_file| dest_file.write(config) }

    Collectd.restart
  end

  def self.remove_app(app_name)
    config_name = "#{app_name}.#{CONFIG_EXTENSION}"
    FileUtils.rm(File.join(SITES_ENABLED_PATH, config_name))
    Collectd.restart
  end

  # Removes all the enabled sites
  def self.clear_sites_enabled
    if File.exists?(SITES_ENABLED_PATH)
      sites = Dir.entries(SITES_ENABLED_PATH)
      # Remove any files that are not configs
      sites.delete_if { |site| !site.end_with?(CONFIG_EXTENSION) }
      full_path_sites = sites.map { |site| File.join(SITES_ENABLED_PATH, site) }
      FileUtils.rm_f full_path_sites

      Collectd.restart
    end
  end

  def self.clear_monitoring_data
    `rm -rf /var/lib/collectd/rrd/`
  end

  # Set up the folder structure and creates the configuration files necessary for collectd
  def self.initialize_config(my_ip, head_node_ip)
    listen_line = ""
    rrdtool_line = ""
    data_plugin = ""
    # The head node will collect all the data, so it needs specific configs
    if my_ip == head_node_ip
      listen_line = "Listen \"#{head_node_ip}\" \"25826\""
      data_plugin = "LoadPlugin rrdtool"
      rrdtool_line = "<Plugin rrdtool>
        DataDir \"/var/lib/collectd/rrd/\"
</Plugin>"
    end

    config = <<CONFIG
FQDNLookup false
Hostname "#{my_ip}"

LoadPlugin syslog
LoadPlugin cpu
#LoadPlugin df
LoadPlugin disk
#LoadPlugin interface
LoadPlugin load
LoadPlugin memcached
LoadPlugin memory
LoadPlugin nginx
LoadPlugin network
LoadPlugin processes
LoadPlugin swap
LoadPlugin tail
# This plugin seems to eat CPU at high load
#LoadPlugin tcpconns
#{data_plugin}

<Plugin syslog>
        LogLevel info
</Plugin>

<Plugin memcached>
        Host "#{my_ip}"
        Port "11211"
</Plugin>

<Plugin "nginx">
        URL "http://#{my_ip}/nginx_status"
</Plugin>

#{rrdtool_line}

#<Plugin tcpconns>
#        ListeningPorts false
#        LocalPort "80"
#        RemotePort "80"
#</Plugin>

<Plugin "network">
  Server "#{head_node_ip}" "25826"
  #{listen_line}
  Forward false
  CacheFlush 1800
</Plugin>

Include "/etc/collectd/sites-enabled/*.conf"
Include "/etc/collectd/thresholds.conf"
CONFIG

    # Create the sites enabled folder
    unless File.exists? SITES_ENABLED_PATH
      FileUtils.mkdir_p SITES_ENABLED_PATH
    end

    # Write the base configuration file which sets default configuration parameters
    File.open(MAIN_CONFIG_FILE, "w+") { |dest_file| dest_file.write(config) }
  end
end
