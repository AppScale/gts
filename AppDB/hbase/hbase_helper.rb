require 'djinn'
require 'djinn_job_data'
require 'helperfunctions'
require "#{APPSCALE_HOME}/AppDB/hadoop/hadoop_helper"

HBASE_LOC = "#{APPSCALE_HOME}/AppDB/hbase/hbase-0.90.4-cdh3u3"
THRIFT_PORT = 9090
MASTER_SERVER_PORT = 60000
ENABLE_SINGLE_NODE = true

def get_uaserver_ip()
  Djinn.get_nearest_db_ip
end

def get_db_ports
  [60000, 60020]
end

def has_soap_server?(job)
  return true if job.is_db_master? || job.is_db_slave?
  return false
end

def setup_db_config_files(master_ip, slave_ips, creds)
  setup_hadoop_config(master_ip, creds["replication"])

  source_dir = "#{APPSCALE_HOME}/AppDB/hbase/templates"
  dest_dir = File.join(HBASE_LOC, "conf")

  # We must remove zoo.cfg to enable hbase-site.xml configurations.
  Djinn.log_debug(`rm -fv #{dest_dir}/zoo.cfg`)
  Djinn.log_debug(`rm -fv #{dest_dir}/hbase-site.xml`)

  # Generate Quorum setting
  zkips = []
  @nodes.each { |node|
    zkips.push(node.private_ip) if node.is_zookeeper?
  }
  zkconnect = zkips.join(",")

  files_to_config = `ls #{source_dir}`.split
  files_to_config.each { |filename|
    full_path_to_read = File.join(source_dir, filename)
    full_path_to_write = File.join(dest_dir, filename)
    File.open(full_path_to_read) { |source_file|
      contents = source_file.read
      contents.gsub!(/APPSCALE-MASTER/, master_ip)
      contents.gsub!(/APPSCALE-SLAVES/, slave_ips.join("\n"))
      contents.gsub!(/REPLICATION/, creds["replication"])
      contents.gsub!(/APPSCALE-ZOOKEEPER/, zkconnect)

      File.open(full_path_to_write, "w+") { |f| f.write(contents) }
    }
  }
end

def start_db_master()
  @state = "Starting up HBase"
  Djinn.log_debug("Starting up HBase as Master")
  Djinn.log_run("pkill ThriftBroker")
  Djinn.log_run("rm -rfv #{APPSCALE_HOME}/AppDB/hbase/hbase-0.20.6/logs/*")

  start_hadoop_master
  wait_on_hadoop
  Djinn.log_run("cp #{APPSCALE_HOME}/AppDB/hbase/patch/cache_classpath.txt #{HBASE_LOC}/target/")
  Djinn.log_run("#{HBASE_LOC}/bin/hbase-daemon.sh start master")
  until `lsof -i :#{MASTER_SERVER_PORT} -t`.length > 0
    Djinn.log_debug("Waiting for HBase master to come up...")
    sleep(5)
  end
  if ENABLE_SINGLE_NODE
    Djinn.log_run("#{HBASE_LOC}/bin/hbase-daemon.sh start regionserver")
  end
  # wait for at least one region server.
  status_cmd = "#{APPSCALE_HOME}/AppDB/hbase/hbase-status.sh"
  until `#{status_cmd}`.to_i > 0
    Djinn.log_debug("waiting for hbase region server coming up")
    sleep(5)
  end
  Djinn.log_run("#{HBASE_LOC}/bin/hbase-daemon.sh start thrift")

  until `lsof -i :#{THRIFT_PORT} -t`.length > 0
    Djinn.log_debug("Waiting for Thrift server to come up...")
    sleep(5)
  end
end

def stop_db_master()
  # TODO: we must stop only soap server and appscale server.
  Djinn.log_debug("Stopping HBase as master")
  Djinn.log_run("#{HBASE_LOC}/bin/hbase-daemon.sh stop thrift")
  if ENABLE_SINGLE_NODE
    Djinn.log_run("#{HBASE_LOC}/bin/hbase-daemon.sh stop regionserver")
  end
  Djinn.log_run("#{HBASE_LOC}/bin/hbase-daemon.sh stop master")
  stop_hadoop_master
end

def start_db_slave()
  Djinn.log_debug("Starting HBase as slave")
  Djinn.log_run("rm -rfv #{APPSCALE_HOME}/AppDB/hbase/hbase-0.20.6/logs/*")
  start_hadoop_slave
  Djinn.log_run("#{HBASE_LOC}/bin/hbase-daemon.sh start regionserver")
  # need to wait for the master's soap server to come up
  # or we won't be able to get the user/apps schemas
  HelperFunctions.sleep_until_port_is_open(Djinn.get_db_master_ip, 4343)  
  Djinn.log_run("#{HBASE_LOC}/bin/hbase-daemon.sh start thrift")
end

def stop_db_slave()
  Djinn.log_debug("Stopping HBase as slave")
  Djinn.log_run("#{HBASE_LOC}/bin/hbase-daemon.sh stop thrift")
  Djinn.log_run("#{HBASE_LOC}/bin/hbase-daemon.sh stop regionserver")
  stop_hadoop_slave
end
