require 'djinn'
require 'djinn_job_data'
require 'helperfunctions'

DB_PORT = 6666
VOLDEMORT_LOC = "#{APPSCALE_HOME}/AppDB/voldemort/voldemort"

def get_uaserver_ip()
  Djinn.get_nearest_db_ip
end

def get_db_ports
  [50000, DB_PORT]
end

def has_soap_server?(job)
  return true if job.is_db_master? || job.is_db_slave?
  return false
end

def setup_db_config_files(master_ip, slave_ips, creds)
  return unless my_node.is_db_master? || my_node.is_db_slave?

  voldemort_server_template = "#{APPSCALE_HOME}/AppDB/voldemort/templates/server.properties" 
  voldemort_stores_temp = "#{APPSCALE_HOME}/AppDB/voldemort/templates/stores.xml"
  voldemort_conf_loc = "#{VOLDEMORT_LOC}/config/appscale/config"
  voldemort_stores_loc = "#{voldemort_conf_loc}/stores.xml"
  # clear config folder.
  `rm -rf #{voldemort_conf_loc}`
  `mkdir -p #{voldemort_conf_loc}`
  database_nodes = @nodes.select { |node| node.jobs.include?("db_master") || node.jobs.include?("db_slave") }
  my_db_id = nil
  database_nodes.each_with_index {|node,i| my_db_id = i if node.private_ip == my_node.private_ip }
  if my_db_id.nil?
    db_fail_msg = "FATAL: Unable to get id of current database node!"
    Djinn.log_debug(db_fail_msg)
    abort(db_fail_msg)
  end
  # TODO: this should not use djinn class field.
  setup_cluster_config(voldemort_conf_loc, database_nodes)
  setup_server_config(voldemort_server_template, voldemort_conf_loc, my_db_id)
  r = creds["voldemortr"]
  w = creds["voldemortw"]
  setup_stores_config(voldemort_stores_temp, voldemort_stores_loc, creds["replication"], r, w)
end # setup

def setup_stores_config(template_loc, dest_loc, n, r, w)
  # n = replication factor
  # r = num of nodes necessary for a read to occur
  # w = num of nodes necessary for a write to occur
  contents = (File.open(template_loc) { |f| f.read }).chomp

  contents.gsub!(/REPLICATION/, "#{n}")
  contents.gsub!(/VOLDEMORT-R/, "#{r}")
  contents.gsub!(/VOLDEMORT-W/, "#{w}")

  File.open(dest_loc, "w+") { |dest_file|
    dest_file.write(contents)
  }  
end
  
def setup_cluster_config(dest_dir, database_nodes)
  cluster_file = ""
  start = "<cluster>\n<name>mycluster</name>\n"
    
  middle = ""
  database_nodes.each_index do |index|
    partition = index * 2
    this_part = <<-PART
      <server>
        <id>#{index}</id>
        <host>#{database_nodes[index].private_ip}</host>
        <http-port>50000</http-port>
        <socket-port>#{DB_PORT}</socket-port>
        <partitions>#{partition}, #{partition+1}</partitions>
      </server>
      PART
    middle = middle + this_part
  end
  fin = "</cluster>"
    
  cluster_file = start + middle + fin

  full_path_to_write = File.join(dest_dir, "cluster.xml")
  File.open(full_path_to_write, "w+") do |dest_file|
    dest_file.write(cluster_file)
  end
end

def setup_server_config(source_file, dest_dir, my_index)
  full_path_to_write = File.join(dest_dir, "server.properties")
  File.open(source_file) do |source|
    contents = source.read
    contents.gsub!(/APPSCALE-NODE-ID/, my_index.to_s)

    File.open(full_path_to_write, "w+") { |dest_file| dest_file.write(contents) }
  end
end

def start_db_master()
  @state = "Starting up Voldemort on the head node"
  Djinn.log_debug("Starting up Voldemort as master")
  Djinn.log_debug(`pkill python2.6`)
#  Kernel.system("python2.6 /root/appscale/AppDB/setup_datastore.py -t voldemort")
  `rm -rf #{VOLDEMORT_LOC}/data/*`
  `rm -rf /var/appscale/voldemort`
  `mkdir -p /var/appscale/voldemort`
  Djinn.log_debug(`start-stop-daemon --start --background --exec #{VOLDEMORT_LOC}/bin/voldemort-server.sh -- #{VOLDEMORT_LOC}/config/appscale`)

  my_ip = my_node.private_ip
  @nodes.each { |node|
    next unless node.is_db_slave?
    #HelperFunctions.run_remote_command(node.private_ip, "rm -rf #{VOLDEMORT_LOC}/data/*", @ssh_key, NO_OUTPUT)
    #HelperFunctions.run_remote_command(node.private_ip, "rm -rf /var/appscale/voldemort", @ssh_key, NO_OUTPUT)
    #HelperFunctions.run_remote_command(node.private_ip, "mkdir -p /var/appscale/voldemort", @ssh_key, NO_OUTPUT)
    #HelperFunctions.run_remote_command(node.private_ip, "start-stop-daemon --start --background --exec #{VOLDEMORT_LOC}/bin/voldemort-server.sh -- #{VOLDEMORT_LOC}/config/appscale", @ssh_key, NO_OUTPUT)
    HelperFunctions.sleep_until_port_is_open(node.private_ip, DB_PORT)
    #sleep(1)
  }

  uaserver_ip = get_uaserver_ip

  HelperFunctions.sleep_until_port_is_open("localhost", DB_PORT)
end

def start_db_slave()
  @state = "Waiting for Voldemort to come up"
  Djinn.log_debug("Starting up Voldemort as slave")

#  Kernel.system("python2.6 /root/appscale/AppDB/setup_datastore.py -t voldemort")
  `rm -rf #{VOLDEMORT_LOC}/data/*`
  `rm -rf /var/appscale/voldemort`
  `mkdir -p /var/appscale/voldemort`
  Djinn.log_debug(`start-stop-daemon --start --background --exec #{VOLDEMORT_LOC}/bin/voldemort-server.sh -- #{VOLDEMORT_LOC}/config/appscale`)

  HelperFunctions.sleep_until_port_is_open(Djinn.get_db_master_ip, DB_PORT)
  HelperFunctions.sleep_until_port_is_open(HelperFunctions.local_ip, DB_PORT)
end

def stop_db_master()
  Djinn.log_debug("Stopping Voldemort")
  Djinn.log_debug(`#{VOLDEMORT_LOC}/bin/voldemort-stop.sh`)
#  Djinn.log_debug(`python2.6 #{APPSCALE_HOME}/AppDB/shutdown_datastore.py -t voldemort`)
#  Djinn.log_debug(`pkill python2.6`)
end

def stop_db_slave()
  Djinn.log_debug("Stopping Voldemort")
  Djinn.log_debug(`#{VOLDEMORT_LOC}/bin/voldemort-stop.sh`)
#  Djinn.log_debug(`pkill python2.6`)
end
