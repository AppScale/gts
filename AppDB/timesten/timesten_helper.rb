require 'djinn'
require 'djinn_job_data'
require 'helperfunctions'

DB_PORT = 17001

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
  timesten_loc = "#{APPSCALE_HOME}/AppDB/timesten"

  Djinn.log_debug(`mkdir -p /etc/TimesTen`)
  Djinn.log_debug(`/sbin/sysctl -w kernel.shmmax=1000000000`)
#  Djinn.log_debug(`cp #{timesten_loc}/.odbc.ini ~/`)
  Djinn.log_debug(`/opt/TimesTen/tt70/bin/ttAdmin -ramPolicy always "dsn=TT_tt70"`)
end

def start_db_master
#  my_djinn.state = "Starting up TimesTen"
  Djinn.log_debug("Starting up TimesTen as Master")

  Djinn.log_debug(`rm -rf /tmp/m*`)
#  Djinn.log_debug(`pkill python2.6`)
#  Djinn.log_debug(`python2.6 /root/appscale/AppDB/setup_datastore.py -t timesten`)

  uaserver_ip = Djinn.get_db_master_ip

  Kernel.system "/etc/init.d/tt_tt70 start"
  HelperFunctions.sleep_until_port_is_open("localhost", DB_PORT)
end

def stop_db_master
  Djinn.log_debug("Stopping TimesTen as master")
  Djinn.log_debug(`/etc/init.d/tt_tt70 stop`)
#  Djinn.log_debug(`pkill python2.6`)
end

def start_db_slave
  Djinn.log_debug("Starting TimesTen as slave")
  # TODO: setup db replication
end
  
def stop_db_slave
  Djinn.log_debug("Stopping TimesTen as slave")
end
