# Written by Navyasri Canumalla

#!/usr/bin/env ruby
require 'djinn'
require 'djinn_job_data'
require 'helperfunctions'
if APPSCALE_HOME==""
  APPSCALE_HOME=ENV['APPSCALE_HOME']
end

 Djinn.log_debug("Starting up Redis Helper")

 DB_PORT = 6379

 PATH = "#{APPSCALE_HOME}/AppDB/redisdb/templates/"

 def get_uaserver_ip
  Djinn.get_db_master_ip
 end

 def get_db_ports
  [DB_PORT,6380]
 end

 def has_soap_server?(job)
  return true if job.is_db_master?
  return false
 end

 def setup_db_config_files(master_ip, slave_ips, creds)
 
  # No configuration required for Master. The slaves are configured by passing master_ip and port while starting up slave servers.  

  # source_file = "#{APPSCALE_HOME}/AppDB/redisdb/redis.conf"
  # dest_file = "#{APPSCALE_HOME}/AppDB/redisdb/templates/redis.conf"
 end

 def start_db_master()
  @state = "Starting up Redis"
  Djinn.log_debug("Starting up Redis as Master")
  Djinn.log_debug(`pkill redis-server`)
  Djinn.log_debug(`pkill redis-cli`)
  Djinn.log_debug(`rm -rf /tmp/redis*`)
  Djinn.log_debug(`rm -rf #{PATH}dump.rdb`)
  uaserver_ip = get_uaserver_ip()

  Djinn.log_debug(`/var/appscale/redisdb/src/redis-server #{PATH}redis.conf`)

  # TODO: it is better to wait slave shard servers.
  HelperFunctions.sleep_until_port_is_open("localhost", DB_PORT)

  Djinn.log_debug(`/var/appscale/redisdb/src/redis-cli -h "#{uaserver_ip}" -p 6379 flushdb`)
 end

 def stop_db_master()
  Djinn.log_debug("Stopping Redis as master")
  uaserver_ip = get_uaserver_ip()
  Djinn.log_debug(`rm -rf /tmp/redis*`)
  Djinn.log_debug(`rm -rf #{PATH}dump.rdb`)
  Djinn.log_debug(`/var/appscale/redisdb/src/redis-cli -h "#{uaserver_ip}" -p 6379 flushdb`) 
 
  Djinn.log_debug(`/var/appscale/redisdb/src/redis-cli -h "#{uaserver_ip}" -p 6379 shutdown`)
  
  Djinn.log_debug(`pkill redis-server`)
  Djinn.log_debug(`pkill redis-cli`)
 end

 def start_db_slave()
  uaserver_ip = get_uaserver_ip()
  slave_ips = Djinn.get_db_slave_ips()
  Djinn.log_debug("Starting Redis as slave")
  Djinn.log_debug(`rm -rf /tmp/redis*`)
  Djinn.log_debug(`rm -rf #{PATH}dump.rdb`)
  slave_ips.delete(uaserver_ip)
  slave_ips.each do |slave|
        Djinn.log_debug(`/var/appscale/redisdb/src/redis-server #{PATH}redis.conf`)
	Djinn.log_debug(`/var/appscale/redisdb/src/redis-cli -h "#{slave}" -p 6379 flushdb`)
	
  	Djinn.log_debug(`/var/appscale/redisdb/src/redis-cli -h "#{slave}" -p 6379 slaveof "#{uaserver_ip}" 6379`)
  end
 end

 def stop_db_slave
  Djinn.log_debug("Stopping Redis as slave")
  uaserver_ip = get_uaserver_ip()
  slave_ips = Djinn.get_db_slave_ips()
  slave_ips.delete(uaserver_ip)
  slave_ips.each do |slave|
  	Djinn.log_debug(`/var/appscale/redisdb/src/redis-cli -h "#{slave}" -p 6379 slaveof no one`)
  
	Djinn.log_debug(`/var/appscale/redisdb/src/redis-cli -h "#{slave}" -p 6379 flushdb`)
  end
 end
