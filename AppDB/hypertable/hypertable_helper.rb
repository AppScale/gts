require 'djinn'
require 'djinn_job_data'
require 'helperfunctions'
require "#{APPSCALE_HOME}/AppDB/hadoop/hadoop_helper"

HT_VERSION="0.9.5.5"

def get_uaserver_ip()
  Djinn.get_nearest_db_ip
end

def get_db_ports
  [38040, 38050]
end

def has_soap_server?(job)
  return true if job.is_db_master? || job.is_db_slave?
  return false
end

def setup_db_config_files(master_ip, slave_ips)
  setup_hadoop_config(master_ip, @creds["replication"])

  source_dir = "#{APPSCALE_HOME}/AppDB/hypertable/templates"
  dest_dir = "/opt/hypertable/#{HT_VERSION}/conf"

  files_to_config = `ls #{source_dir}`.split
  files_to_config.each do |filename|
    full_path_to_read = File.join(source_dir, filename)
    full_path_to_write = File.join(dest_dir, filename)
    File.open(full_path_to_read) do |source_file|
      contents = source_file.read
      contents.gsub!(/APPSCALE-MASTER/, master_ip)
      contents.gsub!(/REPLICATION/, @creds["replication"])

      if full_path_to_read.include?("Capfile")
        contents.gsub!(/APPSCALE-SLAVES/, (slave_ips + [master_ip]).join("\", \""))
      else
        contents.gsub!(/APPSCALE-SLAVES/, (slave_ips + [master_ip]).join("\n"))
      end
                
      File.open(full_path_to_write, "w+") do |dest_file|
        dest_file.write(contents)
      end
    end
  end
end

def start_db_master()
  @state = "Preparing Hypertable for use on the master"
  Djinn.log_debug("Starting up Hypertable as Master")
  Djinn.log_debug(`rm -rfv /opt/hypertable/#{HT_VERSION}/log/*`)
#  Djinn.log_debug(`pkill python2.6`)
#  Djinn.log_debug(`pkill java`)
  Djinn.log_debug(`pkill ThriftBroker`)

  uaserver_ip = get_uaserver_ip()
  master_ip = Djinn.get_db_master_ip

  # this is needed for Capistrano
  ENV['HOME'] = "/root"
  ENV['USER'] = "root"

  @state = "Starting up Hadoop"
  start_hadoop_master
  # Wait for HDFS
#  wait_on_hadoop

  hadoop_loc = "#{APPSCALE_HOME}/AppDB/hadoop-0.20.2-cdh3u3"

  Djinn.log_debug(`#{hadoop_loc}/bin/hadoop dfs -mkdir /hypertable`)
  Djinn.log_debug(`#{hadoop_loc}/bin/hadoop dfs -chmod 777 /hypertable`)

  @state = "Starting up Hypertable"
  hypertable_loc = "/opt/hypertable/#{HT_VERSION}"
  config_file = "#{hypertable_loc}/conf/hypertable.cfg"
  Djinn.log_debug(`cd #{hypertable_loc}/conf; cap dist`)
  Djinn.log_debug(`cd #{hypertable_loc}/conf; cap cleandb`)
  Djinn.log_debug(`cd #{hypertable_loc}/conf; cap start`)
  # Cap start will start the thrift broker on all nodes
  #Djinn.log_debug(`#{hypertable_loc}/bin/start-thriftbroker.sh --config=#{config_file}`)

  HelperFunctions.sleep_until_port_is_open(Djinn.get_db_master_ip, 38080)
  #Djinn.log_debug(`cd #{hypertable_loc}/bin; sh start-monitoring.sh`)
end

def stop_db_master()
  Djinn.log_debug("Removing temp files for Hypertable on master box, no formal shutdown process yet")
  # need commands to stop hypertable
  hypertable_loc = "/opt/hypertable/#{HT_VERSION}"
  #Djinn.log_debug(`cd #{hypertable_loc}/bin; sh stop-monitoring.sh`)
  Djinn.log_debug(`#{hypertable_loc}/bin/stop-servers.sh`)
  stop_hadoop_master
#  Djinn.log_debug(`rm -rf /tmp/h*`)
end

def start_db_slave()
  hypertable_loc = "/opt/hypertable/#{HT_VERSION}"
  config_file = "#{hypertable_loc}/conf/hypertable.cfg"

  Djinn.log_debug(`rm -rfv /opt/hypertable/#{HT_VERSION}/log/*`)
  start_hadoop_slave

  # like hbase, wait for master's soap server to come up
  # so that we can grab the user/apps schemas
  HelperFunctions.sleep_until_port_is_open(Djinn.get_db_master_ip, 4343)
end

def stop_db_slave()
  Djinn.log_debug("Only need to remove temp files that make up HDFS")
  # need commands to stop hypertable
  hypertable_loc = "/opt/hypertable/#{HT_VERSION}"
  Djinn.log_debug(`#{hypertable_loc}/bin/stop-servers.sh`)
  stop_hadoop_slave
#  Djinn.log_debug(`rm -rf /tmp/h*`)
#  Djinn.log_debug(`pkill python2.6`)
#  Djinn.log_debug(`pkill java`)
end
