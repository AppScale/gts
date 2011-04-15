#!/usr/bin/ruby -w

# see if still using socket lib

require 'monitor'
require 'openssl'
require 'socket'
require 'soap/rpc/driver'
require 'syslog'
require 'yaml'

require 'rubygems'
require 'right_aws'
require 'zookeeper'

$:.unshift File.join(File.dirname(__FILE__))
require 'djinn_job_data'
require 'helperfunctions'
require 'cron_helper'
require 'haproxy'
require 'collectd'
require 'nginx'
require 'pbserver'
require 'blobstore'
require 'app_controller_client'
require 'user_app_client'
require 'ejabberd'
require 'repo'
require 'zkinterface'

$VERBOSE = nil # to supress excessive SSL cert warnings
APPSCALE_HOME = ENV['APPSCALE_HOME']

FIREWALL_IS_ON = false

WANT_OUTPUT = true
NO_OUTPUT = false

require "#{APPSCALE_HOME}/AppDB/zkappscale/zookeeper_helper"
require "#{APPSCALE_HOME}/Neptune/neptune"

class Exception
  alias real_init initialize
  def initialize(*args)
    real_init *args

    File.open("#{APPSCALE_HOME}/.appscale/exception.log", "w+") { |file| 
      file.write(message) 
    }

    begin
      #Syslog.open("appscale") { |s| s.debug(message) }
      puts message
    rescue RuntimeError
      # this can occur if we write to syslog at the same time
      # as one of the python components
    end
  end

  alias real_set_backtrace set_backtrace
  
  def set_backtrace(*args)
    real_set_backtrace *args
    
    # Only print the last line of the backtrace so the logs arent polluted
    bt = self.backtrace #.last # cgb: need full trace for the moment
    output = "#{self.class}: #{self.message} #{bt}"

    File.open("#{APPSCALE_HOME}/.appscale/exception-full.log", "w+") { |file| 
      file.write(output) 
    }

    begin
      #Syslog.open("appscale") { |s| s.debug(output) }
    rescue RuntimeError
    end   
  end
end

BAD_SECRET_MSG = "false: bad secret"
DJINN_SERVER_PORT = 17443
UA_SERVER_PORT = 4343
SSH_PORT = 22
USE_SSL = true
NEPTUNE_INFO = "/etc/appscale/neptune_info.txt"

class Djinn
  attr_accessor :job, :nodes, :creds, :app_names, :done_loading 
  attr_accessor :port, :apps_loaded, :userappserver_public_ip 
  attr_accessor :userappserver_private_ip, :state, :kill_sig_received 
  attr_accessor :my_index, :total_boxes, :num_appengines, :restored
  attr_accessor :neptune_jobs, :neptune_nodes

  public

  def done(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return @done_loading  
  end

  def kill(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    @kill_sig_received = true
    
    if is_hybrid_cloud? 
      Thread.new {
        sleep(5)
        HelperFunctions.terminate_hybrid_vms(creds)
      }
    elsif is_cloud?
      Thread.new {
        sleep(5)
        infrastructure = creds["infrastructure"]
        keyname = creds["keyname"]
        HelperFunctions.terminate_all_vms(infrastructure, keyname)
      }
    else
      # in xen/kvm deployments we actually want to keep the boxes
      # turned on since that was the state they started in

      stop_memcached
      stop_ejabberd if my_node.is_login?
      Repo.stop if my_node.is_shadow?

      jobs_to_run = my_node.jobs
      commands = {
        "load_balancer" => "stop_load_balancer",
        "appengine" => "stop_appengine",
        "db_master" => "stop_db_master",
        "db_slave" => "stop_db_slave",
        "zookeeper" => "stop_zookeeper"
      }

      my_node.jobs.each do |job|
        if commands.include?(job)
          Djinn.log_debug("About to run [#{commands[job]}]")
          send(commands[job].to_sym)
        else
          Djinn.log_debug("Unable to find command for job #{job}. Skipping it.")
        end
      end


      if has_soap_server?(my_node)
        stop_soap_server
        stop_pbserver
      end
    end

    return "OK"  
  end
 
  def set_parameters(djinn_locations, database_credentials, app_names, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    Djinn.log_debug("Djinn locations class: #{djinn_locations.class}")
    Djinn.log_debug("DB Credentials class: #{database_credentials.class}")
    Djinn.log_debug("Apps to load class: #{app_names.class}")

    #Djinn.log_debug("Djinn locations: #{djinn_locations.join(', ')}")
    #Djinn.log_debug("DB Credentials: #{HelperFunctions.obscure_creds(database_credentials).inspect}")
    #Djinn.log_debug("Apps to load: #{app_names.join(', ')}")

    ["djinn_locations", "database_credentials", "app_names"].each { |param_name|
      param = eval(param_name)
      if param.class != Array
        Djinn.log_debug "#{param_name} wasn't an Array. It was a/an #{param.class}"
        return "Error: #{param_name} wasn't an Array. It was a/an #{param.class}"
      end
    }

    # credentials is an array that we're converting to
    # hash tables, so we need to make sure that every key maps to a value
    # e.g., ['foo', 'bar'] becomes {'foo' => 'bar'}
    # so we need to make sure that the array has an even number of elements
        
    if database_credentials.length % 2 != 0
      error_msg = "Error: DB Credentials wasn't of even length: Len = " + \
        "#{database_credentials.length}"
      Djinn.log_debug(error_msg)
      return error_msg
    end
  
    possible_credentials = Hash[*database_credentials]
    if !valid_format_for_credentials(possible_credentials)
      return "Error: Credential format wrong"
    end

    Djinn.log_debug("parameters were valid")

    keyname = possible_credentials["keyname"]
    @nodes = Djinn.convert_location_array_to_class(djinn_locations, keyname)
    @creds = possible_credentials
    @app_names = app_names
    
    convert_fqdns_to_ips
    @creds = sanitize_credentials

    Djinn.log_debug("Djinn locations: #{@nodes.join(', ')}")
    Djinn.log_debug("DB Credentials: #{HelperFunctions.obscure_creds(@creds).inspect}")
    Djinn.log_debug("Apps to load: #{@app_names.join(', ')}")

    find_me_in_locations
    if @my_index == nil
      return "Error: Couldn't find me in the node map"
    end
    Djinn.log_debug("My index = #{@my_index}")
    

    # no longer a need to set it in bashrc since it won't take effect
    # since the program is already running
    
    ENV['EC2_URL'] = @creds['ec2_url']
    
    #change_job(@@secret)  
    return "OK"
  end

  def set_apps(app_names, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    @app_names = app_names
    return "app names is now #{@app_names.join(', ')}"
  end
 
  def status(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    
    usage = HelperFunctions.get_usage
    mem = sprintf("%3.2f", usage['mem'])

    job = my_node.jobs
    if job.nil?
      job = "none"
    else
      job = job.join(', ')
    end

    # don't use an actual % below, or it will cause a string format exception
    stats = <<-STATUS
    Currently using #{usage['cpu']} Percent CPU and #{mem} Percent Memory
    Hard disk is #{usage['disk']} Percent full
    Is currently: #{job}
    Database is at #{@userappserver_public_ip}
    Is in cloud: #{my_node.cloud}
    Current State: #{@state}
    STATUS

    if my_node.is_appengine?
      stats << "    Hosting the following apps: #{@app_names.join(', ')}"
    end
 
    return stats
  end

  def stop_app(app_name, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    app_name.gsub!(/[^\w\d\-]/, "")
    Djinn.log_debug("Shutting down app named [#{app_name}]")
    result = ""
    
    if @app_names.include?(app_name) and !my_node.is_appengine?
      @nodes.each { |node|
        if node.is_appengine? or node.is_login?
          ip = node.private_ip
          acc = AppControllerClient.new(ip, @@secret)
          result = acc.stop_app(app_name)
          Djinn.log_debug("#{ip} returned #{result} (#{result.class})")
        end
      }
    end

    if (@app_names.include?(app_name) and !my_node.is_appengine?) or @nodes.length == 1
      ip = HelperFunctions.read_file("#{APPSCALE_HOME}/.appscale/masters")
      uac = UserAppClient.new(ip, @@secret)
      result = uac.delete_app(app_name)
      Djinn.log_debug("delete app: #{ip} returned #{result} (#{result.class})")
    end

    if my_node.is_login? # may need to stop XMPP listener
      pid_files = `ls #{APPSCALE_HOME}/.appscale/xmpp-#{app_name}.pid`.split
      unless pid_files.length.zero? # not an error here - XMPP is optional
        pid_files.each { |pid_file|
          pid = HelperFunctions.read_file(pid_file)
          `kill -9 #{pid}`
        }

        result = "true"
      end
    end    

    if my_node.is_appengine?
      pid_files = `ls #{APPSCALE_HOME}/.appscale/#{app_name}*`.split
      return "Error: App not running" if pid_files.length.zero?
      pid_files.each { |pid_file|
        pid = HelperFunctions.read_file(pid_file)
        Djinn.log_debug("killing appserver for #{app_name} with pid #{pid}")
        `kill -9 #{pid}`
      }

      Nginx.remove_app(app_name)
      Collectd.remove_app(app_name)
      HAProxy.remove_app(app_name)
      Nginx.reload
      Collectd.restart
      ZKInterface.remove_app_entry(app_name)

      result = "true"
    end

    @apps_loaded = @apps_loaded - [app_name]    
    @app_names = @app_names - [app_name]

    if @apps_loaded.empty?
      @apps_loaded << "none"
    end

    if @app_names.empty?
      @app_names << "none"
    end

    return result
  end

  def update(app_names, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    
    apps = @app_names - app_names + app_names
    
    @nodes.each_index { |index|
      ip = @nodes[index].private_ip
      acc = AppControllerClient.new(ip, @@secret)
      result = acc.set_apps(apps)
      Djinn.log_debug("#{ip} returned #{result} (#{result.class})")
      @everyone_else_is_done = false if !result
    }

    # now that another app is running we can take out 'none' from the list
    # if it was there (e.g., run-instances with no app given)
    @app_names = @app_names - ["none"]
    
    return "OK"
  end

  def get_all_public_ips(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    public_ips = []
    @nodes.each { |node|
      public_ips << node.public_ip
    }
    return public_ips
  end

  def job_start(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    wait_for_data
    change_job(secret)
    
    while !@kill_sig_received do
      @state = "Done starting up AppScale, now in heartbeat mode"
      write_database_info
      write_neptune_info     

      #ensure_critical_services_are_running

      `mkdir -p #{APPSCALE_HOME}/.appscale/logs/`
      if my_node.is_shadow?
        @nodes.each { |node|
          get_status(node)
          `cp /tmp/*.log #{APPSCALE_HOME}/.appscale/logs/`

          if node.should_destroy?
            Djinn.log_debug("heartbeat - destroying node [#{node}]")
            @nodes.delete(node)
            @neptune_nodes.delete(node)
            infrastructure = @creds["infrastructure"]
            HelperFunctions.terminate_vms([node], infrastructure)
            Djinn.log_run("rm -v /etc/appscale/status-#{node.private_ip}.log")
          end
        }
        Djinn.log_debug("Finished contacting all other nodes")

        @neptune_nodes.each { |node|
          Djinn.log_debug("Currently examining node [#{node}]")
          if node.should_extend?
            Djinn.log_debug("extending time for node [#{node}]")
            node.extend_time
          elsif node.should_destroy?
            Djinn.log_debug("time is up for node [#{node}] - destroying it")
            @nodes.delete(node)
            @neptune_nodes.delete(node)
            infrastructure = @creds["infrastructure"]
            HelperFunctions.terminate_vms([node], infrastructure)
            Djinn.log_run("rm -v /etc/appscale/status-#{node.private_ip}.log")
          end
        }
      else
        Djinn.log_debug("No need to heartbeat, we aren't the shadow")
      end

      # TODO: consider only calling this if new apps are found
      start_appengine if my_node.is_appengine?
      sleep(20)
    end
  end

  def ensure_critical_services_are_running
    # TODO: clean this up
    # verify we're starting all services correctly

    if !is_running?("ejabberd") and (my_node.is_login?)
      Djinn.log_debug("ejabberd was not running - restarting it now")
      start_ejabberd
    end

    if !is_running?("/usr/bin/memcached") and (my_node.is_load_balancer? or my_node.is_appengine?)
      Djinn.log_debug("memcached was not running - restarting it now")
      start_memcached
    end

    if !is_running?("appscale_server") and (has_soap_server?(my_node))
      Djinn.log_debug("pbserver was not running - restarting it now")
      start_pbserver
    end

    if !is_running?("soap_server.py") and (has_soap_server?(my_node))
      Djinn.log_debug("soap was not running - restarting it now")
      start_soap_server
    end

    if !is_running?("blobstore_server.py") and (my_node.is_appengine?)
      Djinn.log_debug("blobserver was not running - restarting it now")
      start_blobstore_server
    end

    Nginx.restart unless Nginx.is_running?
    HAProxy.restart unless HAProxy.is_running?
  end

  def get_online_users_list(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    online_users = []

    login_node = get_login
    ip = login_node.public_ip
    key = login_node.ssh_key
    raw_list = `ssh -i #{key} -o StrictHostkeyChecking=no root@#{ip} 'ejabberdctl connected-users'`
    raw_list.split("\n").each { |userdata|
      online_users << userdata.split("/")[0]
    }

    return online_users
  end

  def done_uploading(appname, location, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    if File.exists?(location)
      ZKInterface.add_app_entry(appname, my_node.serialize, location)
      result = "success"
    else
      result = "The #{appname} app was not found at #{location}."
    end

    Djinn.log_debug(result)
    return result
  end

  def is_app_running(appname, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    hosters = ZKInterface.get_app_hosters(appname)
    hosters_w_appengine = []
    hosters.each { |node|
      hosters_w_appengine << node if node.is_appengine?
    }

    app_running = !hosters_w_appengine.empty?
    Djinn.log_debug("Is app #{appname} running? #{app_running}")
    return app_running
  end

  def backup_appscale(backup_info, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    Djinn.log_debug("Got a backup request with info: #{backup_info.join(', ')}")

    # TODO: FIXME
    #unless backup_info["ebs_location"].nil? && backup_info["tar_location"].nil?
    #  Djinn.log_debug("failed the first test")
    #  return "Please specify backing up to either EBS or to a tar file."
    #end
 
    Djinn.log_debug("Passed the first test")

    if backup_info[0] == "ebs_location"
      return "Backing up to EBS not yet supported."
    end

    if backup_info[0] == "tar_location"
      # right now we only backup the db contents
      # TODO: what else should be backed up?

      uac = UserAppClient.new(@userappserver_private_ip, @@secret)      
      all_apps = uac.get_all_apps()

      Djinn.log_debug("all apps are [#{all_apps}]")
      app_list = all_apps.split(":")
      app_list = app_list - [app_list[0]] # first item is a dummy value, ____
      app_list.each { |app|
        app_is_enabled = uac.does_app_exist?(app)
        Djinn.log_debug("[backup] is app #{app} enabled? #{app_is_enabled}")
        if app_is_enabled == "true"
          app_data = uac.get_app_data(app)
          Djinn.log_debug("[backup] app data for #{app} is [#{app_data}]")
          hosts = app_data.scan(/\nhosts:([\d\.|:]+)\n/).flatten.to_s.split(":")
          ports = app_data.scan(/\nports: ([\d|:]+)\n/).flatten.to_s.split(":")
          # TODO : make sure that len hosts = len ports
          hosts.each_index { |i|
            Djinn.log_debug("deleting instance for app #{app} at #{hosts[i]}:#{ports[i]}")
            uac.delete_instance(app, hosts[i], ports[i]) 
          }
          Djinn.log_debug("finished deleting instances for app #{app}")
        else
          Djinn.log_debug("app #{app} wasnt enabled, skipping it")
        end
      }

      ip = nil
      ssh_key = nil

      @nodes.each { |node|
        next unless node.is_db_master?
        ip = node.public_ip
        ssh_key = node.ssh_key
      }

      acc = AppControllerClient.new(ip, @@secret)
      Djinn.log_debug("About to call on #{ip}")
      result = acc.backup_database_state(backup_info)
      Djinn.log_debug("hey #{ip} said [#{ip}]")
      if result == "failed"
        return "Database backup failed. Please contact a cloud administrator."
      end

      # backup_state returns the location of the tar'ed db
      HelperFunctions.scp_file(result, result, ip, ssh_key)

      return "DB Backup created at #{result}"
    end
  end

  def backup_database_state(backup_info, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    #unless backup_info["ebs_location"].nil? && backup_info["tar_location"].nil?
    #  Djinn.log_debug("Failed second test: Please specify backing up to either EBS or to a tar file.")
    #  return "failed"
    #end
    Djinn.log_debug("passed the second test")

    if backup_info[0] == "ebs_location"
      Djinn.log_debug("Backing up to EBS not yet supported.")
      return "failed"
    end

    if backup_info[0] == "tar_location"
      Djinn.log_debug("i think it's a tar")
      db_backup_tar = backup_db()
      Djinn.log_debug("Backed up database to #{db_backup_tar}")
      return db_backup_tar
    end

    Djinn.log_debug("we have a problem - its not a tar nor ebs")
  end

  def add_role(new_role, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    my_node.add_roles(new_role)
    start_roles = new_role.split(":")
    start_roles.each { |role|
      send("start_#{role}".to_sym)
    }
    return "OK"
  end

  def remove_role(old_role, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    my_node.remove_roles(old_role)
    stop_roles = old_role.split(":")
    stop_roles.each { |role|
      send("stop_#{role}".to_sym)
    }
    return "OK"
  end

  private

  def self.log_debug(msg)
      # TODO: reduce the copypasta here
      puts "[#{Time.now}] #{msg}"
      STDOUT.flush # TODO: examine performance impact of this
      if @lock.nil?
      begin
        Syslog.open("appscale") { |s| s.debug(msg) }
      rescue RuntimeError
      end
      else
      @lock.synchronize {
      begin
        Syslog.open("appscale") { |s| s.debug(msg) }
      rescue RuntimeError
      end
      }
      end
  end

  def self.log_run(command)
    Djinn.log_debug(command)
    Djinn.log_debug(`#{command}`)
  end

  # kinda misnamed - it converts an array of strings
  # to an array of DjinnJobData
  def self.convert_location_array_to_class(nodes, keyname)
    if nodes.class != Array
      abort("Locations should be an array, not a #{nodes.class}")
    end

    Djinn.log_debug("keyname is of class #{keyname.class}")
    Djinn.log_debug("keyname is #{keyname}")
    
    array_of_nodes = []
    nodes.each { |node|
      converted = DjinnJobData.new(node, keyname)
      array_of_nodes << converted
      Djinn.log_debug("adding data " + converted.to_s)
    }
    
    return array_of_nodes
  end

  def self.convert_location_class_to_array(djinn_locations)
    if djinn_locations.class != Array
      raise Exception, "Locations should be an array"
    end
    
    djinn_loc_array = []
    djinn_locations.each { |location|
      djinn_loc_array << location.serialize
      Djinn.log_debug("serializing data " + location.serialize)
    }
    
    return djinn_loc_array
  end
    
  def initialize()
    @job = "none"
    @nodes = []
    @creds = {}
    @app_names = []
    @apps_loaded = []
    @kill_sig_received = false
    @my_index = nil
    @@secret = HelperFunctions.get_secret
    @done_loading = false
    @port = 8080
    @userappserver_public_ip = "not-up-yet"
    @userappserver_private_ip = "not-up-yet"
    @state = "AppController just started"
    @total_boxes = 0
    @num_appengines = 3
    @restored = false
    @neptune_jobs = {}
    @neptune_nodes = []
    @lock = Monitor.new
  end

  def get_login
    @nodes.each { |node|
      return node if node.is_login?
    }

    abort("No login nodes found.")
  end

  def get_shadow
    @nodes.each { |node|
      return node if node.is_shadow?
    }

    abort("No shadow nodes found.")
  end

  def get_db_master
    @nodes.each { |node|
      return node if node.is_db_master?
    }

    abort("No db master nodes found.")
  end

  def self.get_db_master_ip
    masters_file = File.expand_path("#{APPSCALE_HOME}/.appscale/masters")
    master_ip = HelperFunctions.read_file(masters_file)
    return master_ip
  end

  def self.get_db_slave_ips
    slaves_file = File.expand_path("#{APPSCALE_HOME}/.appscale/slaves")
    slave_ips = File.open(slaves_file).readlines.map { |f| f.chomp! }
    slave_ips = [] if slave_ips == [""]
    return slave_ips
  end

  def self.get_nearest_db_ip(is_mysql=false)
    db_ips = self.get_db_slave_ips
    # Unless this is mysql we include the master ip
    # Update, now mysql also has an API node
    db_ips << self.get_db_master_ip
    db_ips.compact!
    
    local_ip = HelperFunctions.local_ip
    Djinn.log_debug("db ips are [#{db_ips.join(', ')}]")
    if db_ips.include?(local_ip)
      # If there is a local database then use it
      local_ip
    else
      # Otherwise just select one randomly
      db_ips.sort_by { rand }[0]
    end
  end

  def valid_secret?(secret)
    @@secret = HelperFunctions.get_secret
    if secret != @@secret
      failed_match_msg = "Incoming secret [#{secret}] failed to match " + \
        " known secret [#{@@secret}]"
      Djinn.log_debug(failed_match_msg)
    end
    return secret == @@secret
  end

  def set_uaserver_ips()
    ip_addr = get_uaserver_ip()
    unless is_cloud?
      @userappserver_public_ip = ip_addr
      @userappserver_private_ip = ip_addr
      Djinn.log_debug("\n\nUAServer is at [#{@userappserver_public_ip}]\n\n")
      return
    end
    
    keyname = @creds["keyname"]
    infrastructure = @creds["infrastructure"]    
 
    if is_hybrid_cloud?
      Djinn.log_debug("getting hybrid ips with creds #{@creds.inspect}")
      public_ips, private_ips = HelperFunctions.get_hybrid_ips(@creds)
    else
      Djinn.log_debug("getting cloud ips for #{infrastructure} with keyname #{keyname}")
      public_ips, private_ips = HelperFunctions.get_cloud_ips(infrastructure, keyname)
    end
 
    Djinn.log_debug("public ips are #{public_ips.join(', ')}")
    Djinn.log_debug("private ips are #{private_ips.join(', ')}")
    Djinn.log_debug("looking for #{ip_addr}")

    public_ips.each_index { |index|
      if public_ips[index] == ip_addr or private_ips[index] == ip_addr
        @userappserver_public_ip = public_ips[index]
        @userappserver_private_ip = private_ips[index]
        return
      end
    }

    unable_to_convert_msg = "[get uaserver ip] Couldn't find out whether #{ip_addr} was " + 
      "a public or private IP address. Public IPs are " +
      "[#{public_ips.join(', ')}], private IPs are [#{private_ips.join(', ')}]"

    abort(unable_to_convert_msg)
  end
  
  def get_public_ip(private_ip)
    return private_ip unless is_cloud?
    
    keyname = @creds["keyname"]
    infrastructure = @creds["infrastructure"]    

    if is_hybrid_cloud?
      Djinn.log_debug("getting hybrid ips with creds #{@creds.inspect}")
      public_ips, private_ips = HelperFunctions.get_hybrid_ips(@creds)
    else
      Djinn.log_debug("getting cloud ips for #{infrastructure} with keyname #{keyname}")
      public_ips, private_ips = HelperFunctions.get_cloud_ips(infrastructure, keyname)
    end

    Djinn.log_debug("public ips are #{public_ips.join(', ')}")
    Djinn.log_debug("private ips are #{private_ips.join(', ')}")
    Djinn.log_debug("looking for #{private_ip}")

    public_ips.each_index { |index|
      if private_ips[index] == private_ip or public_ips[index] == private_ip
        return public_ips[index]
      end
    }

    unable_to_convert_msg = "[get public ip] Couldn't convert private IP #{private_ip}" + 
      " to a public address. Public IPs are [#{public_ips.join(', ')}]," + 
      " private IPs are [#{private_ips.join(', ')}]"

    abort(unable_to_convert_msg)  
  end

  def get_status(node)
    public_ip = node.private_ip
    ip = node.private_ip
    ssh_key = node.ssh_key
    acc = AppControllerClient.new(ip, @@secret)

    result = acc.get_status(ok_to_fail=true)
    Djinn.log_debug("#{ip}'s returned [#{result}] - class is #{result.class}")

    if !result
      node.failed_heartbeats += 1
      Djinn.log_debug("#{ip} returned false - is it not running?")
      Djinn.log_debug("#{ip} has failed to respond to #{node.failed_heartbeats} heartbeats in a row")
      return
    else
      Djinn.log_debug("#{ip} responded to the heartbeat - it is alive")
      node.failed_heartbeats = 0
    end

    if result[0].chr == "f" # false: bad secret (debug)
      old_secret = @@secret
      @@secret = HelperFunctions.get_secret
      secret_mismatch_msg = "Bad secret with #{ip}. My new secret " + \
        "is [#{@@secret}], and the old secret was [#{old_secret}]"
      Djinn.log_debug(secret_mismatch_msg)
    else
      status_file = "/etc/appscale/status-#{ip}.log"
      HelperFunctions.write_file(status_file, result)

      unless my_node.is_login?
        login_ip = get_login.private_ip
        HelperFunctions.scp_file(status_file, status_file, login_ip, ssh_key)
      end

      # copy remote log over - handy for debugging
      local_log = "#{APPSCALE_HOME}/.appscale/logs/#{ip}.log"
      remote_log = "/tmp/*.log"

      FileUtils.mkdir_p("#{APPSCALE_HOME}/.appscale/logs/")
      Djinn.log_run("scp -o StrictHostkeyChecking=no -i #{ssh_key} #{ip}:#{remote_log} #{local_log}")
    end
  end

  # TODO: add neptune file, which will have this function
  def run_neptune_in_cloud?(neptune_info)
    Djinn.log_debug("activecloud_info = #{neptune_info}")
    return true if is_cloud? && !neptune_info["nodes"].nil?
    return true if !is_cloud? && !neptune_info["nodes"].nil? && !neptune_info["machine"].nil?
    return false
  end

  def heartbeat(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return true
  end

  def write_database_info()
    table = @creds["table"]
    replication = @creds["replication"]
    keyname = @creds["keyname"]
    
    tree = { :table => table, :replication => replication,
      :local_accesses => @global_local, :remote_accesses => @global_remote ,
      :keyname => keyname }
    db_info_path = "#{APPSCALE_HOME}/.appscale/database_info.yaml"
    File.open(db_info_path, "w") { |file| YAML.dump(tree, file) }
    
    num_of_nodes = @nodes.length
    HelperFunctions.write_file("#{APPSCALE_HOME}/.appscale/num_of_nodes", "#{num_of_nodes}\n")
    
    all_private_ips = []
    @nodes.each { |loc|
      all_private_ips << loc.private_ip
    }
    all_private_ips << "\n"
    HelperFunctions.write_file("#{APPSCALE_HOME}/.appscale/all_ips", all_private_ips.join("\n"))
    # Re-run the filewall script here since we just wrote the all_ips file
    `bash #{APPSCALE_HOME}/firewall.conf` if FIREWALL_IS_ON 
  end

  def write_neptune_info()
    info = ""
    @neptune_jobs.each { |k, v|
      info << v.join("\n") + "\n"
    }

    HelperFunctions.write_file(NEPTUNE_INFO, info)
  end

  def load_neptune_info()
    unless File.exists?(NEPTUNE_INFO)
      Djinn.log_debug("no neptune data found - no need to restore")
      return
    end

    Djinn.log_debug("restoring neptune data!")
    jobs_info = (File.open(NEPTUNE_INFO) { |f| f.read }).chomp
    jobs = []
    jobs_info.split("\n").each { |job|
      info = job.split("::")
      name = info[0]
      num_nodes = Integer(info[1])

      begin
        start_time = Time._load(info[2])
        end_time = Time._load(info[3])
      rescue TypeError
        start_time = Time.now
        end_time = Time.now
      end

      this_job = NeptuneJobData.new(name, num_nodes, start_time, end_time)

      if @neptune_jobs[name].nil?
        @neptune_jobs[name] = [this_job]
      else
        @neptune_jobs[name] << this_job
      end
    }
  end

  def wait_for_data()
    loop {
      if got_all_data
        got_data_msg = "Got data from another node! DLoc = " + \
          "#{@nodes.join(', ')}, #{@creds.inspect}, AppsToLoad = " + \
          "#{@app_names.join(', ')}"
        Djinn.log_debug(got_data_msg)
        
        if @creds["appengine"]
          @num_appengines = Integer(@creds["appengine"])
        end

        Djinn.log_debug("keypath is #{@creds['keypath']}, keyname is #{@creds['keyname']}")

        if @creds["keypath"] != ""
          my_key_dir = "/etc/appscale/keys/#{my_node.cloud}"
          my_key_loc = "#{my_key_dir}/#{@creds['keypath']}"
          Djinn.log_debug("Creating directory #{my_key_dir} for my ssh key #{my_key_loc}")
          FileUtils.mkdir_p(my_key_dir)
          `cp /etc/appscale/ssh.key #{my_key_loc}`
        end
        
        if is_cloud?
          # for euca
          ENV['EC2_ACCESS_KEY'] = @creds["ec2_access_key"]
          ENV['EC2_SECRET_KEY'] = @creds["ec2_secret_key"]
          ENV['EC2_URL'] = @creds["ec2_url"]

          # for ec2
          cloud_keys_dir = File.expand_path("/etc/appscale/keys/cloud1")
          ENV['EC2_PRIVATE_KEY'] = "#{cloud_keys_dir}/mykey.pem"
          ENV['EC2_CERT'] = "#{cloud_keys_dir}/mycert.pem"
        end

        write_database_info
        load_neptune_info
        write_neptune_info     
        break
      elsif @kill_sig_received
        msg = "Received kill signal, aborting startup"
        Djinn.log_debug(msg)
        abort(msg)
      else
        Djinn.log_debug("Waiting for data from the load balancer or cmdline tools")
        sleep(5)
      end
    }

    return
  end

  def got_all_data()
    return false if @nodes == []
    return false if @creds == {}
    return false if @app_names == []
    return true
  end
  
  def convert_fqdns_to_ips()
    return unless is_cloud?
    
    if @creds["hostname"] =~ /#{FQDN_REGEX}/
      begin
        @creds["hostname"] = HelperFunctions.convert_fqdn_to_ip(@creds["hostname"])
      rescue Exception => e
        Djinn.log_debug("rescue! failed to convert main hostname #{@creds['hostname']} to public, might want to look into this?")
      end
    end
    
    @nodes.each { |node|
      #pub = location.public_ip
      #if pub =~ /#{FQDN_REGEX}/
      #  location.public_ip = HelperFunctions.convert_fqdn_to_ip(pub)
      #end

      pri = node.private_ip
      if pri =~ /#{FQDN_REGEX}/
        begin
          node.private_ip = HelperFunctions.convert_fqdn_to_ip(pri)
        rescue Exception => e
          node.private_ip = location.public_ip
        end
      end
    }
  end

 
  def find_me_in_locations()
    @my_index = nil
    @nodes.each_index { |index|
      if @nodes[index].private_ip == HelperFunctions.local_ip
        @my_index = index
        break
      end
    }
  end

  def valid_format_for_credentials(possible_credentials)
    return false if possible_credentials.class != Hash

    required_fields = ["table", "hostname", "ips"]
    required_fields.each { |field|
      return false if !possible_credentials[field]
    }

    return true
  end
  
  def sanitize_credentials()
    newcreds = {}
    @creds.each { |key, val|
      newkey = key.gsub(/[^\w\d_@-]/, "") unless key.nil?
      newval = val.gsub(/[^\w\d\.:\/_-]/, "") unless val.nil?
      newcreds[newkey] = newval
    }
    return newcreds
  end
    
  def change_job(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    
    my_data = my_node
    jobs_to_run = my_data.jobs
    
    if @creds['ips']
      @total_boxes = @creds['ips'].length + 1
    elsif @creds['min_images']
      @total_boxes = Integer(@creds['min_images'])
    end

    Djinn.log_debug("pre-loop: #{@nodes.join('\n')}")
    if @nodes.size == 1 and @total_boxes > 1
      spawn_and_setup_appengine
      loop {
        Djinn.log_debug("looping: #{@nodes.join('\n')}")
        @everyone_else_is_done = true
        @nodes.each_index { |index|
          unless index == @my_index
            ip = @nodes[index].private_ip
            acc = AppControllerClient.new(ip, @@secret)
            result = acc.done()
            Djinn.log_debug("#{ip} returned #{result} (#{result.class})")
            @everyone_else_is_done = false unless result
          end
        }
        break if @everyone_else_is_done
        Djinn.log_debug("Waiting on other nodes to come online")
        sleep(5)
      }
    end

    initialize_server
    # start_load_balancer 

    if my_node.is_load_balancer? or my_node.is_appengine?
      start_memcached
    end

    setup_config_files
    set_uaserver_ips 
    write_hypersoap

    # ejabberd uses uaserver for authentication
    # so start it after we find out the uaserver's ip

    start_ejabberd if my_node.is_login?

    @done_loading = true

    # start zookeeper
    if my_node.is_zookeeper?
      configure_zookeeper(@nodes, @my_index)
      init = !(@creds.include?("keep_zookeeper_data"))
      start_zookeeper(init)
    end

    ZKInterface.init(my_node, @nodes)

    commands = {
      "load_balancer" => "start_load_balancer",
      "db_master" => "start_db_master",
      "db_slave" => "start_db_slave"
    }

    jobs_to_run.each do |job|
      if commands.include?(job)
        Djinn.log_debug("About to run [#{commands[job]}]")
        send(commands[job].to_sym)
      end
    end

    # create initial tables
    if (my_node.is_db_master? || (defined?(is_priming_needed?) && is_priming_needed?(my_node))) && !restore_from_db?
      table = @creds['table']
      prime_script = "#{APPSCALE_HOME}/AppDB/#{table}/prime_#{table}.py"
      retries = 10
      retval = 0
      while retries > 0
        Djinn.log_debug(`MASTER_IP="localhost" LOCAL_DB_IP="localhost" python2.6 #{prime_script}; echo $? > /tmp/retval`)
        retval = `cat /tmp/retval`.to_i
        break if retval == 0
        Djinn.log_debug("Fail to create initial table. Retry #{retries} times.")
        sleep(5)
        retries -= 1
      end
      if retval != 0
        Djinn.log_debug("Fail to create initial table. Could not startup AppScale.")
        exit(1)
        # TODO: terminate djinn
      end
    end

    # start soap server and pb server
    if has_soap_server?(my_node)
      @state = "Starting up SOAP Server and PBServer"
      start_pbserver
      start_soap_server
      HelperFunctions.sleep_until_port_is_open(HelperFunctions.local_ip, UA_SERVER_PORT)
    end

   start_blobstore_server if my_node.is_appengine?

   # for neptune jobs, start a place where they can save output to
   Repo.init(get_shadow.public_ip, @@secret)
   if my_node.is_shadow?
     Repo.start(get_login.public_ip, @userappserver_private_ip)
   end

   # appengine is started elsewhere
  end

  def start_blobstore_server
    db_local_ip = @userappserver_private_ip
    BlobServer.start(db_local_ip, PbServer.listen_port)
    BlobServer.is_running(db_local_ip)
  end


  def start_soap_server
    db_master_ip = nil
    @nodes.each { |node|
      db_master_ip = node.private_ip if node.is_db_master?
    }
    abort("db master ip was nil") if db_master_ip.nil?

    db_local_ip = @userappserver_private_ip
            
    table = @creds['table']

    if table == "simpledb"
      a_key = @creds['SIMPLEDB_ACCESS_KEY']
      s_key = @creds['SIMPLEDB_SECRET_KEY']
      simpledb_creds = "SIMPLEDB_ACCESS_KEY='#{a_key}' SIMPLEDB_SECRET_KEY='#{s_key}'"
    else
      simpledb_creds = ""
    end

    cmd = [ "MASTER_IP='#{db_master_ip}' LOCAL_DB_IP='#{db_local_ip}'",
            simpledb_creds,
            "start-stop-daemon --start",
            "--exec /usr/bin/python2.6",
            "--name soap_server",
            "--make-pidfile",
            "--pidfile /var/appscale/appscale-soapserver.pid",
            "--background",
            "--",
            "#{APPSCALE_HOME}/AppDB/soap_server.py",
            "-t #{table}",
            "-s #{HelperFunctions.get_secret}"]
    Djinn.log_debug(cmd.join(" "))
    Kernel.system cmd.join(" ")
  end 

  def start_pbserver
    db_master_ip = nil
    my_ip = my_node.public_ip
    @nodes.each { |node|
      db_master_ip = node.private_ip if node.is_db_master?
    }
    abort("db master ip was nil") if db_master_ip.nil?
    table = @creds['table']
    zoo_connection = get_zk_connection_string(@nodes)
    PbServer.start(db_master_ip, @userappserver_private_ip, my_ip, table, zoo_connection)
    HAProxy.create_pbserver_config(my_ip, PbServer.proxy_port, table)
    Nginx.create_pbserver_config(my_ip, PbServer.proxy_port)
    Nginx.restart 
    # TODO check the return value
    PbServer.is_running(my_ip)
  end

  def stop_blob_server
    BlobServer.stop
    Djinn.log_debug(`pkill -f blobstore_server`)
  end 

  def stop_soap_server
    Kernel.system "start-stop-daemon --stop --pidfile /var/appscale/appscale-soapserver.pid"
  end 

  def stop_pbserver
    PbServer.stop(@creds['table']) 
  end
  
  def is_hybrid_cloud?
    if @creds["infrastructure"].nil?
      false
    else
      @creds["infrastructure"] == "hybrid"
    end
  end

  def is_cloud?
    !@creds["infrastructure"].nil?
  end

  def restore_from_db?
    @creds['restore_from_tar'] || @creds['restore_from_ebs']
  end

  def spawn_and_setup_appengine()
    # should also make sure the tools are on the vm and the envvars are set

    table = @creds['table']

    nodes = HelperFunctions.deserialize_info_from_tools(@creds["ips"])
    appengine_info = spawn_appengine(nodes)

    @state = "Copying over needed files and starting the AppController on the other VMs"
    
    keyname = @creds["keyname"] 
    appengine_info = Djinn.convert_location_array_to_class(appengine_info, keyname)
    @nodes.concat(appengine_info)
    
    creds = @creds.to_a.flatten
    Djinn.log_debug("Djinn locations: #{@nodes.join(', ')}")
    Djinn.log_debug("DB Credentials: #{@creds.inspect}")
    Djinn.log_debug("Apps to load: #{@app_names.join(', ')}")

    Djinn.log_debug("Appengine info: #{appengine_info}")

    threads = []
    appengine_info.each { |slave|
      threads << Thread.new { 
        initialize_node(slave)
      }
    }

    threads.each { |t| t.join }
  end

  def spawn_appengine(nodes)
    appengine_info = []
    if nodes.length > 0
      if is_hybrid_cloud?
        num_of_vms_needed = nodes.length
        @state = "Spawning up hybrid virtual machines"
        appengine_info = HelperFunctions.spawn_hybrid_vms(@creds, nodes)
      elsif is_cloud?
        num_of_vms_needed = nodes.length
        machine = @creds["machine"]
        ENV['EC2_URL'] = @creds["ec2_url"]
        instance_type = @creds["instance_type"]
        keyname = @creds["keyname"]
        infrastructure = @creds["infrastructure"]

        @state = "Spawning up #{num_of_vms_needed} virtual machines"
        roles = nodes.values

        # since there's only one cloud, call it cloud1 to tell us
        # to use the first ssh key (the only key)
        HelperFunctions.set_creds_in_env(@creds, "1")
        appengine_info = HelperFunctions.spawn_vms(num_of_vms_needed, roles, 
          machine, instance_type, keyname, infrastructure, "cloud1")
      else
        nodes.each_pair do |ip,roles|
          # for xen the public and private ips are the same
          # and we call it cloud1 since the first key (only key)
          # is the key to use

          info = "#{ip}:#{ip}:#{roles}:i-SGOOBARZ:cloud1"
          appengine_info << info
          Djinn.log_debug("Received appengine info: #{info}")
        end
      end
    end

    return appengine_info
  end

  def initialize_node(node)
    copy_encryption_keys(node)
    validate_image(node)
    restore_db_state_if_needed(node)
    rsync_files(node)
    start_appcontroller(node)
  end

  def validate_image(node)
    ip = node.public_ip
    key = node.ssh_key
    HelperFunctions.ensure_image_is_appscale(ip, key)
    HelperFunctions.ensure_db_is_supported(ip, @creds["table"], key)
  end

  def restore_db_state_if_needed(dest_node)
    return unless dest_node.is_db_master?
    return unless @creds["restore_from_tar"]

    ip = dest_node.private_ip
    ssh_key = dest_node.ssh_key
    Djinn.log_debug("Restoring DB, copying data to DB master at #{ip}")
    db_tar_loc = @creds["restore_from_tar"]
    HelperFunctions.scp_file(db_tar_loc, db_tar_loc, ip, ssh_key)
  end

  def copy_encryption_keys(dest_node)
    ip = dest_node.private_ip
    ssh_key = dest_node.ssh_key

    HelperFunctions.sleep_until_port_is_open(ip, SSH_PORT)
    sleep(3)

    if @creds["infrastructure"] == "ec2" or @creds["infrastructure"] == "hybrid"
      enable_root_login = "sudo cp /home/ubuntu/.ssh/authorized_keys /root/.ssh/"
      Djinn.log_run("ssh -i #{ssh_key} -o StrictHostkeyChecking=no 2>&1 ubuntu@#{ip} '#{enable_root_login}'")
    end

    secret_key_loc = "/etc/appscale/secret.key"
    cert_loc = "/etc/appscale/certs/mycert.pem"
    key_loc = "/etc/appscale/certs/mykey.pem"

    HelperFunctions.scp_file(secret_key_loc, secret_key_loc, ip, ssh_key)
    HelperFunctions.scp_file(cert_loc, cert_loc, ip, ssh_key)
    HelperFunctions.scp_file(key_loc, key_loc, ip, ssh_key)

    # TODO: should be able to merge these together
    if is_hybrid_cloud?
      cloud_num = 1
      loop {
        cloud_type = @creds["CLOUD#{cloud_num}_TYPE"]
        break if cloud_type.nil? or cloud_type == ""
        cloud_keys_dir = File.expand_path("/etc/appscale/keys/cloud#{cloud_num}")
        make_dir = "mkdir -p #{cloud_keys_dir}"

        keyname = @creds["keyname"]
        cloud_ssh_key = "#{cloud_keys_dir}/#{keyname}.key"
        cloud_private_key = "#{cloud_keys_dir}/mykey.pem"
        cloud_cert = "#{cloud_keys_dir}/mycert.pem"

        HelperFunctions.run_remote_command(ip, make_dir, ssh_key, NO_OUTPUT)
        HelperFunctions.scp_file(cloud_ssh_key, cloud_ssh_key, ip, ssh_key)
        HelperFunctions.scp_file(cloud_private_key, cloud_private_key, ip, ssh_key)
        HelperFunctions.scp_file(cloud_cert, cloud_cert, ip, ssh_key)
        cloud_num += 1
      }
    else
      cloud_keys_dir = File.expand_path("/etc/appscale/keys/cloud1")
      make_dir = "mkdir -p #{cloud_keys_dir}"

      cloud_private_key = "#{cloud_keys_dir}/mykey.pem"
      cloud_cert = "#{cloud_keys_dir}/mycert.pem"

      HelperFunctions.run_remote_command(ip, make_dir, ssh_key, NO_OUTPUT)
      HelperFunctions.scp_file(ssh_key, ssh_key, ip, ssh_key)
      HelperFunctions.scp_file(cloud_private_key, cloud_private_key, ip, ssh_key)
      HelperFunctions.scp_file(cloud_cert, cloud_cert, ip, ssh_key)
    end
  end
 
  def rsync_files(dest_node)
    controller = "#{APPSCALE_HOME}/AppController"
    server = "#{APPSCALE_HOME}/AppServer"
    loadbalancer = "#{APPSCALE_HOME}/AppLoadBalancer"
    appdb = "#{APPSCALE_HOME}/AppDB"
    neptune = "#{APPSCALE_HOME}/Neptune"
    loki = "#{APPSCALE_HOME}/Loki"

    ssh_key = dest_node.ssh_key
    ip = dest_node.private_ip

    Djinn.log_run("rsync -e 'ssh -i #{ssh_key}' -arv #{controller}/* root@#{ip}:#{controller}")
    Djinn.log_run("rsync -e 'ssh -i #{ssh_key}' -arv #{server}/* root@#{ip}:#{server}")
    Djinn.log_run("rsync -e 'ssh -i #{ssh_key}' -arv #{loadbalancer}/* root@#{ip}:#{loadbalancer}")
    Djinn.log_debug(`rsync -e 'ssh -i #{ssh_key}' -arv --exclude="logs/*" --exclude="hadoop-*" --exclude="hbase/hbase-*" --exclude="voldemort/voldemort/*" --exclude="cassandra/cassandra/*" #{appdb}/* root@#{ip}:#{appdb}`)
    Djinn.log_debug(`rsync -e 'ssh -i #{ssh_key}' -arv #{neptune}/* root@#{ip}:#{neptune}`)
    #Djinn.log_debug(`rsync -e 'ssh -i #{ssh_key}' -arv #{loki}/* root@#{ip}:#{loki}`)
  end

  def setup_config_files()
    @state = "Setting up database configuration files"

    master_ip = []
    slave_ips = []

    # load datastore helper
    # TODO: this should be the class or module
    table = @creds['table']
    # require db_file
    begin
      require "#{APPSCALE_HOME}/AppDB/#{table}/#{table}_helper"
    rescue Exception => e
      backtrace = e.backtrace.join("\n")
      bad_datastore_msg = "Unable to find #{table} helper." + \
        " Please verify datastore type: #{e}\n#{backtrace}"
      Djinn.log_debug(bad_datastore_msg)
      abort(bad_datastore_msg)
    end
    `mkdir -p #{APPSCALE_HOME}/AppDB/logs`

    @nodes.each { |node| 
      master_ip = node.private_ip if node.jobs.include?("db_master")
      slave_ips << node.private_ip if node.jobs.include?("db_slave")
    }

    Djinn.log_debug("Master is at #{master_ip}, slaves are at #{slave_ips.join(', ')}")

    my_public = my_node.public_ip
    HelperFunctions.write_file("#{APPSCALE_HOME}/.appscale/my_public_ip", "#{my_public}\n")

    my_private = my_node.private_ip
    HelperFunctions.write_file("#{APPSCALE_HOME}/.appscale/my_private_ip", "#{my_private}\n")
   
    head_node_ip = get_public_ip(@creds['hostname'])
    HelperFunctions.write_file("#{APPSCALE_HOME}/.appscale/head_node_ip", "#{head_node_ip}\n")

    login_ip = get_login.public_ip
    HelperFunctions.write_file("#{APPSCALE_HOME}/.appscale/login_ip", "#{login_ip}\n")
    
    masters_file = "#{APPSCALE_HOME}/.appscale/masters"
    HelperFunctions.write_file(masters_file, "#{master_ip}\n")

    if @total_boxes == 1
      slave_ips = [ @creds['hostname'] ]
    end
    
    slave_ips_newlined = slave_ips.join("\n")
    HelperFunctions.write_file("#{APPSCALE_HOME}/.appscale/slaves", "#{slave_ips_newlined}\n")

    # n = @creds["replication"]

    # setup_hadoop_config(template_loc, hadoop_hbase_loc, master_ip, slave_ips, n)

    # Invoke datastore helper function
    setup_db_config_files(master_ip, slave_ips, @creds)

    all_nodes = ""
    @nodes.each_with_index { |node, index|
      all_nodes << "#{node.private_ip} appscale-image#{index}\n"
    }
    
    etc_hosts = "/etc/hosts"
    my_hostname = "appscale-image#{@my_index}"
    etc_hostname = "/etc/hostname"

    new_etc_hosts = <<HOSTS
127.0.0.1 localhost.localdomain localhost
127.0.1.1 localhost
::1     ip6-localhost ip6-loopback
fe00::0 ip6-localnet
ff00::0 ip6-mcastprefix
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
ff02::3 ip6-allhosts
#{all_nodes}
HOSTS

    File.open(etc_hosts, "w+") { |file| file.write(new_etc_hosts) }    
    File.open(etc_hostname, "w+") { |file| file.write(my_hostname) }

    # on ubuntu jaunty, we can change the hostname by running hostname.sh
    # on karmic, this file doesn't exist - run /bin/hostname instead
    # TODO: does the fix for karmic hold for lucid?

    jaunty_hostname_file = "/etc/init.d/hostname.sh"

    if File.exists?(jaunty_hostname_file)
      `/etc/init.d/hostname.sh`
    else
      `/bin/hostname #{my_hostname}`
    end

    # use iptables to lock down outside traffic
    # nodes can talk to each other on any port
    # but only the outside world on certain ports
    #`iptables --flush`
    `bash #{APPSCALE_HOME}/firewall.conf` if FIREWALL_IS_ON
  end

  def write_hypersoap()
    HelperFunctions.write_file("#{APPSCALE_HOME}/.appscale/hypersoap", @userappserver_private_ip)
  end

  def my_node()
    if @my_index.nil?
      find_me_in_locations
    #  Djinn.log_debug("my index is nil - is nodes nil? #{@nodes.nil?}")
    #  return nil
    end

    @nodes[@my_index]
  end
  
  # Perform any necessary initialization steps before we begin starting up services
  def initialize_server
    my_public_ip = my_node.public_ip
    head_node_ip = get_public_ip(@creds['hostname'])

    HAProxy.initialize_config
    Nginx.initialize_config
    Collectd.initialize_config(my_public_ip, head_node_ip)
    Monitoring.reset
  end

  def start_appcontroller(node)
    ip = node.private_ip
    ssh_key = node.ssh_key

    start_server = "service appscale-controller start"
    begin
      HelperFunctions.run_remote_command(ip, start_server, ssh_key, WANT_OUTPUT)
      HelperFunctions.sleep_until_port_is_open(ip, DJINN_SERVER_PORT, USE_SSL)
    rescue Exception => except
      backtrace = except.backtrace.join("\n")
      remote_start_msg = "[remote_start] Unforeseen exception when " + \
        "talking to #{ip}: #{except}\nBacktrace: #{backtrace}"
      Djinn.log_debug(remote_start_msg)
      retry
    end
    
    Djinn.log_debug("Sending data to #{ip}")
    acc = AppControllerClient.new(ip, @@secret)

    loc_array = Djinn.convert_location_class_to_array(@nodes)
    credentials = @creds.to_a.flatten

    result = acc.set_parameters(loc_array, credentials, @app_names)
    Djinn.log_debug("#{ip} responded with #{result}")
  end

  def is_running?(name)
    `ps ax | grep #{name} | grep -v grep` != ""
  end

  def start_memcached()
    @state = "Starting up memcached"
    Djinn.log_debug("Starting up memcached")
    Djinn.log_run("/usr/bin/memcached -d -m 32 -p 11211 -u root")
  end

  def stop_memcached()
    Djinn.log_run("pkill memcached")
  end

  def start_ejabberd()
    @state = "Starting up XMPP server"
    my_public = my_node.public_ip
    Ejabberd.stop
    Djinn.log_run("rm -f /var/lib/ejabberd/*")
    Ejabberd.write_auth_script(my_public, @@secret)
    Ejabberd.write_config_file(my_public)
    Ejabberd.start
  end

  def stop_ejabberd()
    Ejabberd.stop
    `pkill -f xmpp_receiver`
  end

  def start_load_balancer()
    @state = "Starting up Load Balancer"
    Djinn.log_debug("Starting up Load Balancer")

    my_ip = my_node.public_ip
    HAProxy.create_app_load_balancer_config(my_ip, LoadBalancer.proxy_port)
    Nginx.create_app_load_balancer_config(my_ip, LoadBalancer.proxy_port)
    LoadBalancer.start
    Nginx.restart
    Collectd.restart

    head_node_ip = get_public_ip(@creds['hostname'])
    if my_ip == head_node_ip
      # Only start monitoring on the head node
      HAProxy.create_app_monitoring_config(my_ip, Monitoring.proxy_port)
      Nginx.create_app_monitoring_config(my_ip, Monitoring.proxy_port)
      Nginx.restart
      Monitoring.start
    end

    LoadBalancer.server_ports.each do |port|
      HelperFunctions.sleep_until_port_is_open("localhost", port)
      `curl http://localhost:#{port}`
    end
  end

  # TODO: this function should use hadoop_helper
  def setup_hadoop_config_org(source_dir, dest_dir, master_ip, slave_ips, n)
    ["source_dir", "dest_dir", "master_ip"].each { |param_name|
      param = eval(param_name)
      abort("#{param_name} wasn't a String. It was a/an #{param.class}") if param.class != String
    }

    source_dir = File.expand_path(source_dir)
    dest_dir = File.expand_path(dest_dir)

    abort("Source dir [#{source_dir}] didn't exist") unless File.directory?(source_dir)
    abort("Dest dir [#{dest_dir}] didn't exist") unless File.directory?(dest_dir)

    files_to_config = `ls #{source_dir}`.split
    files_to_config.each{ |filename|
      full_path_to_read = source_dir + File::Separator + filename
      full_path_to_write = dest_dir + File::Separator + filename
      File.open(full_path_to_read) { |source_file|
        contents = source_file.read
        contents.gsub!(/APPSCALE-MASTER/, master_ip)
        contents.gsub!(/APPSCALE-SLAVES/, slave_ips.join("\n"))
        contents.gsub!(/REPLICATION/, n)
  
        HelperFunctions.write_file(full_path_to_write, contents)
      }
    }
  end

  # TODO: this function should use hadoop_helper
  def start_hadoop_org()
    i = my_node
    return unless i.is_shadow? # change this later to db_master
    hadoop_home = File.expand_path("#{APPSCALE_HOME}/AppDB/hadoop-0.20.2/")
    Djinn.log_debug(`#{hadoop_home}/bin/hadoop namenode -format 2>&1`)
    Djinn.log_debug(`#{hadoop_home}/bin/start-dfs.sh 2>&1`)
    Djinn.log_debug(`python #{hadoop_home}/../wait_on_hadoop.py 2>&1`)
    Djinn.log_debug(`#{hadoop_home}/bin/start-mapred.sh 2>&1`)
  end

  def stop_load_balancer()
    Djinn.log_debug("Shutting down Load Balancer")
    LoadBalancer.stop
  end

  def start_appengine()
    @state = "Preparing to run AppEngine apps if needed"
    Djinn.log_debug("starting appengine - pbserver is at [#{@userappserver_private_ip}]")

    uac = UserAppClient.new(@userappserver_private_ip, @@secret)

    if @restored == false #and restore_from_db?
      Djinn.log_debug("need to restore")
      all_apps = uac.get_all_apps()
      Djinn.log_debug("all apps are [#{all_apps}]")
      app_list = all_apps.split(":")
      app_list = app_list - [app_list[0]] # first item is a dummy value, ____
      app_list.each { |app|
        app_is_enabled = uac.does_app_exist?(app)
        Djinn.log_debug("is app #{app} enabled? #{app_is_enabled}")
        if app_is_enabled == "true"
          @app_names = @app_names + [app]
        end
      }

      @app_names.uniq!
      Djinn.log_debug("decided to restore these apps: [#{@app_names.join(', ')}]")
      @restored = true
    else
      Djinn.log_debug("don't need to restore")
    end

    apps_to_load = @app_names - @apps_loaded - ["none"]
    apps_to_load.each { |app|
      app_data = uac.get_app_data(app)
      Djinn.log_debug("Get app data for #{app} said [#{app_data}]")

      loop {
        app_version = app_data.scan(/version:(\d+)/).flatten.to_s
        Djinn.log_debug("Waiting for app data to have instance info for app named #{app}: #{app_data}")
        Djinn.log_debug("The app's version is #{app_version}, and its class is #{app_version.class}")

        if app_data[0..4] != "Error"
          app_version = "0" if app_version == ""
          app_version = Integer(app_version)
          break if app_version >= 0
        end

        app_data = uac.get_app_data(app)
        sleep(5)
      }

      my_public = my_node.public_ip
      app_version = app_data.scan(/version:(\d+)/).flatten.to_s
      app_language = app_data.scan(/language:(\w+)/).flatten.to_s
            
      # TODO: merge these 
      shadow = get_shadow
      shadow_ip = shadow.private_ip
      ssh_key = shadow.ssh_key
      app_dir = "/var/apps/#{app}/app"
      app_path = "#{app_dir}/#{app}.tar.gz"
      FileUtils.mkdir_p(app_dir)
       
      copy_app_to_local(app)
      HelperFunctions.setup_app(app)
 
      if my_node.is_shadow?
        CronHelper.update_cron(my_public, app_language, app)
        start_xmpp_for_app(app, app_language)
      end

      if my_node.is_appengine?
        app_number = @port - 8080
        start_port = 20000
        static_handlers = HelperFunctions.parse_static_data(app)
        proxy_port = HAProxy.app_listen_port(app_number)
        login_ip = get_login.public_ip
        Nginx.write_app_config(app, app_number, my_public, proxy_port, static_handlers, login_ip)
        HAProxy.write_app_config(app, app_number, @num_appengines, my_public)
        Collectd.write_app_config(app)

        @num_appengines.times { |index|
          app_true_port = start_port + app_number * @num_appengines + index
          Djinn.log_debug("Starting #{app_language} app #{app} on #{HelperFunctions.local_ip}:#{app_true_port}")
          xmpp_ip = get_login.public_ip
          pid = HelperFunctions.run_app(app, app_true_port, @userappserver_private_ip, my_public, app_version, app_language, @port, xmpp_ip)
          pid_file_name = "#{APPSCALE_HOME}/.appscale/#{app}-#{app_true_port}.pid"
          HelperFunctions.write_file(pid_file_name, pid)
        }

        Nginx.reload
        Collectd.restart

        loop {
          add_instance_info = uac.add_instance(app, my_public, @port)
          Djinn.log_debug("Add instance returned #{add_instance_info}")
          break if add_instance_info == "true"
          sleep(5)
        }

        @port = @port + 1

        # now doing this at the real end so that the tools will
        # wait for the app to actually be running before returning
        done_uploading(app, app_path, @@secret)
      end

      Monitoring.restart if my_node.is_shadow?

      if @app_names.include?("none")
        @apps_loaded = @apps_loaded - ["none"]
        @app_names = @app_names - ["none"]
      end
        
      @apps_loaded << app
    }

    Djinn.log_debug("#{apps_to_load.size} apps loaded")  
  end

  def stop_appengine()
    Djinn.log_debug("Shutting down AppEngine")

    uac = UserAppClient.new(@userappserver_private_ip, @@secret)
    all_apps = uac.get_all_apps()
    my_public = my_node.public_ip

    Djinn.log_debug("all apps are [#{all_apps}]")
    app_list = all_apps.split(":")
    app_list = app_list - [app_list[0]] # first item is a dummy value, ____
    app_list.each { |app|
      app_is_enabled = uac.does_app_exist?(app)
      Djinn.log_debug("[stop appengine] is app #{app} enabled? #{app_is_enabled}")
      if app_is_enabled == "true"
        app_data = uac.get_app_data(app)
        Djinn.log_debug("[stop appengine] app data for #{app} is [#{app_data}]")
        hosts = app_data.scan(/\nhosts:([\d\.|:]+)\n/).flatten.to_s.split(":")
        ports = app_data.scan(/\nports: ([\d|:]+)\n/).flatten.to_s.split(":")
        # TODO : make sure that len hosts = len ports
        hosts.each_index { |i|
          if hosts[i] == my_public
            Djinn.log_debug("[stop appengine] deleting instance for app #{app} at #{hosts[i]}:#{ports[i]}")
            uac.delete_instance(app, hosts[i], ports[i])
          end
        }
        Djinn.log_debug("finished deleting instances for app #{app}")
        #Djinn.log_run("rm -fv /etc/nginx/#{app}.conf")
        Nginx.reload
      else
        Djinn.log_debug("app #{app} wasnt enabled, skipping it")
      end
    }

    @app_names = []
    @apps_loaded = []
    @restored = false
  
    Djinn.log_debug(`pkill -f dev_appserver`)
    Djinn.log_debug(`pkill -f DevAppServerMain`)
  end

  def copy_app_to_local(appname)
    app_dir = "/var/apps/#{appname}/app"
    app_path = "#{app_dir}/#{appname}.tar.gz"

    if File.exists?(app_path)
      Djinn.log_debug("I already have a copy of app #{appname} - won't grab it remotely")
      return
    else
      Djinn.log_debug("I don't have a copy of app #{appname} - will grab it remotely")
    end

    nodes_with_app = []
    loop {
      nodes_with_app = ZKInterface.get_app_hosters(appname)
      break unless nodes_with_app.empty?
      Djinn.log_debug("No nodes currently have a copy of app #{appname}, waiting...")
      sleep(5)
    }

    nodes_with_app.each { |node|
      ssh_key = node.ssh_key
      ip = node.public_ip
      Djinn.log_run("scp -o StrictHostkeyChecking=no -i #{ssh_key} #{ip}:#{app_path} #{app_path}")
      # TODO: check for failure here
      Djinn.log_debug("Got a copy of #{appname} from #{ip}")
      break
    }
  end

  def start_xmpp_for_app(app, app_language)
    # create xmpp account for the app
    # for app named baz, this translates to baz@login_ip

    login_ip = get_login.public_ip
    login_uac = UserAppClient.new(login_ip, @@secret)
    xmpp_user = "#{app}@#{login_ip}"
    xmpp_pass = HelperFunctions.encrypt_password(xmpp_user, @@secret)
    login_uac.commit_new_user(xmpp_user, xmpp_pass, "app")

    Djinn.log_debug("Created user [#{xmpp_user}] with password [#{@@secret}] and hashed password [#{xmpp_pass}]")

    if Ejabberd.does_app_need_receive?(app, app_language)
      cmd = "python #{APPSCALE_HOME}/AppController/xmpp_receiver.py #{app} #{login_ip} #{@@secret}"
      Kernel.system("#{cmd} &")

      pid = "ps ax | grep '#{cmd}' | grep -v grep | awk '{print $1}'"
      pid_file_name = "#{APPSCALE_HOME}/.appscale/xmpp-#{app}.pid"
      HelperFunctions.write_file(pid_file_name, pid)
    end
  end
end
