require 'djinn'
require 'djinn_job_data'
require 'helperfunctions'

DB_PORT = 3306
MGMD_PORT = 1186

def get_uaserver_ip()
  Djinn.get_nearest_db_ip
end

def get_db_ports
  [1186]
end

def has_soap_server?(job)
  return true if job.is_db_master? || job.is_db_slave?
  return false
end

def setup_db_config_files(master_ip, slave_ips, creds)
  mysql_loc = "#{APPSCALE_HOME}/AppDB/mysql"
  # clear root password
#  `/usr/bin/mysqld_safe --user=root --skip-grant-tables &`
#  `/usr/bin/mysql mysql < #{mysql_loc}/templates/clear-password.sql`
#  `/usr/bin/mysqladmin -u root shutdown`

  # setting up ndb_mgmd.cnf (only for master)
  dest_file = "/etc/mysql/config.ini"
  contents = <<MGMD
[NDBD DEFAULT]
NoOfReplicas=#{creds["replication"]}
DataMemory=256M   # How much memory to allocate for data storage
IndexMemory=256M   # How much memory to allocate for index storage
RedoBuffer=256M

[MYSQLD DEFAULT]
[NDB_MGMD DEFAULT]
#[TCP DEFAULT]

[NDB_MGMD]
# IP address of the management node
hostname=#{master_ip}
[NDBD]
hostname=#{master_ip}
DataDir=/var/appscale/mysql-cluster
BackupDataDir=/var/appscale/mysql-cluster/backup
[MYSQLD]
MGMD
  slave_ips.delete(master_ip)
  slave_ips.each do |slave|
    contents << <<SLAVE
[NDBD]
hostname=#{slave}
DataDir=/var/appscale/mysql-cluster
BackupDataDir=/var/appscale/mysql-cluster/backup
[MYSQLD]
hostname=#{slave}
SLAVE
  end
  File.open(dest_file, "w+") { |file| file.write(contents) }

  # setting up ndb.cnf
  # TODO: we should remove skip-grant-tables for security reason
  dest_file = "/etc/mysql/my.cnf"
  contents = <<NDB
[mysqld]
ndbcluster
set-variable=max_connections=4096
set-variable=thread_cache_size=32
max_allowed_packet=16M
skip-grant-tables
user=root
ndb-connectstring=#{master_ip}
#bind-address=0.0.0.0
#[MYSQL_CLUSTER]
#ndb-connectstring=#{master_ip}
NDB
  File.open(dest_file, "w") { |file| file.write(contents) }
end

def is_priming_needed?(job)
  job.is_db_master? 
end

def start_db_master()
  @state = "Starting up MySQL"
  Djinn.log_debug("Starting MySQL as master")
#  Djinn.log_debug(`python2.6 /root/appscale/AppDB/setup_datastore.py -t mysql`)
  # TODO: this should be more safe way
  Djinn.log_debug(`mkdir -p /var/run/mysqld`)
  Djinn.log_debug(`rm -fv /var/run/mysqld/mysqld.sock`)
  Djinn.log_debug(`rm -rf /var/appscale/mysql-cluster`)
  Djinn.log_debug(`mkdir -p /var/appscale/mysql-cluster/backup`)
  Djinn.log_debug(`ndb_mgmd -f /etc/mysql/config.ini --initial configdir=/etc/mysql &`)
  Djinn.log_debug("Starting ndb connections...")
  Djinn.log_debug(`ndbd -c #{Djinn.get_db_master_ip} &` )
  # wait for start up all ndb servers
  Djinn.log_debug("Waiting on ndb connections...")
  Djinn.log_debug(`/usr/bin/ndb_waiter -t 300`)
  Djinn.log_debug("Starting mysqld")
  Djinn.log_debug(`mkdir -p /var/run/mysqld`)
  Djinn.log_debug(`nohup mysqld --defaults-file=/etc/mysql/my.cnf > /var/log/appscale/mysql.out 2> /var/log/appscale/mysql.err < /dev/null & `)
  
  Djinn.log_debug("Waiting on DB Port")
  HelperFunctions.sleep_until_port_is_open("127.0.0.1", DB_PORT)
  Djinn.log_debug(`mysql -e \"drop database if exists appscale;\"`)
  Djinn.log_debug(`mysql -e \"create database appscale;\"`)
end

def stop_db_master
  Djinn.log_debug(`service mysql stop`)
  Djinn.log_debug(`service mysql-ndb stop`)
  Djinn.log_debug(`service mysql-ndb-mgm stop`)
  # Clear the configuration to enable upgrade of mysql package.
  Djinn.log_debug(`rm -fv /etc/mysql/ndb_mgmd.conf`)
  Djinn.log_debug(`rm -fv /etc/mysql/conf.d/ndb.conf`)
  Djinn.log_debug(`rm -fv /var/run/mysqld/mysqld.sock`)
  Djinn.log_debug(`rm -fv /var/log/appscale/mysql.err`)
  Djinn.log_debug(`rm -fv /var/log/appscale/mysql.out`)
  Djinn.log_debug(`rm -frv /var/appscale/mysql-cluster`)
  Djinn.log_debug(`rm -frv /var/lib/mysql/appscale`)
end

def start_db_slave()
  @state = "Starting up MySQL"
  Djinn.log_debug("Starting MySQL as slave")
  # start ndb server
  Djinn.log_debug(`mkdir -p /var/run/mysqld`)
  Djinn.log_debug(`rm -fv /var/run/mysqld/mysqld.sock`)
  Djinn.log_debug(`rm -rf /var/appscale/mysql-cluster`)
  Djinn.log_debug(`mkdir -p /var/appscale/mysql-cluster/backup`)
  master_ip = Djinn.get_db_master_ip
  HelperFunctions.sleep_until_port_is_open(master_ip, MGMD_PORT)
  Djinn.log_debug(`ndbd -c #{master_ip} &`)

  HelperFunctions.sleep_until_port_is_open(master_ip, DB_PORT)
  # start API node after the master
  Djinn.log_debug(`nohup mysqld --defaults-file=/etc/mysql/my.cnf  > /var/log/appscale/mysql.out 2> /var/log/appscale/mysql.err < /dev/null &`)
  Djinn.log_debug(`mysql -e \"create database appscale;\"`)
end

def stop_db_slave
  Djinn.log_debug(`service mysql stop`)
  Djinn.log_debug(`service mysql-ndb stop`)
  # Clear the configuration to enable upgrade of mysql package.
  Djinn.log_debug(`rm -fv /var/run/mysqld/mysqld.sock`)
  Djinn.log_debug(`rm -fv /etc/mysql/ndb_mgmd.conf`)
  Djinn.log_debug(`rm -fv /etc/mysql/conf.d/ndb.conf`)
  Djinn.log_debug(`rm -fv /var/log/appscale/mysql.err`)
  Djinn.log_debug(`rm -fv /var/log/appscale/mysql.out`)
  Djinn.log_debug(`rm -frv /var/appscale/mysql-cluster`)
  Djinn.log_debug(`rm -frv /var/lib/mysql/appscale`)
end
