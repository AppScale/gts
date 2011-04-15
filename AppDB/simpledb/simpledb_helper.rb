require 'djinn'
require 'djinn_job_data'
require 'helperfunctions'

def get_uaserver_ip()
  Djinn.get_nearest_db_ip
end

def get_db_ports
  [DB_PORT, 31000]
end

def has_soap_server?(job)
  return true if job.is_db_master? || job.is_db_slave?
  return false
end

def setup_db_config_files(master_ip, slave_ips, creds)
  # nothing to do
end

def start_db_master()
  @state = "Starting up SimpleDB"
  Djinn.log_debug("Starting up SimpleDB as Master - just set env vars for prime/py scripts")

  access_key = @creds['SIMPLEDB_ACCESS_KEY']
  secret_key = @creds['SIMPLEDB_SECRET_KEY']

  if access_key.nil? or access_key == ""
    abort("SIMPLEDB_ACCESS_KEY was not set, which is a required value.")
  end

  if secret_key.nil? or secret_key == ""
    abort("SIMPLEDB_SECRET_KEY was not set, which is a required value.")
  end

  ENV['SIMPLEDB_ACCESS_KEY'] = access_key
  ENV['SIMPLEDB_SECRET_KEY'] = secret_key
end

def stop_db_master
  Djinn.log_debug("Stopping SimpleDB as master")
  `python2.6 #{APPSCALE_HOME}/AppDB/simpledb/shutdown_simpledb.py`
end

def start_db_slave()
  Djinn.log_debug("Starting SimpleDB as slave - hosted remotely, so do nothing")

  access_key = @creds['SIMPLEDB_ACCESS_KEY']
  secret_key = @creds['SIMPLEDB_SECRET_KEY']

  if access_key.nil? or access_key == ""
    abort("SIMPLEDB_ACCESS_KEY was not set, which is a required value.")
  end

  if secret_key.nil? or secret_key == ""
    abort("SIMPLEDB_SECRET_KEY was not set, which is a required value.")
  end

  ENV['SIMPLEDB_ACCESS_KEY'] = access_key
  ENV['SIMPLEDB_SECRET_KEY'] = secret_key
end

def stop_db_slave
  Djinn.log_debug("Stopping SimpleDB as slave")
end

def backup_db
  fail # definitely not implemented yet
end

def restore_db_from_tar
  fail
end

def restore_db_from_ebs(ebs_location)
  fail
end
