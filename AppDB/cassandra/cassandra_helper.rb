# Programmer: Navraj Chohan <nlake44@gmail.com>
require 'djinn'
require 'djinn_job_data'
require 'helperfunctions'


# The path on the local filesystem where the Cassandra executable can be found.
CASSANDRA_BIN = "#{APPSCALE_HOME}/AppDB/cassandra/cassandra/bin/cassandra"


# The path on the local filesystem where the nodetool executable can be found.
NODETOOL_BIN = "#{APPSCALE_HOME}/AppDB/cassandra/cassandra/bin/nodetool"


# The file that we should write the process id running Cassandra to.
CASSANDRA_PID_FILE = "/var/appscale/appscale-cassandra.pid"


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

def get_local_token(master_ip, slave_ips)
  # Calculate everyone's token for data partitioning
  if master_ip == HelperFunctions.local_ip
    return 0
  end
    
  slave_ips.each_with_index { |ip, index|
    # Based on local ip return the correct token
    # This token generation was taken from:
    # http://www.datastax.com/docs/0.8/install/cluster_init#cluster-init
    if ip == HelperFunctions.local_ip
      # Add one to offset the master
      return (index + 1) * (2**127)/(1 + slave_ips.length)
    end
  }
end

def setup_db_config_files(master_ip, slave_ips, creds)
  source_dir = "#{APPSCALE_HOME}/AppDB/cassandra/templates"
  dest_dir = "#{APPSCALE_HOME}/AppDB/cassandra/cassandra/conf"

  all_ips = [master_ip, slave_ips].flatten
  local_token = get_local_token(master_ip, slave_ips)

  files_to_config = `ls #{source_dir}`.split
  files_to_config.each { |filename|
    full_path_to_read = File.join(source_dir, filename)
    full_path_to_write = File.join(dest_dir, filename)
    File.open(full_path_to_read) { |source_file|
      contents = source_file.read
      contents.gsub!(/APPSCALE-LOCAL/, HelperFunctions.local_ip)
      contents.gsub!(/APPSCALE-MASTER/, master_ip)
      contents.gsub!(/APPSCALE-TOKEN/, "#{local_token}")
      contents.gsub!(/REPLICATION/, creds["replication"])
      contents.gsub!(/APPSCALE-JMX-PORT/, "7070")              
      File.open(full_path_to_write, "w+") { |dest_file|
        dest_file.write(contents)
      }
    }
  }
  
end
def start_db_master()
  @state = "Starting up Cassandra on the head node"
  Djinn.log_info("Starting up Cassandra as master")

  Djinn.log_run("pkill ThriftBroker")
  if @creds["clear_datastore"]
    Djinn.log_run("rm -rf /var/appscale/cassandra*")
    Djinn.log_run("rm -rf /opt/appscale/cassandra*")
  end
  
  Djinn.log_run("rm /var/log/appscale/cassandra/system.log")
  Djinn.log_run("#{CASSANDRA_BIN} start -p #{CASSANDRA_PID_FILE}")
  HelperFunctions.sleep_until_port_is_open(HelperFunctions.local_ip, 9160)
end

def start_db_slave()
  @state = "Waiting for Cassandra to come up"
  Djinn.log_info("Starting up Cassandra as slave")

  HelperFunctions.sleep_until_port_is_open(Djinn.get_db_master_ip, 9160)
  sleep(5)
  if @creds["clear_datastore"]
    Djinn.log_run("rm -rf /var/appscale/cassandra*")
    Djinn.log_run("rm /var/log/appscale/cassandra/system.log")
  end
  Djinn.log_run("#{CASSANDRA_BIN} start -p #{CASSANDRA_PID_FILE}")
  Djinn.log_run("#{CASSANDRA_BIN} start -p #{CASSANDRA_PID_FILE}")
  HelperFunctions.sleep_until_port_is_open(HelperFunctions.local_ip, 9160)
end

def stop_db_master
  Djinn.log_info("Stopping Cassandra master")
  Djinn.log_run("cat #{CASSANDRA_PID_FILE} | xargs kill -9")
end

def stop_db_slave
  Djinn.log_info("Stopping Cassandra slave")
  Djinn.log_run("cat #{CASSANDRA_PID_FILE} | xargs kill -9")
end
