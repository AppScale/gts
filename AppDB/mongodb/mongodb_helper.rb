require 'djinn'
require 'djinn_job_data'
require 'helperfunctions'

DB_PORT = 27017

def get_uaserver_ip()
  Djinn.get_db_master_ip
end

def get_db_ports
  [DB_PORT, 28017]
end

def has_soap_server?(job)
  return true if job.is_db_master?
  return false
end

def setup_db_config_files(master_ip, slave_ips, creds)
  # configure shards
  dest_file = "#{APPSCALE_HOME}/.appscale/mongo-shards.js"
  contents = <<MASTER
db.runCommand({addshard:"#{master_ip}:27020"});
MASTER
  slave_ips.delete(master_ip)
  slave_ips.each do |slave|
    contents << <<SLAVE
db.runCommand({addshard:"#{slave}:27020"});
SLAVE
  end
  File.open(dest_file, "w+") { |file| file.write(contents) }
end

def start_db_master()
  @state = "Starting up MongoDB"
  Djinn.log_debug("Starting up MongoDB as Master")
#  Djinn.log_debug(`pkill python2.6`)
  Djinn.log_debug(`pkill mongod`)
  Djinn.log_debug(`pkill mongos`)
  Djinn.log_debug(`rm -rf /tmp/m*`)
  Djinn.log_debug(`rm -rf /var/appscale/mongodb`)

  uaserver_ip = get_uaserver_ip()

  Djinn.log_debug(`mkdir -p /var/appscale/mongodb/shard`)
  Djinn.log_debug(`mkdir -p /var/appscale/mongodb/config`)

#  Kernel.system "/root/appscale/AppDB/mongodb/mongodb-linux-x86_64-1.0.0/bin/mongod --dbpath /tmp &"
  # start config server
  Djinn.log_debug(`start-stop-daemon --start --background --make-pidfile --pidfile /var/appscale/mongodb-config.pid --exec /usr/bin/mongod -- --configsvr --dbpath /var/appscale/mongodb/config --port 27018`)
  # start shard server
  Djinn.log_debug(`start-stop-daemon --start --background --make-pidfile --pidfile /var/appscale/mongodb-shard.pid --exec /usr/bin/mongod -- --shardsvr --dbpath /var/appscale/mongodb/shard --port 27020`)
  # start routing server
  HelperFunctions.sleep_until_port_is_open("localhost", 27018)
  Djinn.log_debug(`start-stop-daemon --start --background --make-pidfile --pidfile /var/appscale/mongodb-routing.pid --exec /usr/bin/mongos -- --port #{DB_PORT} --configdb localhost:27018`)

  # configure shards
  # TODO: it is better to wait slave shard servers.
  HelperFunctions.sleep_until_port_is_open("localhost", DB_PORT)
  HelperFunctions.sleep_until_port_is_open("localhost", 27020)
  dest_file = "#{APPSCALE_HOME}/.appscale/mongo-shards.js"
  Djinn.log_debug(`/usr/bin/mongo localhost:27017/admin #{dest_file}`)
end

def stop_db_master
  Djinn.log_debug("Stopping MongoDB as master")
#  Djinn.log_debug(`python2.6 #{APPSCALE_HOME}/AppDB/shutdown_datastore.py -t mongodb`)
  Djinn.log_debug(`rm -rf /tmp/m*`)
#  Djinn.log_debug(`pkill python2.6`)
  Djinn.log_debug(`pkill mongod`)
  Djinn.log_debug(`pkill mongos`)
end

def start_db_slave()
  Djinn.log_debug("Starting MongoDB as slave")
  Djinn.log_debug(`rm -rf /tmp/m*`)
  Djinn.log_debug(`rm -rf /var/appscale/mongodb`)

  Djinn.log_debug(`mkdir -p /var/appscale/mongodb/shard`)

  # Wait for the master to come up
#  uaserver_ip = get_uaserver_ip()
#  HelperFunctions.sleep_until_port_is_open(uaserver_ip, 27017)

#  Kernel.system "screen -d -m /root/appscale/AppDB/mongodb/mongodb-linux-x86_64-1.0.0/bin/mongo #{uaserver_ip}"
  # start shard server
  Djinn.log_debug(`/usr/bin/mongod --shardsvr --dbpath /var/appscale/mongodb/shard --port 27020 --fork --logpath /var/appscale/mongodb/mongo-shard.log`)
end

def stop_db_slave
  Djinn.log_debug("does nothing right now, need to find where mongo stores data")
  Djinn.log_debug(`pkill mongod`)
  Djinn.log_debug(`pkill mongos`)
end

