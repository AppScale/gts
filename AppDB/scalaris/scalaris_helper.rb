require 'djinn'
require 'djinn_job_data'
require 'helperfunctions'

DB_PORT = 9001

def get_uaserver_ip()
  Djinn.get_db_master_ip
end

def get_db_ports
  [DB_PORT]
end

def has_soap_server?(job)
  return true if job.is_db_master?
  return false
end

def setup_db_config_files(master_ip, slave_ips, creds)
  source_file = "#{APPSCALE_HOME}/AppDB/scalaris/templates/scalaris.local.cfg"
  dest_file = "/etc/scalaris/scalaris.local.cfg"
  master_ip_comma = master_ip.gsub(/\./, ",")
  File.open(source_file) do |source|
    contents = source.read
    contents.gsub!(/MASTER_IP_ADDRESS/, master_ip_comma)
    File.open(dest_file, "w+") do |dest|
      dest.write(contents)
    end
  end
end

def start_db_master
#  my_djinn.state = "Starting up Scalaris on the head node"
  Djinn.log_debug("Starting up Scalaris as master")
  #Djinn.log_debug(`pkill beam`)
  #Djinn.log_debug(`pkill epmd`)
  Kernel.system("HOME='/root' /usr/bin/scalarisctl boot start")

  uaserver_ip = HelperFunctions.local_ip

  HelperFunctions.sleep_until_port_is_open("localhost", DB_PORT)
end

def start_db_slave
  Djinn.log_debug("Starting up Scalaris as slave")
  #Djinn.log_debug(`pkill beam`)
  #Djinn.log_debug(`pkill epmd`)
  HelperFunctions.sleep_until_port_is_open(Djinn.get_db_master_ip, DB_PORT)

  Kernel.system("HOME='/root' /usr/bin/scalarisctl node start")
end

def stop_db_master
  Djinn.log_debug("Stopping Scalaris")
  Djinn.log_debug(`HOME='/root' /usr/bin/scalarisctl boot stop`)
  Djinn.log_debug(`pkill beam`)
  Djinn.log_debug(`pkill epmd`)
end

def stop_db_slave
  Djinn.log_debug("Stopping Scalaris")
  Djinn.log_run("HOME='/root' /usr/bin/scalarisctl node stop")
  #Djinn.log_run(`pkill beam`)
  #Djinn.log_run(`pkill epmd`)
end
