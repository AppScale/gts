require 'djinn'
require 'djinn_job_data'
require 'helperfunctions'

def get_uaserver_ip()
  Djinn.get_nearest_db_ip
end

def get_db_ports
  [7000, 7001, 9160, 7002]
end

def has_soap_server?(job)
  return true if job.is_db_master? || job.is_db_slave?
  return false
end

def setup_db_config_files(master_ip, slave_ips, creds)
  source_dir = "#{APPSCALE_HOME}/AppDB/cassandra/templates"
  dest_dir = "#{APPSCALE_HOME}/AppDB/cassandra/cassandra/conf"

  all_ips = [master_ip, slave_ips].flatten

  files_to_config = `ls #{source_dir}`.split
  files_to_config.each{ |filename|
    full_path_to_read = File.join(source_dir, filename)
    full_path_to_write = File.join(dest_dir, filename)
    File.open(full_path_to_read) { |source_file|
      contents = source_file.read
      contents.gsub!(/APPSCALE-LOCAL/, HelperFunctions.local_ip)
      contents.gsub!(/APPSCALE-MASTER/, master_ip)
      contents.gsub!(/REPLICATION/, creds["replication"])
                
      File.open(full_path_to_write, "w+") { |dest_file|
        dest_file.write(contents)
      }
    }
  }
end

def start_db_master()
  @state = "Starting up Cassandra on the head node"
  Djinn.log_debug("Starting up Cassandra as master")

  Djinn.log_debug(`pkill ThriftBroker`)
  `rm -rf /var/appscale/cassandra*`

  Djinn.log_debug(`#{APPSCALE_HOME}/AppDB/cassandra/cassandra/bin/cassandra start -p /var/appscale/appscale-cassandra.pid`)
  HelperFunctions.sleep_until_port_is_open(HelperFunctions.local_ip, 9160)
end

def start_db_slave()
  @state = "Waiting for Cassandra to come up"
  Djinn.log_debug("Starting up Cassandra as slave")

  HelperFunctions.sleep_until_port_is_open(Djinn.get_db_master_ip, 9160)
    
  `rm -rf /var/appscale/cassandra*`
  Djinn.log_debug(`#{APPSCALE_HOME}/AppDB/cassandra/cassandra/bin/cassandra start -p /var/appscale/appscale-cassandra.pid`)
  HelperFunctions.sleep_until_port_is_open(HelperFunctions.local_ip, 9160)
end

def stop_db_master
  Djinn.log_debug("Stopping Cassandra master")
  Djinn.log_run("cat /var/appscale/appscale-cassandra.pid | xargs kill -9")
end

def stop_db_slave
  Djinn.log_debug("Stopping Cassandra slave")
  Djinn.log_run("#{APPSCALE_HOME}/AppDB/cassandra/cassandra/bin/nodetool decommission -h #{HelperFunctions.local_ip} -p 6666")
  Djinn.log_run("cat /var/appscale/appscale-cassandra.pid | xargs kill -9")
end
