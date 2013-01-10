#!/usr/bin/ruby -w

# Imports within Ruby's standard libraries
require 'monitor'
require 'net/http'
require 'openssl'
require 'socket'
require 'soap/rpc/driver'
require 'syslog'
require 'yaml'


# Imports for RubyGems
require 'rubygems'
require 'httparty'
require 'json'
require 'right_aws'
require 'zookeeper'


# Imports for AppController libraries
$:.unshift File.join(File.dirname(__FILE__), "lib")
require 'app_controller_client'
require 'app_manager_client'
require 'blobstore'
require 'custom_exceptions'
require 'ejabberd'
require 'error_app'
require 'collectd'
require 'cron_helper'
require 'godinterface'
require 'haproxy'
require 'helperfunctions'
require 'infrastructure_manager_client'
require 'neptune_manager_client'
require 'pbserver'
require 'nginx'
require 'rabbitmq'
require 'repo'
require 'user_app_client'
require 'zkinterface'

NO_OUTPUT = false

# This lock makes it so that global variables related to apps are not updated 
# concurrently, preventing race conditions. 
APPS_LOCK = Monitor.new()


$:.unshift File.join(File.dirname(__FILE__), "..", "AppDB", "zkappscale")
require "zookeeper_helper"

# A HTTP client that assumes that responses returned are JSON, and automatically
# loads them, returning the result. Raises a NoMethodError if the host/URL is 
# down or otherwise unreachable.
class JSONClient
  include HTTParty

  # Assume the response is JSON and load it accordingly.
  parser(
    Proc.new do |body, format|
      JSON.load(body)
    end
  )
end


# The string that should be returned to the caller if they call a publicly
# exposed SOAP method but provide an incorrect secret.
BAD_SECRET_MSG = "false: bad secret"


# The location on the local file system where we store information about
# where ZooKeeper clients are located, used to backup and restore 
# AppController information.
ZK_LOCATIONS_FILE = "/etc/appscale/zookeeper_locations.json"


# Djinn (interchangeably known as 'the AppController') automatically
# configures and deploys all services for a single node. It relies on other
# Djinns or the AppScale Tools to tell it what services (roles) it should
# be hosting, and exposes these methods via a SOAP interface (as is provided
# in DjinnServer).
class Djinn
  # An Array of DjinnJobData objects, each of which containing information about
  # a node in the currently running AppScale deployment.
  attr_accessor :nodes
  

  # A Hash containing all the parameters needed to configure any service
  # on any node. At a minimum, this is all the information from the AppScale
  # Tools, including information about database parameters and the roles
  # for all nodes.
  attr_accessor :creds
  

  # An Array of Strings, each of which corresponding to the name of an App
  # Engine app that should be loaded.
  attr_accessor :app_names
  
  
  # An Array of Strings, each of which corresponding to the name of an App
  # Engine app that has been loaded on this node.
  attr_accessor :apps_loaded


  # A boolean that is used to let remote callers know when this AppController
  # is done initializing itself, but not necessarily done starting or 
  # stopping roles.
  attr_accessor :done_initializing


  # A boolean that is used to let remote callers know when this AppController
  # is done starting all the services it is responsible for.
  attr_accessor :done_loading


  # The port that nginx will listen to for the next App Engine app that is
  # uploaded into the system.
  attr_accessor :nginx_port
  

  # The port that haproxy will listen to for the next App Engine app that is
  # uploaded into the system.
  attr_accessor :haproxy_port
  
  
  # The public IP address (or FQDN) that the UserAppServer can be found at,
  # initally set to a dummy value to tell callers not to use it until a real
  # value is set.
  attr_accessor :userappserver_public_ip 


  # The public IP address (or FQDN) that the UserAppServer can be found at,
  # initally set to a dummy value to tell callers not to use it until a real
  # value is set.
  attr_accessor :userappserver_private_ip
  
  
  # The human-readable state that this AppController is in.
  attr_accessor :state
  
 
  # A boolean that is used to let remote callers start the shutdown process
  # on this AppController, which will cleanly shut down and terminate all
  # services on this node.
  attr_accessor :kill_sig_received 


  # An Integer that indexes into @nodes, to return information about this node.
  attr_accessor :my_index
  
  
  # The number of nodes that are running in this AppScale deployment.
  # TODO(cgb): It would seem like we could always calculate this with
  # @nodes.length, so replace it accordingly.
  attr_accessor :total_boxes
  
  
  # The number of dev_appservers that should run for every App Engine
  # application.
  attr_accessor :num_appengines
  
  
  # A boolean that indicates if we are done restoring state from a previously
  # running AppScale deployment.
  attr_accessor :restored


  # A Hash that maps information about each successfully completed Neptune
  # job to information about the job, that will one day be used to provide
  # hints to future jobs about how to schedule them optimally.
  attr_accessor :neptune_jobs
  
  
  # An Array of DjinnJobData objects that correspond to nodes used for
  # Neptune computation. Nodes are reclaimed every hour if they are not in
  # use (to avoid being charged for them for another hour).
  attr_accessor :neptune_nodes
  
  
  # A Hash that lists the status of each Google App Engine API made available
  # within AppScale. Keys are the names of the APIs (e.g., memcache), and
  # values are the statuses of those APIs (e.g., running).
  attr_accessor :api_status


  # For Babel jobs via Neptune, we keep a list of queues that may have tasks
  # stored for execution, as well as the parameters needed to execute them
  # (e.g., input location, output location, cloud credentials).
  attr_accessor :queues_to_read

  # An integer timestamp that corresponds to the last time this AppController
  # has updated @nodes, which we use to compare with a similar timestamp in
  # ZooKeeper to see when data in @nodes has changed on other nodes.
  attr_accessor :last_updated


  # A Hash that contains information about each Google App Engine application
  # running in this deployment. It includes information about the nginx and
  # haproxy ports the app uses, as well as the language the app is written
  # in.
  attr_accessor :app_info_map


  # A lock that should be used whenever we modify internal state that can be
  # modified by more than one thread at a time.
  attr_accessor :state_change_lock


  # The port that the AppController runs on by default
  SERVER_PORT = 17443


  # The port that SSH connections are hosted over, by default.
  SSH_PORT = 22


  # A boolean that should be used when we are waiting for a specific port
  # to open, and only if that port needs SSL to talk over it.
  USE_SSL = true


  # A boolean that indicates whether or not we should turn the firewall on,
  # and continuously keep it on. Should definitely be on for releases, and
  # on whenever possible.
  FIREWALL_IS_ON = true


  # The location on the local filesystem where AppScale-related configuration
  # files are written to.
  CONFIG_FILE_LOCATION = "/etc/appscale"


  # The location on the local filesystem where the AppController writes
  # information about Neptune jobs that have finished. One day this information
  # may be used to more intelligently schedule jobs on the fly.
  NEPTUNE_INFO = "#{CONFIG_FILE_LOCATION}/neptune_info.txt"


  # The location on the local filesystem where the AppController writes
  # information about the status of App Engine APIs, which the AppLoadBalancer
  # will read and display to users.
  HEALTH_FILE = "#{CONFIG_FILE_LOCATION}/health.json"


  # The location on the local filesystem where the AppController periodically
  # writes its state to, and recovers its state from if it crashes.
  STATE_FILE = "#{CONFIG_FILE_LOCATION}/appcontroller-state.json"


  APPSCALE_HOME = ENV['APPSCALE_HOME']


  # The message that we display to the user if they call a SOAP-accessible
  # function with a malformed input (e.g., of the wrong class or format).
  BAD_INPUT_MSG = JSON.dump({'success' => false, 'message' => 'bad input'})


  # The message to display to users if they try to add nodes to a one node
  # deployment, which currently is not supported.
  CANT_SCALE_FROM_ONE_NODE = JSON.dump({
    'success' => false, 
    'message' => "can't scale up from a one node deployment"
  })


  # The message that we display to the user if they want to scale up services
  # in an Xen/KVM deployment but don't have enough open nodes to do so.
  NOT_ENOUGH_OPEN_NODES = JSON.dump({'success' => false, 
    'message' => 'not enough open nodes'})


  # The options that should be used when invoking wget, so that the
  # AppController can automatically probe a site to see if it's up.
  WGET_OPTIONS = "--tries=1000 --no-check-certificate -q -O /dev/null"


  # How often we should attempt to increase the number of AppServers on a
  # given node.
  SCALEUP_TIME_THRESHOLD = 60  # seconds
  
  
  # How often we should attempt to decrease the number of AppServers on a
  # given node.
  SCALEDOWN_TIME_THRESHOLD = 300  # seconds


  # The size of the rotating buffers that we use to keep information on
  # the request rate and number of enqueued requests.
  NUM_DATA_POINTS = 10


  # The minimum number of AppServers (for all applications) that should be run
  # on this node.
  MIN_APPSERVERS_ON_THIS_NODE = 1


  # The maximum number of AppServers (for all applications) that should be run
  # on this node.
  MAX_APPSERVERS_ON_THIS_NODE = 10


  # The position in the haproxy profiling information where the name of
  # the service (e.g., the frontend or backend) is specified.
  SERVICE_NAME_INDEX = 1


  # The position in the haproxy profiling information where the number of
  # enqueued requests is specified.
  REQ_IN_QUEUE_INDEX = 2


  # The position in the haproxy profiling information where the request rate
  # is specified.
  REQ_RATE_INDEX = 46

  
  # Scales up the number of AppServers used to host an application if the
  # request rate rises above this value.
  SCALEUP_REQUEST_RATE_THRESHOLD = 5


  # Scales down the number of AppServers used to host an application if the
  # request rate falls below this value.
  SCALEDOWN_REQUEST_RATE_THRESHOLD = 2


  # The minimum number of requests that have to sit in haproxy's wait queue for
  # an App Engine application before we will scale up the number of AppServers 
  # that serve that application.
  SCALEUP_QUEUE_SIZE_THRESHOLD = 5


  # The path to the file where we will store information about AppServer
  # scaling decisions.
  AUTOSCALE_LOG_FILE = "/var/log/appscale/autoscale.log"
  

  # CPU limits that determine when to stop adding AppServers on a node. Because
  # AppServers in different languages consume different amounts of CPU, set
  # different limits per language.
  MAX_CPU_FOR_APPSERVERS = {'python' => 80.00, 'python27' => 90.00, 'java' => 75.00, 'go' => 70.00}


  # Memory limits that determine when to stop adding AppServers on a node. 
  # Because AppServers in different languages consume different amounts of 
  # memory, set different limits per language.
  MAX_MEM_FOR_APPSERVERS = {'python' => 90.00, 'python27' => 90.00, 'java' => 95.00, 'go' => 90.00}

  # Creates a new Djinn, which holds all the information needed to configure
  # and deploy all the services on this node.
  def initialize()
    # The password, or secret phrase, that is required for callers to access
    # methods exposed via SOAP.
    @@secret = HelperFunctions.get_secret()

    @nodes = []
    @my_index = nil
    @creds = {}
    @app_names = []
    @apps_loaded = []
    @kill_sig_received = false
    @done_initializing = false
    @done_loading = false
    @nginx_port = Nginx::START_PORT
    @haproxy_port = HAProxy::START_PORT
    @appengine_port = 20000
    @userappserver_public_ip = "not-up-yet"
    @userappserver_private_ip = "not-up-yet"
    @state = "AppController just started"
    @total_boxes = 0
    @num_appengines = 1
    @restored = false
    @neptune_jobs = {}
    @neptune_nodes = []
    @api_status = {}
    @queues_to_read = []
    @last_updated = 0
    @state_change_lock = Monitor.new()
    @app_info_map = {}

    @scaling_in_progress = false
    @last_decision = {}
    @initialized_apps = {}
    @req_rate = {}
    @req_in_queue = {}
  end


  # A SOAP-exposed method that callers can use to determine if this node
  # has received information from another node and is starting up.
  def is_done_initializing(secret)
    if valid_secret?(secret)
      return @done_initializing
    else
      return BAD_SECRET_MSG
    end
  end


  # A SOAP-exposed method that callers use to determine if this node has
  # finished starting all the roles it should run when it initially starts.
  def is_done_loading(secret)
    if valid_secret?(secret)
      return @done_loading
    else
      return BAD_SECRET_MSG
    end
  end


  # A SOAP-exposed method that callers can use to get information about what
  # roles each node in the AppScale deployment are running.
  def get_role_info(secret)
    if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end

    all_nodes = []
    @nodes.each { |node|
      all_nodes << node.to_hash()
    }

    return all_nodes
  end


  def kill(secret)
    if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end
    @kill_sig_received = true
    
    if is_hybrid_cloud? 
      Thread.new {
        Kernel.sleep(5)
        HelperFunctions.terminate_hybrid_vms(creds)
      }
    elsif is_cloud?
      Thread.new {
        Kernel.sleep(5)
        infrastructure = creds["infrastructure"]
        keyname = creds["keyname"]
        HelperFunctions.terminate_all_vms(infrastructure, keyname)
      }
    else
      # in xen/kvm deployments we actually want to keep the boxes
      # turned on since that was the state they started in

      stop_ejabberd if my_node.is_login?
      Repo.stop if my_node.is_shadow? or my_node.is_appengine?

      jobs_to_run = my_node.jobs
      commands = {
        "load_balancer" => "stop_load_balancer",
        "appengine" => "stop_appengine",
        "db_master" => "stop_db_master",
        "db_slave" => "stop_db_slave",
        "zookeeper" => "stop_zookeeper"
      }

      my_node.jobs.each { |job|
        if commands.include?(job)
          Djinn.log_debug("About to run [#{commands[job]}]")
          send(commands[job].to_sym)
        else
          Djinn.log_debug("Unable to find command for job #{job}. Skipping it.")
        end
      }

      if has_soap_server?(my_node)
        stop_soap_server
        stop_pbserver
      end
     
      stop_app_manager_server
      stop_neptune_manager
      stop_infrastructure_manager
    end

    GodInterface.shutdown
    FileUtils.rm_rf(STATE_FILE)
    return "OK"  
  end
 

  # Validates and sets the instance variables that Djinn needs before it can
  # begin configuring and deploying services on a given node (and if it is the
  # first Djinn, starting up the other Djinns).
  def set_parameters(djinn_locations, database_credentials, app_names, secret)
    if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end

    Djinn.log_debug("Djinn locations class: #{djinn_locations.class}")
    Djinn.log_debug("DB Credentials class: #{database_credentials.class}")
    Djinn.log_debug("Apps to load class: #{app_names.class}")

    if djinn_locations.class != Array
      msg = "Error: djinn_locations wasn't an Array, but was a " +
        djinn_locations.class.to_s
      Djinn.log_debug(msg)
      return msg
    end

    if database_credentials.class != Array
      msg = "Error: database_credentials wasn't an Array, but was a " +
        database_credentials.class.to_s
      Djinn.log_debug(msg)
      return msg
    end

    if app_names.class != Array
      msg = "Error: app_names wasn't an Array, but was a " + 
        app_names.class.to_s
      Djinn.log_debug(msg)
      return msg
    end

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

    Djinn.log_debug("Parameters were valid")

    keyname = possible_credentials["keyname"]
    @nodes = Djinn.convert_location_array_to_class(djinn_locations, keyname)
    @creds = possible_credentials
    @app_names = app_names
    
    convert_fqdns_to_ips
    @creds = sanitize_credentials

    Djinn.log_debug("(set_parameters) locations: #{@nodes.join(', ')}")
    Djinn.log_debug("(set_parameters) DB Credentials: #{HelperFunctions.obscure_creds(@creds).inspect}")
    Djinn.log_debug("Apps to load: #{@app_names.join(', ')}")

    find_me_in_locations
    if @my_index.nil?
      return "Error: Couldn't find me in the node map"
    end
    Djinn.log_debug("(set_parameters) My index = #{@my_index}")

    ENV['EC2_URL'] = @creds['ec2_url']
    
    return "OK"
  end


  # Validates and sets the list of applications that should be loaded on this
  # node.
  def set_apps(app_names, secret)
    if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end

    if app_names.class != Array
      return "app names was not an Array but was a #{app_names.class}"
    end

    @app_names = app_names
    return "App names is now #{@app_names.join(', ')}"
  end

  # Gets the status of the current node in the AppScale deployment
  # 
  # Args:
  #   secret: The shared key for authentication
  # Returns:
  #   A string with the current node's status
  # 
  def status(secret)
    if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end

    stats = get_stats(secret)

    stats_str = <<-STATUS
    Currently using #{stats['cpu']} Percent CPU and #{stats['memory']} Percent Memory
    Hard disk is #{stats['disk']} Percent full
    Is currently: #{stats['roles'].join(', ')}
    Database is at #{stats['db_location']}
    Is in cloud: #{stats['cloud']}
    Current State: #{stats['state']}
    STATUS

    if my_node.is_appengine?
      app_names = []
      stats['apps'].each { |k, v|
        app_names << k
      }

      stats_str << "    Hosting the following apps: #{app_names.join(', ')}\n"

      stats['apps'].each { |app_name, is_loaded|
        next if !is_loaded
        next if app_name == "none"
        if !@app_info_map[app_name]['appengine'].nil?
          stats_str << "    The number of AppServers for app #{app_name} is: " +
            "#{@app_info_map[app_name]['appengine'].length}\n"
        end
      }
    end
 
    return stats_str
  end

  def get_stats(secret)
    if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end

    usage = HelperFunctions.get_usage
    mem = sprintf("%3.2f", usage['mem'])

    jobs = my_node.jobs or ["none"]
    # don't use an actual % below, or it will cause a string format exception
    stats = {
      'ip' => my_node.public_ip,
      'cpu' => usage['cpu'],
      'memory' => mem,
      'disk' => usage['disk'],
      'roles' => jobs,
      'db_location' => @userappserver_public_ip,
      'cloud' => my_node.cloud,
      'state' => @state
    }

    stats['apps'] = {}
    APPS_LOCK.synchronize {
      @app_names.each { |name|
        stats['apps'][name] = @apps_loaded.include?(name)
      }
    }
    return stats
  end

  # Removes an application and stops all AppServers hosting this application.
  #
  # Args:
  #   app_name: The application to stop
  #   secret: Shared key for authentication
  #
  def stop_app(app_name, secret)
    if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end

    app_name.gsub!(/[^\w\d\-]/, "")
    Djinn.log_debug("(stop_app): Shutting down app named [#{app_name}]")
    result = ""
    Djinn.log_run("rm -rf /var/apps/#{app_name}")
   
    # app shutdown process can take more than 30 seconds
    # so run it in a new thread to avoid 'execution expired'
    # error messages and have the tools poll it 
    Thread.new {
      # Tell other nodes to shutdown this application
      if @app_names.include?(app_name) and !my_node.is_appengine?
        @nodes.each { |node|
          next if node.private_ip == my_node.private_ip
          if node.is_appengine? or node.is_login?
            ip = node.private_ip
            acc = AppControllerClient.new(ip, @@secret)
            result = acc.stop_app(app_name)
            Djinn.log_debug("(stop_app): Removing application #{app_name} --- #{ip} returned #{result} (#{result.class})")
          end
        }
      end

      # Contact the soap server and remove the application
      if (@app_names.include?(app_name) and !my_node.is_appengine?) or @nodes.length == 1
        ip = HelperFunctions.read_file("#{CONFIG_FILE_LOCATION}/masters")
        uac = UserAppClient.new(ip, @@secret)
        result = uac.delete_app(app_name)
        Djinn.log_debug("(stop_app) Delete app: #{ip} returned #{result} (#{result.class})")
      end
     
      # may need to stop XMPP listener
      if my_node.is_login? 
        pid_files = HelperFunctions.shell("ls #{CONFIG_FILE_LOCATION}/xmpp-#{app_name}.pid").split
        unless pid_files.nil? # not an error here - XMPP is optional
          pid_files.each { |pid_file|
            pid = HelperFunctions.read_file(pid_file)
            Djinn.log_run("kill -9 #{pid}")
          }

          result = "true"
        end
      end    

      if my_node.is_appengine?
        app_manager = AppManagerClient.new()
        Djinn.log_debug("(stop_app) Calling AppManager for app #{app_name}")
        if !app_manager.stop_app(app_name)
          Djinn.log_debug("(stop_app) ERROR: Unable to stop app #{app_name}") 
        else
          Djinn.log_debug("(stop_app) AppManager shut down app #{app_name}")
        end

        Nginx.remove_app(app_name)
        Collectd.remove_app(app_name)
        HAProxy.remove_app(app_name)
        Nginx.reload
        Collectd.restart
        ZKInterface.remove_app_entry(app_name, my_node.serialize)

        # If this node has any information about AppServers for this app,
        # clear that information out.
        if !@app_info_map[app_name].nil?
          @app_info_map.delete(app_name)
        end

        result = "true"
      end
      APPS_LOCK.synchronize {
        @apps_loaded = @apps_loaded - [app_name]    
        @app_names = @app_names - [app_name]

        if @apps_loaded.empty?
          @apps_loaded << "none"
        end

        if @app_names.empty?
          @app_names << "none"
        end
      }
    }

    return "true"
  end

  def update(app_names, secret)
    if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end
    
    apps = @app_names - app_names + app_names
    
    @nodes.each_index { |index|
      ip = @nodes[index].private_ip
      acc = AppControllerClient.new(ip, @@secret)
      result = acc.set_apps(apps)
      Djinn.log_debug("Update #{ip} returned #{result} (#{result.class})")
      @everyone_else_is_done = false if !result
    }

    # now that another app is running we can take out 'none' from the list
    # if it was there (e.g., run-instances with no app given)
    @app_names = @app_names - ["none"]
    
    return "OK"
  end

  def get_all_public_ips(secret)
    if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end

    public_ips = []
    @nodes.each { |node|
      public_ips << node.public_ip
    }
    Djinn.log_debug("All public ips are [#{public_ips.join(', ')}]")
    return public_ips
  end

  def job_start(secret)
    if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end

    start_infrastructure_manager

    if restore_appcontroller_state 
      parse_creds
    else
      erase_old_data
      wait_for_data
      parse_creds
      change_job
    end

    start_neptune_manager
    
    @done_loading = true
    write_our_node_info
    wait_for_nodes_to_finish_loading(@nodes)

    while !@kill_sig_received do
      @state = "Done starting up AppScale, now in heartbeat mode"
      write_database_info
      write_zookeeper_locations
      write_neptune_info 
      update_api_status

      update_local_nodes

      if my_node.is_shadow?
        Djinn.log_debug("my node is #{my_node}")

        # Since we now backup state to ZK, don't make everyone do it.
        # The Shadow has the most up-to-date info, so let it handle this
        backup_appcontroller_state
      end

      # Login nodes host the AppLoadBalancer app, which has links to each
      # of the apps running in AppScale. Update the files it reads to
      # reflect the most up-to-date info.
      if my_node.is_login?
        @nodes.each { |node|
          get_status(node)
        }
      end

      #ensure_all_roles_are_running

      # TODO: consider only calling this if new apps are found
      start_appengine
      scale_appservers
      Kernel.sleep(20)
    end
  end


  # Starts the InfrastructureManager service on this machine, which exposes
  # a SOAP interface by which we can dynamically add and remove nodes in this
  # AppScale deployment.
  def start_infrastructure_manager
    if HelperFunctions.is_port_open?("localhost", 
      InfrastructureManagerClient::SERVER_PORT, HelperFunctions::USE_SSL)

      Djinn.log_debug("InfrastructureManager is already running locally - " +
        "don't start it again.")
      return
    end

    start_cmd = "python2.6 #{APPSCALE_HOME}/InfrastructureManager/infrastructure_manager_service.py"
    stop_cmd = "pkill -9 infrastructure_manager_service"
    port = [InfrastructureManagerClient::SERVER_PORT]
    env = {
      'APPSCALE_HOME' => APPSCALE_HOME,
      'EC2_HOME' => ENV['EC2_HOME'],
      'JAVA_HOME' => ENV['JAVA_HOME']
    }

    GodInterface.start(:iaas_manager, start_cmd, stop_cmd, port, env)
    Djinn.log_debug("Started InfrastructureManager successfully!")
  end


  def stop_infrastructure_manager
    Djinn.log_debug("Stopping InfrastructureManager")
    GodInterface.stop(:iaas_manager)
  end


  # Starts the NeptuneManager service on this machine, which exposes
  # a SOAP interface by which we can run programs in arbitrary languages 
  # in this AppScale deployment.
  def start_neptune_manager
    write_cloud_info()

    if HelperFunctions.is_port_open?("localhost", 
      NeptuneManagerClient::SERVER_PORT, HelperFunctions::USE_SSL)

      Djinn.log_debug("NeptuneManager is already running locally - " +
        "don't start it again.")
      return
    end

    start_cmd = "ruby #{APPSCALE_HOME}/Neptune/neptune_manager_server.rb"
    stop_cmd = "pkill -9 neptune_manager_server"
    port = [NeptuneManagerClient::SERVER_PORT]
    env_vars = {
      'APPSCALE_HOME' => APPSCALE_HOME,
      'DATABASE_USED' => @creds['table']
    }

    GodInterface.start(:neptune_manager, start_cmd, stop_cmd, port, env_vars)
    Djinn.log_debug("Started NeptuneManager successfully!")
  end


  def write_cloud_info()
    cloud_info = {
      'is_cloud?' => is_cloud?(), 
      'is_hybrid_cloud?' => is_hybrid_cloud?()
    }

    HelperFunctions.write_json_file("#{CONFIG_FILE_LOCATION}/cloud_info.json", cloud_info)
  end


  def stop_neptune_manager
    Djinn.log_debug("Stopping NeptuneManager")
    GodInterface.stop(:neptune_manager)
  end


  def get_online_users_list(secret)
    if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end

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
    if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end

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
    if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end

    hosters = ZKInterface.get_app_hosters(appname)
    hosters_w_appengine = []
    hosters.each { |node|
      hosters_w_appengine << node if node.is_appengine?
    }
 
    app_running = !hosters_w_appengine.empty?
    Djinn.log_debug("Is app #{appname} running? #{app_running}")
    return app_running
  end


  def add_role(new_role, secret)
    if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end

    # new roles may run indefinitely in the background, so don't block
    # on them - just fire and forget
    Thread.new {
      start_roles = new_role.split(":")
      start_roles.each { |role|
        # only start roles that we aren't already running
        # e.g., don't start_appengine if we already are, as this
        # will create two threads loading apps
        if my_node.jobs.include?(role)
          Djinn.log_debug("Already running role #{role}, not invoking again")
        else
          Djinn.log_debug("Adding and starting role #{role}")
          my_node.add_roles(role)
          send("start_#{role}".to_sym)
        end
      }
    }

    return "OK"
  end

  def remove_role(old_role, secret)
    if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end

    my_node.remove_roles(old_role)
    stop_roles = old_role.split(":")
    stop_roles.each { |role|
      Djinn.log_debug("Removing and stopping role #{role}")
      send("stop_#{role}".to_sym)
    }
    return "OK"
  end


  # This SOAP-exposed method dynamically scales up a currently running
  # AppScale deployment. For virtualized clusters, this assumes the
  # user has given us a list of IP addresses where AppScale has been
  # installed to, and for cloud deployments, we assume that the user
  # wants to use the same credentials as for their current deployment.
  # Args:
  #   ips_hash: A Hash that maps roles (e.g., appengine, database) to the
  #     IP address (in virtualized deployments) or unique identifier (in
  #     cloud deployments) that should run that role.
  #   secret: A String password that is used to authenticate the request
  #     to add nodes to the deployment.
  # Returns:
  #   BAD_SECRET_MSG: If the secret given does not match the secret for
  #     this AppScale deployment.
  #   BAD_INPUT_MSG: If ips_hash was not a Hash.
  #   Otherwise, returns a Hash that maps IP addresses to the roles that
  #     will be hosted on them (the inverse of ips_hash).
  def start_roles_on_nodes(ips_hash, secret)
    if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end

    if ips_hash.class != Hash
      Djinn.log_debug("Was expecting ips_hash to be a Hash, not " +
        "a #{ips_hash.class}")
      return BAD_INPUT_MSG
    end

    if @nodes.length == 1
      Djinn.log_debug("Can't scale up in a one node deployment.")
      return CANT_SCALE_FROM_ONE_NODE
    end

    Djinn.log_debug("Received a request to start additional roles on " +
      "new machines, with the following placement strategy: " +
      "#{ips_hash.inspect}")

    # ips_hash maps roles to IPs, but the internal format here maps
    # IPs to roles, so convert to the right format
    ips_to_roles = {}
    ips_hash.each { |role, ip_or_ips|
      if ip_or_ips.class == String
        ips = [ip_or_ips]  # just one IP
      else
        ips = ip_or_ips  # a list of IPs
      end

      ips.each { |ip|
        if ips_to_roles[ip].nil?
          ips_to_roles[ip] = []
        end
        ips_to_roles[ip] << role
      }
    }

    Thread.new {
      if is_cloud?
        start_new_roles_on_nodes_in_cloud(ips_to_roles)
      else
        start_new_roles_on_nodes_in_xen(ips_to_roles)
      end
    }

    return ips_to_roles
  end


  # This method acquires virtual machines from a cloud IaaS and adds them
  # to the currently running AppScale deployment. The new machines are then
  # assigned the roles given to us by the caller.
  # Args:
  #   ips_to_roles: A Hash that maps machines to the roles that should be
  #     started on them. As we have not yet spawned the machines, we do not
  #     have IP addresses for them, so any unique identifier can be used in
  #     lieu of IP addresses.
  # Returns:
  #   An Array of Strings, where each String contains information about the
  #     public IP address, private IP address, and roles that the new machines
  #     have taken on.
  def start_new_roles_on_nodes_in_cloud(ips_to_roles)
    Djinn.log_debug("Starting new roles in cloud with following info: " +
      "#{ips_to_roles.inspect}")

    keyname = @creds['keyname']
    num_of_vms = ips_to_roles.keys.length
    roles = ips_to_roles.values
    Djinn.log_debug("Need to spawn up #{num_of_vms} VMs")
    imc = InfrastructureManagerClient.new(@@secret)
    new_nodes_info = imc.spawn_vms(num_of_vms, @creds, roles, "cloud1")

    # initialize them and wait for them to start up
    Djinn.log_debug("info about new nodes is " +
      "[#{new_nodes_info.join(', ')}]")

    add_nodes(new_nodes_info)
    update_hosts_info()

    if my_node.is_login?
      regenerate_nginx_config_files()
    end

    return new_nodes_info
  end


  # This method takes a list of IP addresses that correspond to machines
  # with AppScale installed on them, that have passwordless SSH already
  # set up (presumably by appscale-add-instances). The machines are added
  # to the currently running AppScale deployment, and are then assigned
  # the roles given to us by the caller.
  # Args:
  #   ips_to_roles: A Hash that maps machines to the roles that should be
  #     started on them. Machines are uniquely identified by their IP
  #     address, which is assumed to be reachable from any node in the
  #     AppScale deployment.
  # Returns:
  #   An Array of Strings, where each String contains information about the
  #     public IP address, private IP address, and roles that the new machines
  #     have taken on.
  def start_new_roles_on_nodes_in_xen(ips_to_roles)
    Djinn.log_debug("Starting new roles in virt with following info: " +
      "#{ips_to_roles.inspect}")

    nodes_info = []
    keyname = @creds['keyname']
    ips_to_roles.each { |ip, roles|
      Djinn.log_debug("Will add roles #{roles.join(', ')} to new " +
        "node at IP address #{ip}")
      nodes_info << "#{ip}:#{ip}:#{roles.join(':')}:#{keyname}:cloud1"
    }

    add_nodes(nodes_info)
    update_hosts_info()

    if my_node.is_login?
      regenerate_nginx_config_files()
    end

    return nodes_info
  end


  # Starts the given roles by using open nodes, spawning new nodes, or some
  # combination of the two. 'nodes_needed' should be an Array, where each 
  # item is an Array of the roles to start on each node.
  def start_new_roles_on_nodes(nodes_needed, instance_type, secret)
     if !valid_secret?(secret)
      return BAD_SECRET_MSG
    end

    if nodes_needed.class != Array
      Djinn.log_debug("Was expecting nodes_needed to be an Array, not " +
        "a #{nodes_needed.class}")
      return BAD_INPUT_MSG
    end

    Djinn.log_debug("Received a request to acquire nodes with roles " +
      "#{nodes_needed.join(', ')}, with instance type #{instance_type} for " +
      "new nodes")

    vms_to_use = []
    ZKInterface.lock_and_run {
      num_of_vms_needed = nodes_needed.length

      @nodes.each { |node|
        if node.is_open?
          Djinn.log_debug("Will use node #{node} to run new roles")
          vms_to_use << node

          if vms_to_use.length == nodes_needed.length
            Djinn.log_debug("Only using open nodes to run new roles")
            break
          end
        end
      }

      vms_to_spawn = nodes_needed.length - vms_to_use.length
    
      if vms_to_spawn > 0 and !is_cloud?
        Djinn.log_debug("Still need #{vms_to_spawn} more nodes, but we " +
        "aren't in a cloud environment, so we can't acquire more nodes - " +
        "failing the caller's request.")
        return NOT_ENOUGH_OPEN_NODES
      end

      if vms_to_spawn > 0
        Djinn.log_debug("Need to spawn up #{vms_to_spawn} VMs")
        # start up vms_to_spawn vms as open
        imc = InfrastructureManagerClient.new(@@secret)
        new_nodes_info = imc.spawn_vms(vms_to_spawn, @creds, "open", "cloud1")

        # initialize them and wait for them to start up
        Djinn.log_debug("info about new nodes is " +
          "[#{new_nodes_info.join(', ')}]")
        add_nodes(new_nodes_info) 

        # add information about the VMs we spawned to our list, which may
        # already have info about the open nodes we want to use
        new_nodes = Djinn.convert_location_array_to_class(new_nodes_info,
          @creds['keyname'])
        vms_to_use << new_nodes
        vms_to_use.flatten!
      end
    }

    wait_for_nodes_to_finish_loading(vms_to_use)
    
    nodes_needed.each_index { |i|
      Djinn.log_debug("Adding roles #{nodes_needed[i].join(', ')} " +
        "to virtual machine #{vms_to_use[i]}")
      ZKInterface.add_roles_to_node(nodes_needed[i], vms_to_use[i])
    }

    wait_for_nodes_to_finish_loading(vms_to_use)

    return "OK"
  end


  # Given an Array of Strings containing information about machines with
  # AppScale installed on them, copies over deployment-specific files
  # and starts the AppController on them. Each AppController is then
  # instructed to start a specific set of roles, and join the existing
  # AppScale deployment.
  # Args:
  #   node_info: An Array of Strings, where each String has information
  #     about a node to add to the current AppScale deployment (e.g.,
  #     IP addresses, roles to run).
  def add_nodes(node_info)
    keyname = @creds['keyname']
    new_nodes = Djinn.convert_location_array_to_class(node_info, keyname)

    # Since an external thread can modify @nodes, let's put a lock around
    # it to prevent race conditions.
    @state_change_lock.synchronize {
      @nodes.concat(new_nodes)
      Djinn.log_debug("Changed nodes to #{@nodes}")
    }

    initialize_nodes_in_parallel(new_nodes)
  end


  # Cleans out temporary files that may have been written by a previous
  # AppScale deployment.
  def erase_old_data()
    Djinn.log_run("rm -rf /tmp/h*")
    Djinn.log_run("rm -f ~/.appscale_cookies")
    Djinn.log_run("rm -f #{APPSCALE_HOME}/.appscale/status-*")
    Djinn.log_run("rm -f #{APPSCALE_HOME}/.appscale/database_info")
    Djinn.log_run("rm -f /tmp/mysql.sock")

    Nginx.clear_sites_enabled
    Collectd.clear_sites_enabled
    HAProxy.clear_sites_enabled
    Djinn.log_run("echo '' > /root/.ssh/known_hosts") # empty it out but leave the file there
    CronHelper.clear_crontab
  end


  def wait_for_nodes_to_finish_loading(nodes)
    Djinn.log_debug("Waiting for nodes to finish loading")

    nodes.each { |node|
      if ZKInterface.is_node_done_loading?(node.public_ip)
        Djinn.log_debug("Node at #{node.public_ip} has finished loading.")
        next
      else
        Djinn.log_debug("Node at #{node.public_ip} has not yet finished " +
          "loading - will wait for it to finish.")
        Kernel.sleep(30)
        retry
      end
    }

    Djinn.log_debug("Nodes have finished loading")
    return
  end


  # This method is the nexus of all AppController logging - all messages get
  # sent to stdout immediately (which god will send to 
  # /var/log/appscale/controller-17443.log for tailing)
  # Important: Definitely do not log within the following three methods, as
  # it would cause an infinite loop.
  def self.log_debug(msg)
    time = Time.now
    self.log_to_stdout(time, msg)
  end


  # Logs and timestamps the given message to standard out.
  # TODO(cgb): Examine the performance impact of flushing stdout on every puts,
  # which we do to ensure that a message can be seen immediately.
  def self.log_to_stdout(time, msg)
    Kernel.puts "[#{time}] #{msg}"
    STDOUT.flush
  end

  
  # Logs and runs the given command, which is assumed to be trusted and thus
  # needs no filtering on our part. Obviously this should not be executed by
  # anything that the user could inject input into. Returns the return value
  # of the code we executed.
  def self.log_run(command)
    Djinn.log_debug(command)
    Djinn.log_debug(`#{command}`)
    return $?.to_i
  end


  # This method converts an Array of Strings (where each String contains all the
  # information about a single node) to an Array of DjinnJobData objects, which
  # provide convenience methods that make them easier to operate on than just
  # raw String objects.
  def self.convert_location_array_to_class(nodes, keyname)
    Djinn.log_debug("Keyname is of class #{keyname.class}")
    Djinn.log_debug("Keyname is #{keyname}")
    
    array_of_nodes = []
    nodes.each { |node|
      converted = DjinnJobData.new(node, keyname)
      array_of_nodes << converted
      Djinn.log_debug("Adding data " + converted.to_s)
    }
    
    return array_of_nodes
  end


  # This method is the opposite of the previous method, and is needed when an
  # AppController wishes to pass node information to other AppControllers via
  # SOAP (as SOAP accepts Arrays and Strings but not DjinnJobData objects).
  def self.convert_location_class_to_array(djinn_locations)
    if djinn_locations.class != Array
      raise Exception, "Locations should be an array"
    end
    
    djinn_loc_array = []
    djinn_locations.each { |location|
      djinn_loc_array << location.serialize
      Djinn.log_debug("Serializing data " + location.serialize)
    }
    
    return djinn_loc_array
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

    Djinn.log_debug("Couldn't find a shadow node in the following nodes: " +
      "#{@nodes.join(', ')}")

    abort("No shadow nodes found.")
  end

  def get_db_master
    @nodes.each { |node|
      return node if node.is_db_master?
    }

    abort("No db master nodes found.")
  end

  def self.get_db_master_ip
    masters_file = File.expand_path("#{CONFIG_FILE_LOCATION}/masters")
    master_ip = HelperFunctions.read_file(masters_file)
    return master_ip
  end

  def self.get_db_slave_ips
    slaves_file = File.expand_path("#{CONFIG_FILE_LOCATION}/slaves")
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
    Djinn.log_debug("DB IPs are [#{db_ips.join(', ')}]")
    if db_ips.include?(local_ip)
      # If there is a local database then use it
      local_ip
    else
      # Otherwise just select one randomly
      db_ips.sort_by { rand }[0]
    end
  end

  def get_all_appengine_nodes()
    ae_nodes = []
    @nodes.each { |node|
      if node.is_appengine?
        ae_nodes << node.private_ip
      end
    }
    return ae_nodes
  end

  def get_load_balancer_ip()
    @nodes.each { |node|
      if node.is_load_balancer?
        return node.public_ip
      end
    }
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
    if !is_cloud?
      @userappserver_public_ip = ip_addr
      @userappserver_private_ip = ip_addr
      Djinn.log_debug("\n\nUAServer is at [#{@userappserver_public_ip}]\n\n")
      return
    end
    
    keyname = @creds["keyname"]
    infrastructure = @creds["infrastructure"]    
 
    if is_hybrid_cloud?
      Djinn.log_debug("Getting hybrid ips with creds #{@creds.inspect}")
      public_ips, private_ips = HelperFunctions.get_hybrid_ips(@creds)
    else
      Djinn.log_debug("Getting cloud ips for #{infrastructure} with keyname " +
        "#{keyname}")
      public_ips, private_ips = HelperFunctions.get_cloud_ips(infrastructure, 
        keyname)
    end
 
    Djinn.log_debug("Public ips are #{public_ips.join(', ')}")
    Djinn.log_debug("Private ips are #{private_ips.join(', ')}")
    Djinn.log_debug("Looking for #{ip_addr}")

    public_ips.each_index { |index|
      node_public_ip = HelperFunctions.convert_fqdn_to_ip(public_ips[index])
      node_private_ip = HelperFunctions.convert_fqdn_to_ip(private_ips[index])

      if node_public_ip == ip_addr or node_private_ip == ip_addr
        # don't set the uaserver_public_ip to node_public_ip, as then the tools
        # won't be able to resolve that ip (it may be the same as the 
        # unresolvable private ip)
        Djinn.log_debug("Setting uaserver public ip to #{public_ips[index]}")
        Djinn.log_debug("Setting uaserver private ip to #{node_private_ip}")
        @userappserver_public_ip = public_ips[index]
        @userappserver_private_ip = node_private_ip
        return
      end
    }

    unable_to_convert_msg = "[get uaserver ip] Couldn't find out whether " +
      "#{ip_addr} was a public or private IP address. Public IPs are " +
      "[#{public_ips.join(', ')}], private IPs are [#{private_ips.join(', ')}]"

    Djinn.log_debug(unable_to_convert_msg)
    abort(unable_to_convert_msg)
  end
  
  def get_public_ip(private_ip)
    return private_ip unless is_cloud?
    
    keyname = @creds["keyname"]
    infrastructure = @creds["infrastructure"]    

    if is_hybrid_cloud?
      Djinn.log_debug("Getting hybrid ips with creds #{@creds.inspect}")
      public_ips, private_ips = HelperFunctions.get_hybrid_ips(@creds)
    else
      Djinn.log_debug("Getting cloud ips for #{infrastructure} with keyname " +
        "#{keyname}")
      public_ips, private_ips = HelperFunctions.get_cloud_ips(infrastructure, 
        keyname)
    end

    Djinn.log_debug("Public ips are #{public_ips.join(', ')}")
    Djinn.log_debug("Private ips are #{private_ips.join(', ')}")
    Djinn.log_debug("Looking for #{private_ip}")

    public_ips.each_index { |index|
      node_private_ip = HelperFunctions.convert_fqdn_to_ip(private_ips[index])
      node_public_ip = HelperFunctions.convert_fqdn_to_ip(public_ips[index])

      if node_private_ip == private_ip or node_public_ip == private_ip
        Djinn.log_debug("Mapped private ip #{private_ip} to public ip " +
          "#{public_ips[index]}")
        return public_ips[index]
      end
    }

    unable_to_convert_msg = "[get public ip] Couldn't convert private IP " +
      "#{private_ip} to a public address. Public IPs are " +
      "[#{public_ips.join(', ')}], private IPs are [#{private_ips.join(', ')}]"

    Djinn.log_debug(unable_to_convert_msg)
    abort(unable_to_convert_msg)  
  end

  def get_status(node)
    ip = node.private_ip
    ssh_key = node.ssh_key
    acc = AppControllerClient.new(ip, @@secret)

    if !acc.is_done_loading?()
      Djinn.log_debug("Node at #{ip} is not done loading yet - will try " +
        "again later.")
      return
    end

    result = acc.get_status(ok_to_fail=true)
    Djinn.log_debug("#{ip} returned [#{result}] - class is #{result.class}")

    if !result
      Djinn.log_debug("#{ip} returned false - is it not running?")
      return
    end

    status_file = "#{CONFIG_FILE_LOCATION}/status-#{ip}.json"
    stats = acc.get_stats()
    json_state = JSON.dump(stats) 
    HelperFunctions.write_file(status_file, json_state)

    if !my_node.is_login?
      login_ip = get_login.private_ip
      HelperFunctions.scp_file(status_file, status_file, login_ip, ssh_key)
    end

    # copy remote log over - handy for debugging
    local_log = "#{CONFIG_FILE_LOCATION}/logs/#{ip}.log"
    remote_log = "/tmp/*.log"

    FileUtils.mkdir_p("#{CONFIG_FILE_LOCATION}/logs/")
    Djinn.log_run("scp -o StrictHostkeyChecking=no -i #{ssh_key} #{ip}:#{remote_log} #{local_log}")
  end

  # TODO: add neptune file, which will have this function
  def run_neptune_in_cloud?(neptune_info)
    Djinn.log_debug("Activecloud_info = #{neptune_info}")
    return true if is_cloud? && !neptune_info["nodes"].nil?
    return true if !is_cloud? && !neptune_info["nodes"].nil? && !neptune_info["machine"].nil?
    return false
  end

  def write_database_info()
    table = @creds["table"]
    replication = @creds["replication"]
    keyname = @creds["keyname"]
    
    tree = { :table => table, :replication => replication, :keyname => keyname }
    db_info_path = "#{CONFIG_FILE_LOCATION}/database_info.yaml"
    File.open(db_info_path, "w") { |file| YAML.dump(tree, file) }
    
    num_of_nodes = @nodes.length
    HelperFunctions.write_file("#{CONFIG_FILE_LOCATION}/num_of_nodes", "#{num_of_nodes}\n")
    
    all_ips = []
    @nodes.each { |node|
      Djinn.log_debug("Letting #{node.private_ip} through the firewall")
      all_ips << node.private_ip
    }
    all_ips << "\n"
    HelperFunctions.write_file("#{CONFIG_FILE_LOCATION}/all_ips", all_ips.join("\n"))

    # Re-run the filewall script here since we just wrote the all_ips file
    if FIREWALL_IS_ON
      Djinn.log_run("bash #{APPSCALE_HOME}/firewall.conf")
    end
  end

  # Dumps all the info about Neptune jobs that have executed into a file,
  # that can be recovered later via load_neptune_info.
  def write_neptune_info(file_to_write=NEPTUNE_INFO)
    info = { "num_jobs" => @neptune_jobs.length }
    @neptune_jobs.each_with_index { |job, index|
      info["job_#{index}"] = job.to_hash
    }

    json_info = JSON.dump(info)
    HelperFunctions.write_file(file_to_write, json_info)
    return json_info
  end

  # Loads Neptune data (stored in JSON format) into the instance variable
  # @neptune_info. Used to restore Neptune job data from a previously
  # running AppScale instance.
  def load_neptune_info(file_to_load=NEPTUNE_INFO)
    if !File.exists?(file_to_load)
      Djinn.log_debug("No neptune data found - no need to restore")
      return
    end

    Djinn.log_debug("Restoring neptune data!")
    jobs_info = (File.open(file_to_load) { |f| f.read }).chomp
    jobs = []

    json_data = JSON.load(jobs_info)
    return if json_data.nil?
    num_jobs = json_data["num_jobs"]

    num_jobs.times { |i|
      info = json_data["job_#{i}"]
      this_job = NeptuneJobData.from_hash(info)
      job_name = this_job.name

      if @neptune_jobs[job_name].nil?
        @neptune_jobs[job_name] = [this_job]
      else
        @neptune_jobs[job_name] = [this_job]
      end
    }
  end

  def backup_appcontroller_state()
    Djinn.log_debug("Backing up AppController state to ZooKeeper")
    state = {'@@secret' => @@secret }

    instance_variables.each { |k|
      v = instance_variable_get(k)
      if k == "@nodes"
        v = Djinn.convert_location_class_to_array(@nodes)
      elsif k == "@my_index" or k == "@api_status"
        # Don't back up @my_index - it's a node-specific pointer that
        # indicates which node is "our node" and thus should be regenerated
        # via find_me_in_locations. Also don't worry about @api_status - it
        # can take up a lot of space and can easily be regenerated with new
        # data.
        next
      end

      state[k] = v
    }

    ZKInterface.write_appcontroller_state(state)
    Djinn.log_debug("Backed up AppController state to ZooKeeper")
  end


 
  # Restores the state of each of the instance variables that the AppController
  # holds by pulling it from ZooKeeper (previously populated by the Shadow
  # node, who always has the most up-to-date version of this data).
  def restore_appcontroller_state()
    Djinn.log_debug("Restoring AppController state from local file")

    if !File.exists?(ZK_LOCATIONS_FILE)
      Djinn.log_debug("No recovery data found - skipping recovery process")
      return false
    end

    zookeeper_data = HelperFunctions.read_json_file(ZK_LOCATIONS_FILE)
    json_state = {}
    zookeeper_data['locations'].each { |ip|
      begin
        Djinn.log_debug("Restoring AppController state from ZK at #{ip}")
        ZKInterface.init_to_ip(HelperFunctions.local_ip(), ip)
        json_state = ZKInterface.get_appcontroller_state()
      rescue Exception => e
        Djinn.log_debug("Saw exception of class #{e.class} from #{ip}, " +
          "trying next ZooKeeper node")
        next
      end

      Djinn.log_debug("Got data #{json_state.inspect} successfully from #{ip}")
      break
    }

    @@secret = json_state['@@secret']
    keyname = json_state['@creds']['keyname']

    json_state.each { |k, v|
      next if k == "@@secret"
      if k == "@nodes"
        v = Djinn.convert_location_array_to_class(v, keyname)
      elsif k == "@neptune_nodes"
        new_v = []

        v.each { |data|
          new_v << NeptuneJobData.from_hash(data)
        }        

        v = new_v
      end

      instance_variable_set(k, v)
    }

    # Now that we've restored our state, update the pointer that indicates
    # which node in @nodes is ours
    find_me_in_locations

    return true
  end


  # Updates the file that says where all the ZooKeeper nodes are
  # located so that this node has the most up-to-date info if it needs to
  # restore the data down the line.
  def write_zookeeper_locations
    zookeeper_data = { 'last_updated_at' => @last_updated,
      'locations' => []
    }

    @nodes.each { |node|
      if node.is_zookeeper?
        zookeeper_data['locations'] << node.public_ip
      end
    }

    Djinn.log_debug("Writing ZooKeeper backup data #{zookeeper_data.inspect}")
    HelperFunctions.write_json_file(ZK_LOCATIONS_FILE, zookeeper_data)
  end

 
  def update_api_status()
    if my_node.is_appengine?
      repo_host = my_node.private_ip
    else
      repo_host = get_shadow.private_ip
    end

    repo_url = "http://#{repo_host}:#{Repo::SERVER_PORT}/health/all"

    retries_left = 3
    begin
      response = Net::HTTP.get_response(URI.parse(repo_url))
      data = JSON.load(response.body)
      Djinn.log_debug("Update API was successful")
    rescue Exception => e
      Djinn.log_debug("Update API status on host #{repo_host} saw exception #{e.class}")
      data = {}

      if retries_left > 0
        Kernel.sleep(5)
        retries_left -= 1
        retry
      else
        Djinn.log_debug("Repo at #{repo_host} appears to be down - will " +
          "try again later.")
        return
      end
    end

    Djinn.log_debug("Data received is #{data.inspect}")

    majorities = {}

    data.each { |k, v|
      @api_status[k] = [] if @api_status[k].nil?
      @api_status[k] << v
      @api_status[k] = HelperFunctions.shorten_to_n_items(10, @api_status[k])
      majorities[k] = HelperFunctions.find_majority_item(@api_status[k])
    }

    json_state = JSON.dump(majorities)
    HelperFunctions.write_file(HEALTH_FILE, json_state)
  end

  # Backs up information about what this node is doing (roles, apps it is
  # running) to ZooKeeper, for later recovery or updates by other nodes.
  def write_our_node_info
    # Since more than one AppController could write its data at the same 
    # time, get a lock before we write to it.
    Djinn.log_debug("Getting ZK Lock")

    ZKInterface.lock_and_run {
      @last_updated = ZKInterface.add_ip_to_ip_list(my_node.public_ip)
      Djinn.log_debug("Saving our node's information to ZooKeeper")
      ZKInterface.write_node_information(my_node, @done_loading)
    }

    return
  end


  # Queries ZooKeeper to see if our local copy of @nodes is out of date and
  # should be regenerated with up to date data from ZooKeeper. If data on
  # our node has changed, this starts or stops the necessary roles.
  def update_local_nodes
    Djinn.log_debug("Getting ZK lock to update @nodes")

    ZKInterface.lock_and_run {
      # See if the ZooKeeper data is newer than ours - if not, don't
      # update anything and return.
      zk_ips_info = ZKInterface.get_ip_info()
      if zk_ips_info["last_updated"] <= @last_updated
        Djinn.log_debug("Latest ZooKeeper data does not have newer data " +
          "than us. ZK timestamp is #{zk_ips_info['last_updated']}, our" +
          " timestamp  is #{@last_updated}")
        return "NOT UPDATED"
      else
        Djinn.log_debug("Updating data from ZK. Our timestamp, " +
          "#{@last_updated}, was older than the ZK timestamp, " +
          "#{zk_ips_info['last_updated']}")
      end

      all_ips = zk_ips_info["ips"]
      new_nodes = []
      all_ips.each { |ip|
        new_nodes << DjinnJobData.deserialize(
          ZKInterface.get_job_data_for_ip(ip))
      }

      old_roles = my_node.jobs
      @nodes = new_nodes
      find_me_in_locations
      new_roles = my_node.jobs

      Djinn.log_debug("My new nodes are [#{@nodes.join(', ')}], and my new " +
        "node is #{my_node}")

      # Since we're about to possibly load and unload roles, set done_loading
      # for our node to false, so that other nodes don't erroneously send us
      # additional roles to do while we're in this state where lots of side
      # effects are happening.
      @done_loading = false
      ZKInterface.set_done_loading(my_node.public_ip, false)
   
      roles_to_start = new_roles - old_roles
      if !roles_to_start.empty?
        Djinn.log_debug("Need to start [#{roles_to_start.join(', ')}] " +
          "roles on this node")
        roles_to_start.each { |role|
          Djinn.log_debug("Starting role #{role}")
          send("start_#{role}".to_sym)
        }
      end

      roles_to_stop = old_roles - new_roles
      if !roles_to_stop.empty?
        Djinn.log_debug("Need to stop [#{roles_to_stop.join(', ')}] " +
          "roles on this node")
        roles_to_stop.each { |role|
          send("stop_#{role}".to_sym)
        }
      end

      # And now that we're done loading/unloading roles, set done_loading for
      # our node back to true.
      ZKInterface.set_done_loading(my_node.public_ip, true)
      @done_loading = true

      @last_updated = zk_ips_info['last_updated']
      Djinn.log_debug("Releasing ZK lock to update @nodes, and updated " +
        "@last_updated to #{@last_updated}")
    }

    return "UPDATED"
  end


  # Each node has a responsibility to check up on other nodes and make sure
  # they are still running, and if not, to remedy it somehow.
  # Returns an Array of the roles that this process started.
  def ensure_all_roles_are_running
    roles_to_add = []
    ZKInterface.lock_and_run {
      Djinn.log_debug("Seeing if other roles need to be taken over")

      ip_info = ZKInterface.get_ip_info()
      ip_info['ips'].each { |ip|
        Djinn.log_debug("Looking at roles for IP #{ip}")
        if !ZKInterface.is_node_done_loading?(ip)
          Djinn.log_debug("Node at IP #{ip} is not done loading yet, " +
            "skipping...")
          next
        end

        if ZKInterface.is_node_live?(ip)
          Djinn.log_debug("Node at IP #{ip} appears to be up, skipping...")
          next
        else
          Djinn.log_debug("Node at IP #{ip} has failed")
            failed_job_data = ZKInterface.get_job_data_for_ip(ip)
            failed_node = DjinnJobData.deserialize(failed_job_data)
            roles_to_add << failed_node.jobs

            instances_to_delete = ZKInterface.get_app_instances_for_ip(ip)
            uac = UserAppClient.new(@userappserver_private_ip, @@secret)
            instances_to_delete.each { |instance|
              Djinn.log_debug("Deleting app instance for app " +
                "#{instance['app_name']} located at #{instance['ip']}:" +
                "#{instance['port']}")
              uac.delete_instance(instance['app_name'], instance['ip'], 
                instance['port'])
            }

            remove_node_from_local_and_zookeeper(ip)
            Djinn.log_debug("Will recover [#{failed_node.jobs.join(', ')}] " +
              " roles that were being run by the failed node at #{ip}")
        end
      }

      if !roles_to_add.empty?
        start_new_roles_on_nodes(roles_to_add, @creds['instance_type'],
          @@secret)
      end

      Djinn.log_debug("Releasing ZK lock to see if other roles need to be " +
        "taken over")
    }

    return roles_to_add
  end


  # Removes information associated with the given IP address from our local
  # cache (@nodes) as well as the remote node storage mechanism (in ZooKeeper).
  def remove_node_from_local_and_zookeeper(ip)
    # First, remove our local copy
    index_to_remove = nil
    @nodes.each_index { |i|
      if @nodes[i].public_ip == ip
        index_to_remove = i
        break
      end
    }
    @nodes.delete(@nodes[index_to_remove])

    # Then remove the remote copy
    ZKInterface.remove_node_information(ip)
    @last_updated = ZKInterface.remove_ip_from_ip_list(ip)
  end


  def wait_for_data()
    loop {
      break if got_all_data
      if @kill_sig_received
        msg = "Received kill signal, aborting startup"
        Djinn.log_debug(msg)
        abort(msg)
      else
        Djinn.log_debug("Waiting for data from the load balancer or cmdline tools")
        Kernel.sleep(5)
      end
    }

  end

  def parse_creds
    got_data_msg = "Got data from another node! DLoc = " + \
      "#{@nodes.join(', ')}, #{HelperFunctions.obscure_creds(@creds).inspect}, AppsToLoad = " + \
      "#{@app_names.join(', ')}"
    Djinn.log_debug(got_data_msg)
        
    if @creds["appengine"]
      @num_appengines = Integer(@creds["appengine"])
    end

    Djinn.log_debug("Keypath is #{@creds['keypath']}, keyname is #{@creds['keyname']}")

    if !@creds["keypath"].empty?
      my_key_dir = "#{CONFIG_FILE_LOCATION}/keys/#{my_node.cloud}"
      my_key_loc = "#{my_key_dir}/#{@creds['keypath']}"
      Djinn.log_debug("Creating directory #{my_key_dir} for my ssh key #{my_key_loc}")
      FileUtils.mkdir_p(my_key_dir)
      Djinn.log_run("cp #{CONFIG_FILE_LOCATION}/ssh.key #{my_key_loc}")
    end
        
    if is_cloud?
      # for euca
      ENV['EC2_ACCESS_KEY'] = @creds["ec2_access_key"]
      ENV['EC2_SECRET_KEY'] = @creds["ec2_secret_key"]
      ENV['EC2_URL'] = @creds["ec2_url"]

      # for ec2
      cloud_keys_dir = File.expand_path("#{CONFIG_FILE_LOCATION}/keys/cloud1")
      ENV['EC2_PRIVATE_KEY'] = "#{cloud_keys_dir}/mykey.pem"
      ENV['EC2_CERT'] = "#{cloud_keys_dir}/mycert.pem"
    end

    write_database_info
    load_neptune_info
    write_neptune_info
  end

  def got_all_data()
    return false if @nodes == []
    return false if @creds == {}
    return false if @app_names == []
    return true
  end
  

  # If running in a cloud environment, we may be dealing with public and
  # private FQDNs instead of IP addresses, which makes it hard to find out
  # which node is our node (since we find our node by IP). This method
  # looks through all the nodes we currently know of and converts any private
  # FQDNs we see to private IPs.
  def convert_fqdns_to_ips()
    if is_cloud?
      Djinn.log_debug("In a cloud deployment, so converting FQDNs -> IPs")
    else
      Djinn.log_debug("Not in a cloud deployment, so not converting FQDNs -> IPs")
      return
    end

    if @creds["hostname"] =~ /#{FQDN_REGEX}/
      begin
        @creds["hostname"] = HelperFunctions.convert_fqdn_to_ip(@creds["hostname"])
      rescue Exception => e
        Djinn.log_debug("Failed to convert main hostname #{@creds['hostname']} to public, might want to look into this?")
      end
    end
    
    @nodes.each { |node|
      # Resolve the private FQDN to a private IP, but don't resolve the public
      # FQDN, as that will just resolve to the private IP.

      pri = node.private_ip
      if pri =~ /#{FQDN_REGEX}/
        begin
          node.private_ip = HelperFunctions.convert_fqdn_to_ip(pri)
        rescue Exception => e
          node.private_ip = node.public_ip
        end
      end

      Djinn.log_debug("This node has public ip #{node.public_ip} and private ip #{node.private_ip}")
    }
  end

 
  # Searches through @nodes to try to find out which node is ours. Strictly
  # speaking, we assume that our node is identifiable by private IP.
  def find_me_in_locations()
    @my_index = nil
    all_local_ips = HelperFunctions.get_all_local_ips()
    Djinn.log_debug("Seeing which node has a private IP that matches " +
      "our private IPs, which are: #{all_local_ips.join(', ')}")
    Djinn.log_debug("@nodes is #{@nodes.join(', ')}")
    @nodes.each_index { |index|
      Djinn.log_debug("Am I #{@nodes[index].private_ip}?")
      if all_local_ips.include?(@nodes[index].private_ip)
        Djinn.log_debug("Yes!")
        @my_index = index
        HelperFunctions.set_local_ip(@nodes[index].private_ip)
        return
      end
      Djinn.log_debug("No...")
    }
    Djinn.log_debug("I am lost, could not find my node") 
  end


  # Checks to see if the credentials given to us (a Hash) have all the keys that
  # other methods expect to see.
  def valid_format_for_credentials(possible_credentials)
    required_fields = ["table", "hostname", "ips", "keyname"]
    required_fields.each { |field|
      if !possible_credentials[field]
        return false
      end
    }

    return true
  end
  
  def sanitize_credentials()
    newcreds = {}
    @creds.each { |key, val|
      newkey = key.gsub(/[^\w\d_@-]/, "") unless key.nil?
      if newkey.include? "_key"
        newval = val.gsub(/[^\w\d\.\+:\/_-]/, "") unless val.nil?
      else
        newval = val.gsub(/[^\w\d\.:\/_-]/, "") unless val.nil?
      end
      newcreds[newkey] = newval
    }
    return newcreds
  end
    
  def change_job()
    my_data = my_node
    jobs_to_run = my_data.jobs
    
    if @creds['ips']
      @total_boxes = @nodes.length
    elsif @creds['min_images']
      @total_boxes = Integer(@creds['min_images'])
    end

    Djinn.log_debug("Pre-loop: #{@nodes.join('\n')}")
    if my_node.is_shadow?
      # TODO(cgb): Check to make sure the machines aren't already
      # initialized before attempting to start up AppScale on them.
      spawn_and_setup_appengine
      loop {
        Djinn.log_debug("Looping: #{@nodes.join('\n')}")
        @everyone_else_is_done = true
        @nodes.each_index { |index|
          unless index == @my_index
            ip = @nodes[index].private_ip
            acc = AppControllerClient.new(ip, @@secret)
            result = acc.is_done_initializing?()
            Djinn.log_debug("#{ip} returned #{result} (#{result.class})")
            @everyone_else_is_done = false unless result
          end
        }
        break if @everyone_else_is_done
        Djinn.log_debug("Waiting on other nodes to come online")
        Kernel.sleep(5)
      }
    end

    initialize_server
    # start_load_balancer 

    memcache_ips = []
    @nodes.each { |node|
      memcache_ips << node.private_ip if node.is_memcache?
    }

    Djinn.log_debug("Memcache servers will be at #{memcache_ips.join(', ')}")

    memcache_file = "#{CONFIG_FILE_LOCATION}/memcache_ips"
    memcache_contents = memcache_ips.join("\n")
    HelperFunctions.write_file(memcache_file, memcache_contents)

    write_apploadbalancer_location
    find_nearest_rabbitmq
    setup_config_files
    set_uaserver_ips 
    write_hypersoap

    # ejabberd uses uaserver for authentication
    # so start it after we find out the uaserver's ip

    start_ejabberd if my_node.is_login?

    @done_initializing = true

    # start zookeeper
    if my_node.is_zookeeper?
      configure_zookeeper(@nodes, @my_index)
      init = !(@creds.include?("keep_zookeeper_data"))
      start_zookeeper(init)
    end

    ZKInterface.init(my_node, @nodes)

    commands = {
      "load_balancer" => "start_load_balancer",
      "memcache" => "start_memcache",
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
        replication = @creds["replication"]
        Djinn.log_run("APPSCALE_HOME='#{APPSCALE_HOME}' MASTER_IP='localhost' LOCAL_DB_IP='localhost' python2.6 #{prime_script} #{replication}; echo $? > /tmp/retval")
        retval = `cat /tmp/retval`.to_i
        break if retval == 0
        Djinn.log_debug("Fail to create initial table. Retry #{retries} times.")
        Kernel.sleep(5)
        retries -= 1
      end
      if retval != 0
        Djinn.log_debug("Fail to create initial table. Could not startup AppScale.")
        exit(1)
      end
    end

    # All nodes have application managers
    start_app_manager_server

    # start soap server and pb server
    if has_soap_server?(my_node)
      @state = "Starting up SOAP Server and PBServer"
      start_pbserver
      start_soap_server
      HelperFunctions.sleep_until_port_is_open(HelperFunctions.local_ip, UserAppClient::SERVER_PORT)
    end

    start_blobstore_server if my_node.is_appengine?

    if my_node.is_rabbitmq_master?
      start_rabbitmq_master
    elsif my_node.is_rabbitmq_slave?
      start_rabbitmq_slave
    end

    # for neptune jobs, start a place where they can save output to
    # also, since repo does health checks on the app engine apis, start it up there too

    repo_ip = get_shadow.public_ip
    repo_private_ip = get_shadow.private_ip
    repo_ip = my_node.public_ip if my_node.is_appengine?
    repo_private_ip = my_node.private_ip if my_node.is_appengine?
    Repo.init(repo_ip, repo_private_ip,  @@secret)

    if my_node.is_shadow? or my_node.is_appengine?
      Repo.start(get_login.public_ip, @userappserver_private_ip)
    end

    # appengine is started elsewhere
  end

  def start_blobstore_server
    db_local_ip = @userappserver_private_ip
    BlobServer.start(db_local_ip, PbServer::LISTEN_PORT_NO_SSL)
    BlobServer.is_running(db_local_ip)

    return true
  end


  def start_rabbitmq_master
    RabbitMQ.start_master()      
    return true
  end


  def start_rabbitmq_slave
    # All slaves connect to the master to start
    master_ip = nil
    @nodes.each { |node|
      master_ip = node.private_ip if node.is_rabbitmq_master?
    }

    RabbitMQ.start_slave(master_ip)
    return true
  end

  # Starts the application manager which is a SOAP service in charge of 
  # starting and stopping applications.
  def start_app_manager_server
    @state = "Starting up AppManager"
    env_vars = {}
    start_cmd = ["/usr/bin/python2.6 #{APPSCALE_HOME}/AppManager/app_manager_server.py"]
    stop_cmd = "pkill -9 app_manager_server"
    port = [AppManagerClient::SERVER_PORT]
    GodInterface.start(:appmanagerserver, start_cmd, stop_cmd, port, env_vars)
  end

  def start_soap_server
    db_master_ip = nil
    @nodes.each { |node|
      db_master_ip = node.private_ip if node.is_db_master?
    }
    abort("db master ip was nil") if db_master_ip.nil?

    db_local_ip = @userappserver_private_ip
            
    table = @creds['table']

    env_vars = {}

    env_vars['APPSCALE_HOME'] = APPSCALE_HOME
    env_vars['MASTER_IP'] = db_master_ip
    env_vars['LOCAL_DB_IP'] = db_local_ip

    if table == "simpledb"
      env_vars['SIMPLEDB_ACCESS_KEY'] = @creds['SIMPLEDB_ACCESS_KEY']
      env_vars['SIMPLEDB_SECRET_KEY'] = @creds['SIMPLEDB_SECRET_KEY']
    end

    start_cmd = ["/usr/bin/python2.6 #{APPSCALE_HOME}/AppDB/soap_server.py",
            "-t #{table} -s #{HelperFunctions.get_secret}"].join(' ')
    stop_cmd = "pkill -9 soap_server"
    port = [4343]

    GodInterface.start(:uaserver, start_cmd, stop_cmd, port, env_vars)
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
    HAProxy.create_pbserver_config(my_node.private_ip, PbServer::PROXY_PORT, table)
    Nginx.create_pbserver_config(my_node.private_ip, PbServer::PROXY_PORT)
    Nginx.restart()

    # TODO check the return value
    PbServer.is_running(my_ip)
  end

  def stop_blob_server
    BlobServer.stop
    Djinn.log_run("pkill -f blobstore_server")
  end 

  def stop_soap_server
    GodInterface.stop(:uaserver)
  end 

  # Stops the AppManager service
  #
  def stop_app_manager_server
    GodInterface.stop(:appmanagerserver)
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
    write_database_info
    
    creds = @creds.to_a.flatten
    Djinn.log_debug("Djinn locations: #{@nodes.join(', ')}")
    Djinn.log_debug("DB Credentials: #{HelperFunctions.obscure_creds(@creds).inspect}")
    Djinn.log_debug("Apps to load: #{@app_names.join(', ')}")

    Djinn.log_debug("Appengine info: #{appengine_info}")
    initialize_nodes_in_parallel(appengine_info)
  end

  def spawn_appengine(nodes)
    appengine_info = []
    if nodes.length > 0
      if is_hybrid_cloud?
        num_of_vms_needed = nodes.length
        @state = "Spawning up hybrid virtual machines"
        appengine_info = HelperFunctions.spawn_hybrid_vms(@creds, nodes)
      elsif is_cloud?
        @state = "Spawning up #{nodes.length} virtual machines"
        roles = nodes.values

        # since there's only one cloud, call it cloud1 to tell us
        # to use the first ssh key (the only key)
        imc = InfrastructureManagerClient.new(@@secret)
        appengine_info = imc.spawn_vms(nodes.length, @creds, roles, "cloud1")
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

  def initialize_nodes_in_parallel(node_info)
    threads = []
    node_info.each { |slave|
      threads << Thread.new {
        initialize_node(slave)
      }
    }

    threads.each { |t| t.join }
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
    HelperFunctions.ensure_version_is_supported(ip, key)
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
    Djinn.log_debug("Copying SSH keys to node at IP address #{ip}")
    ssh_key = dest_node.ssh_key

    HelperFunctions.sleep_until_port_is_open(ip, SSH_PORT)
    Kernel.sleep(3)

    if @creds["infrastructure"] == "ec2" or @creds["infrastructure"] == "hybrid" or @creds["infrastructure"] == "euca"
      options = "-o StrictHostkeyChecking=no -o NumberOfPasswordPrompts=0"
      enable_root_login = "sudo cp /home/ubuntu/.ssh/authorized_keys /root/.ssh/"
      Djinn.log_run("ssh -i #{ssh_key} #{options} 2>&1 ubuntu@#{ip} '#{enable_root_login}'")
    end

    secret_key_loc = "#{CONFIG_FILE_LOCATION}/secret.key"
    cert_loc = "#{CONFIG_FILE_LOCATION}/certs/mycert.pem"
    key_loc = "#{CONFIG_FILE_LOCATION}/certs/mykey.pem"
    pub_key = File.expand_path("~/.ssh/id_rsa.pub")

    HelperFunctions.scp_file(secret_key_loc, secret_key_loc, ip, ssh_key)
    HelperFunctions.scp_file(cert_loc, cert_loc, ip, ssh_key)
    HelperFunctions.scp_file(key_loc, key_loc, ip, ssh_key)
    scp_ssh_key_to_ip(ip, ssh_key, pub_key)

    # TODO: should be able to merge these together
    if is_hybrid_cloud?
      cloud_num = 1
      loop {
        cloud_type = @creds["CLOUD_TYPE"]
        break if cloud_type.nil? or cloud_type == ""
        cloud_keys_dir = File.expand_path("#{CONFIG_FILE_LOCATION}/keys/cloud#{cloud_num}")
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
      cloud_keys_dir = File.expand_path("#{CONFIG_FILE_LOCATION}/keys/cloud1")
      make_dir = "mkdir -p #{cloud_keys_dir}"

      cloud_private_key = "#{cloud_keys_dir}/mykey.pem"
      cloud_cert = "#{cloud_keys_dir}/mycert.pem"

      HelperFunctions.run_remote_command(ip, make_dir, ssh_key, NO_OUTPUT)
      HelperFunctions.scp_file(ssh_key, ssh_key, ip, ssh_key)
      HelperFunctions.scp_file(cloud_private_key, cloud_private_key, ip, ssh_key)
      HelperFunctions.scp_file(cloud_cert, cloud_cert, ip, ssh_key)
    end
  end

 
  # Copies over SSH keys to ~/.ssh on the given machine, enabling that
  # machine to log in to itself or any other AppScale VM without being
  # prompted for a password. Note that since this copies keys to ~./ssh,
  # it will overwrite any keys that already exist there.
  # Args:
  #   ip: The IP address to copy SSH keys to.
  #   private_key: The SSH private key that should be copied over.
  #   public_key: The SSH public key that should be copied over.
  def scp_ssh_key_to_ip(ip, private_key, public_key)
    HelperFunctions.scp_file(private_key, "~/.ssh/id_rsa", ip,
      private_key)
    # this is needed for EC2 integration.
    HelperFunctions.scp_file(private_key, "~/.ssh/id_dsa", ip,
      private_key)
    HelperFunctions.scp_file(public_key, "~/.ssh/id_rsa.pub", ip,
      private_key)
  end


  def rsync_files(dest_node)
    controller = "#{APPSCALE_HOME}/AppController"
    server = "#{APPSCALE_HOME}/AppServer"
    loadbalancer = "#{APPSCALE_HOME}/AppLoadBalancer"
    appdb = "#{APPSCALE_HOME}/AppDB"
    neptune = "#{APPSCALE_HOME}/Neptune"
    loki = "#{APPSCALE_HOME}/Loki"
    iaas_manager = "#{APPSCALE_HOME}/InfrastructureManager"

    ssh_key = dest_node.ssh_key
    ip = dest_node.private_ip
    options = "-e 'ssh -i #{ssh_key}' -arv --filter '- *.pyc'"

    Djinn.log_run("rsync #{options} #{controller}/* root@#{ip}:#{controller}")
    Djinn.log_run("rsync #{options} #{server}/* root@#{ip}:#{server}")
    Djinn.log_run("rsync #{options} #{loadbalancer}/* root@#{ip}:#{loadbalancer}")
    Djinn.log_run("rsync #{options} --exclude='logs/*' --exclude='hadoop-*' --exclude='hbase/hbase-*' --exclude='voldemort/voldemort/*' --exclude='cassandra/cassandra/*' #{appdb}/* root@#{ip}:#{appdb}")
    Djinn.log_run("rsync #{options} #{neptune}/* root@#{ip}:#{neptune}")
    Djinn.log_run("rsync #{options} #{loki}/* root@#{ip}:#{loki}")
    Djinn.log_run("rsync #{options} #{iaas_manager}/* root@#{ip}:#{iaas_manager}")
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
    FileUtils.mkdir_p("#{APPSCALE_HOME}/AppDB/logs")

    @nodes.each { |node| 
      master_ip = node.private_ip if node.jobs.include?("db_master")
      slave_ips << node.private_ip if node.jobs.include?("db_slave")
    }

    Djinn.log_debug("Master is at #{master_ip}, slaves are at #{slave_ips.join(', ')}")

    my_public = my_node.public_ip
    HelperFunctions.write_file("#{CONFIG_FILE_LOCATION}/my_public_ip", "#{my_public}\n")

    my_private = my_node.private_ip
    HelperFunctions.write_file("#{CONFIG_FILE_LOCATION}/my_private_ip", "#{my_private}\n")
   
    head_node_ip = get_public_ip(@creds['hostname'])
    HelperFunctions.write_file("#{CONFIG_FILE_LOCATION}/head_node_ip", "#{head_node_ip}\n")

    login_ip = get_login.public_ip
    HelperFunctions.write_file("#{CONFIG_FILE_LOCATION}/login_ip", "#{login_ip}\n")
    
    masters_file = "#{CONFIG_FILE_LOCATION}/masters"
    HelperFunctions.write_file(masters_file, "#{master_ip}\n")

    if @total_boxes == 1
      Djinn.log_debug("Only saw one machine, therefore my node is " +
        "also a slave node")
      slave_ips = [ my_private ]
    end
    
    slave_ips_newlined = slave_ips.join("\n")
    HelperFunctions.write_file("#{CONFIG_FILE_LOCATION}/slaves", "#{slave_ips_newlined}\n")

    # Invoke datastore helper function
    setup_db_config_files(master_ip, slave_ips, @creds)

    update_hosts_info()

    # use iptables to lock down outside traffic
    # nodes can talk to each other on any port
    # but only the outside world on certain ports
    #`iptables --flush`
    if FIREWALL_IS_ON
      Djinn.log_run("bash #{APPSCALE_HOME}/firewall.conf")
    end
  end

  # Writes a file to the local filesystem that contains the IP address
  # of a machine that runs the AppLoadBalancer. AppServers use this file
  # to know where to send users to log in. Because users have to be able
  # to access this IP address, we use the public IP here instead of the
  # private IP.
  def write_apploadbalancer_location()
    login_file = "#{CONFIG_FILE_LOCATION}/apploadbalancer_public_ip"
    login_ip = get_login.public_ip()
    HelperFunctions.write_file(login_file, login_ip)
  end


  # Writes a file to the local filesystem that contains the IP
  # address of the 'nearest' machine running the RabbitMQ service.
  # 'Nearest' is defined as being this node's IP if our node runs RabbitMQ,
  # or a random node that runs RabbitMQ otherwise.
  def find_nearest_rabbitmq()
    rabbitmq_ip = nil
    if my_node.is_rabbitmq_master? or my_node.is_rabbitmq_slave?
      rabbitmq_ip = my_node.private_ip
    end

    if rabbitmq_ip.nil?
      rabbitmq_ips = []
      @nodes.each { |node|
        if node.is_rabbitmq_master? or node.is_rabbitmq_slave?
          rabbitmq_ips << node.private_ip
        end
      }
      Djinn.log_debug("RabbitMQ servers are at #{rabbitmq_ips.join(', ')}")

      # pick one at random
      rabbitmq_ip = rabbitmq_ips.sort_by { rand }[0]
    end

    Djinn.log_debug("AppServers on this node will connect to RabbitMQ " +
      "at #{rabbitmq_ip}")
    rabbitmq_file = "#{CONFIG_FILE_LOCATION}/rabbitmq_ip"
    rabbitmq_contents = rabbitmq_ip
    HelperFunctions.write_file(rabbitmq_file, rabbitmq_contents)
  end

  # Updates files on this machine with information about our hostname
  # and a mapping of where other machines are located.
  def update_hosts_info()
    all_nodes = ""
    @nodes.each_with_index { |node, index|
      all_nodes << "#{node.private_ip} appscale-image#{index}\n"
    }
    
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

    etc_hosts = "/etc/hosts"
    File.open(etc_hosts, "w+") { |file| file.write(new_etc_hosts) }    

    etc_hostname = "/etc/hostname"
    my_hostname = "appscale-image#{@my_index}"
    File.open(etc_hostname, "w+") { |file| file.write(my_hostname) }

    Djinn.log_run("/bin/hostname #{my_hostname}")
  end


  # Writes new nginx configuration files for the App Engine applications
  # hosted in this deployment. Callers should invoke this method whenever
  # there is a change in the number of machines hosting App Engine apps.
  def regenerate_nginx_config_files()
    Djinn.log_debug("Regenerating nginx config files for App Engine apps")
    my_public = my_node.public_ip
    my_private = my_node.private_ip
    login_ip = get_login.private_ip

    Djinn.log_debug("@app_info_map is #{@app_info_map.inspect}")
    @apps_loaded.each { |app|  
      Djinn.log_debug("Regenerating nginx config for app #{app}")
      app_number = @app_info_map[app]['nginx'] - Nginx::START_PORT
      proxy_port = HAProxy.app_listen_port(app_number)
      Nginx.write_fullproxy_app_config(app, app_number, my_public,
        my_private, proxy_port, login_ip, get_all_appengine_nodes())
    }
    Djinn.log_debug("Done writing new nginx config files!")
    Nginx.reload()
  end


  def write_hypersoap()
    HelperFunctions.write_file("#{CONFIG_FILE_LOCATION}/hypersoap", @userappserver_private_ip)
  end

  def my_node()
    if @my_index.nil?
      find_me_in_locations
    end

    if @my_index.nil?
      Djinn.log_debug("My index is nil - is nodes nil? #{@nodes.nil?}")
      if @nodes.nil?
        Djinn.log_debug("My nodes is nil also, timing error? race condition?")
      else
        Djinn.log_debug("Setting it to 0 position, even though it was not found")
        # pray its in the 0 position
        return @nodes[0]
      end
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

    remote_home = HelperFunctions.get_remote_appscale_home(ip, ssh_key)
    env = {
      'APPSCALE_HOME' => APPSCALE_HOME,
      'EC2_HOME' => ENV['EC2_HOME'],
      'JAVA_HOME' => ENV['JAVA_HOME']
    }
    start = "ruby #{remote_home}/AppController/djinnServer.rb"
    stop = "ruby #{remote_home}/AppController/terminate.rb"

    # remove any possible appcontroller state that may not have been
    # properly removed in non-cloud runs
    remove_state = "rm -rf #{CONFIG_FILE_LOCATION}/appcontroller-state.json"
    HelperFunctions.run_remote_command(ip, remove_state, ssh_key, NO_OUTPUT)

    GodInterface.start_god(ip, ssh_key)
    Kernel.sleep(1)

    begin
      GodInterface.start(:controller, start, stop, SERVER_PORT, env, ip, ssh_key)
      HelperFunctions.sleep_until_port_is_open(ip, SERVER_PORT, USE_SSL)
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
    !`ps ax | grep #{name} | grep -v grep`.empty?
  end

  def start_memcache()
    @state = "Starting up memcache"
    Djinn.log_debug("Starting up memcache")
    start_cmd = "/usr/bin/memcached -d -m 32 -p 11211 -u root"
    stop_cmd = "pkill memcached"
    GodInterface.start(:memcached, start_cmd, stop_cmd, [11211])
  end

  def stop_memcache()
    GodInterface.stop(:memcached)
  end

  def start_ejabberd()
    @state = "Starting up XMPP server"
    my_private = my_node.private_ip
    Ejabberd.stop
    Djinn.log_run("rm -f /var/lib/ejabberd/*")
    Ejabberd.write_auth_script(my_private, @@secret)
    Ejabberd.write_config_file(my_private)
    Ejabberd.start
  end

  def stop_ejabberd()
    Ejabberd.stop
  end

  def start_load_balancer()
    @state = "Starting up Load Balancer"
    Djinn.log_debug("Starting up Load Balancer")

    my_public = my_node.public_ip
    my_private = my_node.private_ip
    HAProxy.create_app_load_balancer_config(my_public, my_private, 
      LoadBalancer.proxy_port)
    Nginx.create_app_load_balancer_config(my_public, my_private, 
      LoadBalancer.proxy_port)
    LoadBalancer.start
    Nginx.restart
    Collectd.restart

    head_node_ip = get_public_ip(@creds['hostname'])
    if my_public == head_node_ip
      # Only start monitoring on the head node
      HAProxy.create_app_monitoring_config(my_public, my_private, 
        Monitoring.proxy_port)
      Nginx.create_app_monitoring_config(my_public, my_private, 
        Monitoring.proxy_port)
      Nginx.restart
      Monitoring.start
    end

    LoadBalancer.server_ports.each do |port|
      HelperFunctions.sleep_until_port_is_open("localhost", port)
      begin
        Net::HTTP.get_response("localhost:#{port}", '/')
      rescue SocketError
      end
    end
  end

  def stop_load_balancer()
    Djinn.log_debug("Shutting down Load Balancer")
    LoadBalancer.stop
  end

  def start_shadow()
    Djinn.log_debug("Starting Shadow role")
  end

  def stop_shadow()
    Djinn.log_debug("Stopping Shadow role")
  end

  #
  # Swaps out an application with one that relays an error message to the 
  # developer. It will take the application that currently exists in the 
  # application folder, deletes it, and places a templated app that prints out the 
  # given error message. 
  #
  # Args: 
  #   app_name: Name of application to construct an error application for
  #   err_msg: A String message that will be displayed as 
  #            the reason why we couldn't start their application.
  #
  # Returns: 
  #   Returns: Nothing
  #
  def place_error_app(app_name, err_msg)
    Djinn.log_debug("Placing error application for #{app_name} because of: #{err_msg}")
    ea = ErrorApp.new(app_name, err_msg)
    ea.generate() 
  end

  def start_appengine()
    @state = "Preparing to run AppEngine apps if needed"
    Djinn.log_debug("Starting appengine - pbserver is at [#{@userappserver_private_ip}]")

    uac = UserAppClient.new(@userappserver_private_ip, @@secret)
    app_manager = AppManagerClient.new()

    if @restored == false #and restore_from_db?
      Djinn.log_debug("Need to restore")
      app_list = uac.get_all_apps()
      Djinn.log_debug("All apps are [#{app_list.join(', ')}]")
      app_list.each { |app|
        if uac.does_app_exist?(app)
          Djinn.log_debug("App #{app} is enabled, so restoring it")
          @app_names = @app_names + [app]
        else
          Djinn.log_debug("App #{app} is not enabled, moving on")
        end
      }

      @app_names.uniq!
      Djinn.log_debug("Decided to restore these apps: [#{@app_names.join(', ')}]")
      @restored = true
    else
      Djinn.log_debug("Don't need to restore")
    end
    APPS_LOCK.synchronize {
      apps_to_load = @app_names - @apps_loaded - ["none"]
      apps_to_load.each { |app|
        app_data = uac.get_app_data(app)
        Djinn.log_debug("Get app data for #{app} said [#{app_data}]")

        loop {
          Djinn.log_debug("Waiting for app data to have instance info for app named #{app}: #{app_data}")

          app_data = uac.get_app_data(app)
          if app_data[0..4] != "Error"
            break
          end
          Kernel.sleep(5)
        }

        my_public = my_node.public_ip
        my_private = my_node.private_ip
        app_language = app_data.scan(/language:(\w+)/).flatten.to_s
        
        @app_info_map[app] = {}
        @app_info_map[app]['language'] = app_language

        # TODO: merge these 
        shadow = get_shadow
        shadow_ip = shadow.private_ip
        ssh_key = shadow.ssh_key
        app_dir = "/var/apps/#{app}/app"
        app_path = "#{app_dir}/#{app}.tar.gz"
        FileUtils.mkdir_p(app_dir)
         
        if !copy_app_to_local(app)
          place_error_app(app, "ERROR: Failed to copy app: #{app}")
        end
        HelperFunctions.setup_app(app)

         
        if my_node.is_shadow?
          CronHelper.update_cron(my_public, app_language, app)
          start_xmpp_for_app(app, app_language)
        end
        app_number = @nginx_port - Nginx::START_PORT
        proxy_port = HAProxy.app_listen_port(app_number)
        login_ip = get_login.private_ip

        if my_node.is_login? #and !my_node.is_appengine?
          success = Nginx.write_fullproxy_app_config(app, app_number, my_public,
            my_private, proxy_port, login_ip, get_all_appengine_nodes())
          if success
            Nginx.reload
          else
            err_msg = "ERROR: Failure to create valid nginx config file" + \
                      " for application #{app} full proxy."
            place_error_app(app, err_msg)
          end

          @app_info_map[app]['nginx'] = @nginx_port
          @app_info_map[app]['haproxy'] = @haproxy_port

          @nginx_port += 1
          @haproxy_port += 1
        end


        if my_node.is_appengine?
          app_number = @nginx_port - Nginx::START_PORT
          start_port = HelperFunctions::APP_START_PORT
          begin
            static_handlers = HelperFunctions.parse_static_data(app)
          rescue Exception => e
            # This specific exception may be a json parse error
            error_msg = "ERROR: Unable to parse app.yaml file for #{app}." + \
                        " Exception of #{e.class} with message #{e.message}" 
            place_error_app(app, error_msg)
            static_handlers = []
          end
          proxy_port = HAProxy.app_listen_port(app_number)
          login_ip = get_login.private_ip
          success = Nginx.write_app_config(app, app_number, my_public, my_private,
            proxy_port, static_handlers, login_ip)
          if !success
            error_msg = "ERROR: Failure to create valid nginx config file " + \
                        "for application #{app}."
            place_error_app(app, error_msg)
          end
          Collectd.write_app_config(app)

          # send a warmup request to the app to get it loaded - can shave a
          # number of seconds off the initial request if it's java or go
          # go provides a default warmup route
          # TODO: if the user specifies a warmup route, call it instead of /
          warmup_url = "/"

          @app_info_map[app]['appengine'] = []
          @num_appengines.times { |index|
            Djinn.log_debug("Starting #{app_language} app #{app} on " +
              "#{HelperFunctions.local_ip}:#{@appengine_port}")
            @app_info_map[app]['appengine'] << @appengine_port

            xmpp_ip = get_login.public_ip

            pid = app_manager.start_app(app, @appengine_port, 
              get_load_balancer_ip(), @nginx_port, app_language, 
              xmpp_ip, [Djinn.get_nearest_db_ip(false)])

            if pid == -1
              place_error_app(app, "ERROR: Unable to start application " + \
                  "#{app}. Please check the application logs.") 
            end

            pid_file_name = "#{CONFIG_FILE_LOCATION}/#{app}-#{@appengine_port}.pid"
            HelperFunctions.write_file(pid_file_name, pid)

            @appengine_port += 1
          }

          HAProxy.update_app_config(app, app_number, 
            @app_info_map[app]['appengine'], my_private)
          Nginx.reload
          HAProxy.reload
          Collectd.restart

          loop {
            Kernel.sleep(5)
            success = uac.add_instance(app, my_public, @nginx_port)
            Djinn.log_debug("Add instance returned #{success}")
            if success  
              # tell ZK that we are hosting the app in case we die, so that
              # other nodes can update the UserAppServer on its behalf
              ZKInterface.add_app_instance(app, my_public, @nginx_port)
              break
            end
          }

          nginx = @nginx_port
          haproxy = @haproxy_port

          # Update our local information so that we know later what ports
          # we're using to host this app on for nginx and haproxy
          @app_info_map[app]['nginx'] = @nginx_port
          @app_info_map[app]['haproxy'] = @haproxy_port

          login_ip = get_login.public_ip

          Thread.new {
            haproxy_location = "http://#{my_private}:#{haproxy}#{warmup_url}"
            nginx_location = "http://#{my_public}:#{nginx}#{warmup_url}"

            wget_haproxy = "wget #{WGET_OPTIONS} #{haproxy_location}"
            wget_nginx = "wget #{WGET_OPTIONS} #{nginx_location}"

            Djinn.log_run(wget_haproxy)
            Djinn.log_run(wget_nginx)
          }

          @nginx_port += 1
          @haproxy_port += 1

          # now doing this at the real end so that the tools will
          # wait for the app to actually be running before returning
          done_uploading(app, app_path, @@secret)
        end

        Monitoring.restart if my_node.is_shadow?
        APPS_LOCK.synchronize {
          if @app_names.include?("none")
            @apps_loaded = @apps_loaded - ["none"]
            @app_names = @app_names - ["none"]
          end
          
          @apps_loaded << app
        }
      }

      Djinn.log_debug("#{apps_to_load.size} apps loaded")  
    } # end of synchronize
  end


  # This method guards access to perform_scaling_for_appservers so that only 
  # one thread call it at a time. We also only perform scaling if the user 
  # wants us to, and simply return otherwise.
  #
  def scale_appservers
    if !my_node.is_appengine?
      Djinn.log_debug("Not autoscaling, because we aren't an AppServer")
      return
    end

    if @creds["autoscale"] == "true"
      Djinn.log_debug("Examining AppServers to autoscale them")
      perform_scaling_for_appservers()
    else
      Djinn.log_debug("Not autoscaling AppServers - disallowed by the user")
    end
  end


  # Adds or removes AppServers within a node based on the number of requests
  # that each application has received as well as the number of requests that
  # are sitting in haproxy's queue, waiting to be served.
  #
  # TODO: Accessing global state should use a lock. Failure to do so causes 
  #   race conditions where arrays are accessed using indexes that are no 
  #   longer valid. 
  #
  def perform_scaling_for_appservers()
    APPS_LOCK.synchronize {
      @apps_loaded.each { |app_name|

        next if app_name == "none"  
        Djinn.log_debug("Deciding whether to scale AppServers for #{app_name}")
        initialize_scaling_info_for_app(app_name)

        if is_cpu_or_mem_maxed_out?(@app_info_map[app_name]['language'])
          # TODO(cgb): This seems like a good condition to scale down
          Djinn.log_debug("Too much CPU or memory is being used - don't scale")
          return
        end

        case get_scaling_info_for_app(app_name)
        when :scale_up
          try_to_scale_up(app_name)
        when :scale_down
          try_to_scale_down(app_name)
        else
          Djinn.log_debug("No change. Keeping the same number of AppServers")
        end
      }
    }
  end


  # Sets up information about the request rate and number of requests in
  # haproxy's queue for the given application.
  #
  # Args:
  #   app_name: The name of the application to set up scaling info
  #
  def initialize_scaling_info_for_app(app_name)
    return if @initialized_apps[app_name]

    @req_rate[app_name] = []
    @req_in_queue[app_name] = []

    # Fill in req_rate and req_in_queue with dummy info for now
    NUM_DATA_POINTS.times { |i|
      @req_rate[app_name][i] = 0
      @req_in_queue[app_name][i] = 0
    }

    if !@last_decision.has_key?(app_name)
      @last_decision[app_name] = 0
    end

    @initialized_apps[app_name] = true
  end
  

  # Looks at how much CPU and memory is being used system-wide, to determine
  # if a new AppServer should be added. As AppServers in different languages
  # consume different amounts of CPU and memory, we consult the global
  # variables that indicate what the maximum CPU and memory limits are for
  # a new AppServer in the given language.
  def is_cpu_or_mem_maxed_out?(language)
    stats = get_stats(@@secret)
    Djinn.log_debug("CPU used: #{stats['cpu']}, mem used: #{stats['memory']}")

    Djinn.log_debug("Examining CPU and memory usage for a #{language} application.")
    current_cpu = stats['cpu']
    max_cpu = MAX_CPU_FOR_APPSERVERS[language]

    if current_cpu > max_cpu
      Djinn.log_debug("Not enough CPU is free to spawn up a new #{language} " +
        "AppServer (#{current_cpu} CPU used > #{max_cpu} maximum)")
      return true
    end

    current_mem = Float(stats['memory'])
    max_mem = MAX_MEM_FOR_APPSERVERS[language]

    if current_mem > max_mem
      Djinn.log_debug("Not enough memory is free to spawn up a new " +
        "#{language} AppServer (#{current_mem} memory used > #{max_mem} " +
        "maximum)")
      return true
    end

    Djinn.log_debug("Enough CPU and memory are free on this machine to " +
      "support a new #{language} AppServer")
    return false
  end


  # Queries haproxy to see how many requests are queued for a given application
  # and how many requests are served at a given time. Based on this information,
  # this method reports whether or not AppServers should be added, removed, or
  # if no changes are needed.
  def get_scaling_info_for_app(app_name)
    autoscale_log = File.open(AUTOSCALE_LOG_FILE, "a+")
    autoscale_log.puts("Getting scaling info for application #{app_name}")
  
    # Average Request rates and queued requests set to 0
    avg_req_rate = 0
    avg_req_in_queue = 0
  
    # Move all the old data over one spot in our arrays (basically making
    # these rotating buffers) and see the average number of requests received
    # and enqueued from the old data
    (NUM_DATA_POINTS-1).times { |i|
      @req_rate[app_name][i] = @req_rate[app_name][i+1]
      @req_in_queue[app_name][i] = @req_in_queue[app_name][i+1]
      avg_req_rate += @req_rate[app_name][i+1].to_i
      avg_req_in_queue += @req_in_queue[app_name][i+1].to_i
    }

    # Now see how many requests came in for our app and how many are enqueued
    monitor_cmd = "echo \"show info;show stat\" | " +
      "socat stdio unix-connect:/etc/haproxy/stats | grep #{app_name}"

    `#{monitor_cmd}`.each { |line|
      parsed_info = line.split(',')
      if parsed_info.length < REQ_RATE_INDEX  # not a line with request info
        next
      end

      service_name = parsed_info[SERVICE_NAME_INDEX]
      req_in_queue_present = parsed_info[REQ_IN_QUEUE_INDEX]
      req_rate_present = parsed_info[REQ_RATE_INDEX]
      
      if service_name == "FRONTEND"
        autoscale_log.puts("#{service_name} Request Rate #{req_rate_present}")
        req_rate_present = parsed_info[REQ_RATE_INDEX]
        avg_req_rate += req_rate_present.to_i
        @req_rate[app_name][NUM_DATA_POINTS-1] = req_rate_present
      end
      
      if service_name == "BACKEND"
        autoscale_log.puts("#{service_name} Queued Currently " +
          "#{req_in_queue_present}")
        req_in_queue_present = parsed_info[REQ_IN_QUEUE_INDEX]
        avg_req_in_queue += req_in_queue_present.to_i
        @req_in_queue[app_name][NUM_DATA_POINTS-1] = req_in_queue_present
      end
    }
      
    total_req_in_queue = avg_req_in_queue

    avg_req_rate /= NUM_DATA_POINTS
    avg_req_in_queue /= NUM_DATA_POINTS

    autoscale_log.puts("[#{app_name}] Average Request rate: #{avg_req_rate}")
    autoscale_log.puts("[#{app_name}] Average Queued requests: " +
      "#{avg_req_in_queue}")

    if avg_req_rate <= SCALEDOWN_REQUEST_RATE_THRESHOLD and 
      total_req_in_queue.zero?
      return :scale_down
    end

    if avg_req_rate > SCALEUP_REQUEST_RATE_THRESHOLD and 
      avg_req_in_queue > SCALEUP_QUEUE_SIZE_THRESHOLD
      return :scale_up
    end

    return :no_change
  end


  def try_to_scale_up(app_name)
    Djinn.log_debug("Considering whether we should scale up")
    time_since_last_decision = Time.now.to_i - @last_decision[app_name]
    appservers_running = @app_info_map[app_name]['appengine'].length
          
    if time_since_last_decision > SCALEUP_TIME_THRESHOLD and 
      !@app_info_map[app_name]['appengine'].nil? and
      appservers_running < MAX_APPSERVERS_ON_THIS_NODE

      Djinn.log_debug("Adding a new AppServer on this node for #{app_name}")
      add_appserver_process(app_name)
      @last_decision[app_name] = Time.now.to_i
    elsif time_since_last_decision <= SCALEUP_TIME_THRESHOLD
      Djinn.log_debug("Not enough time has passed since when the last " +
        "scaling decision was made for #{app_name}")
    elsif !@app_info_map[app_name]['appengine'].nil? and
      appservers_running > MAX_APPSERVERS_ON_THIS_NODE

      Djinn.log_debug("The maximum number of AppServers for this app " +
        "are already running, so don't add any more")
    end
  end


  def try_to_scale_down(app_name)
    Djinn.log_debug("Considering whether we should scale down")
    time_since_last_decision = Time.now.to_i - @last_decision[app_name]
    appservers_running = @app_info_map[app_name]['appengine'].length

    if time_since_last_decision > SCALEDOWN_TIME_THRESHOLD and
      !@app_info_map[app_name]['appengine'].nil? and
      appservers_running > MIN_APPSERVERS_ON_THIS_NODE

      Djinn.log_debug("Removing an AppServer on this node for #{app_name}")
      remove_appserver_process(app_name)
      @last_decision[app_name] = Time.now.to_i
    elsif !@app_info_map[app_name]['appengine'].nil? and
      appservers_running <= MIN_APPSERVERS_ON_THIS_NODE

      Djinn.log_debug("Only #{MIN_APPSERVERS_ON_THIS_NODE} AppServer(s) " +
        "running - don't kill")
    elsif time_since_last_decision <= SCALEDOWN_TIME_THRESHOLD 
      Djinn.log_debug("Last decision was taken within the time threshold")
    end
  end


  # Starts a new AppServer for the given application.
  # TODO(cgb): This is mostly copy-pasta'd from start_appengine - consolidate
  # this somehow
  #
  # Args:
  #   app: Name of the application for which we're adding a process instance
  #
  def add_appserver_process(app)
    # Starting a appserver instance on request to scale the application 
    @state = "Adding an AppServer for #{app}"

    uac = UserAppClient.new(@userappserver_private_ip, @@secret)
    app_manager = AppManagerClient.new()

    warmup_url = "/"

    app_data = uac.get_app_data(app)
    
    Djinn.log_debug("Get app data for #{app} said [#{app_data}]")

    loop {
        Djinn.log_debug("Waiting for app data to have instance info for app named #{app}: #{app_data}")

        app_data = uac.get_app_data(app)
        if app_data[0..4] != "Error"
          break
        end
        sleep(5)
     }
    
    app_language = app_data.scan(/language:(\w+)/).flatten.to_s
    my_public = my_node.public_ip
    my_private = my_node.private_ip

    app_is_enabled = uac.does_app_exist?(app)
    Djinn.log_debug("is app #{app} enabled? #{app_is_enabled}")
    if app_is_enabled == "false"
      return  
    end

    nginx_port = @app_info_map[app]['nginx']
    haproxy_port = @app_info_map[app]['haproxy']
    @app_info_map[app]['appengine'] << @appengine_port

    app_number = nginx_port - Nginx::START_PORT

    my_private = my_node.private_ip
    Djinn.log_debug("port apps error contains - #{@app_info_map[app]['appengine']}")
    HAProxy.update_app_config(app, app_number, @app_info_map[app]['appengine'],
      my_private)     

    Djinn.log_debug("Adding #{app_language} app #{app} on #{HelperFunctions.local_ip}:#{@appengine_port} ")

    xmpp_ip = get_login.public_ip

    pid = app_manager.start_app(app, @appengine_port, 
            get_load_balancer_ip(), nginx_port, app_language, 
            xmpp_ip, [Djinn.get_nearest_db_ip(false)])

    if pid == -1
      Djinn.log_debug("ERROR: Unable to start application #{app} on port #{@appengine_port}.") 
      next
    end
    pid_file_name = "#{CONFIG_FILE_LOCATION}/#{app}-#{@appengine_port}.pid"
    HelperFunctions.write_file(pid_file_name, pid)

    @appengine_port += 1

    # Nginx.reload 
    HAProxy.reload
    Collectd.restart

    # add_instance_info = uac.add_instance(app, my_public, @nginx_port)
   
    Thread.new {
      haproxy_location = "http://#{my_private}:#{haproxy_port}#{warmup_url}"
      nginx_location = "http://#{my_public}:#{nginx_port}#{warmup_url}"

      wget_haproxy = "wget #{WGET_OPTIONS} #{haproxy_location}"
      wget_nginx = "wget #{WGET_OPTIONS} #{nginx_location}"
 
      Djinn.log_run(wget_haproxy)
      Djinn.log_run(wget_nginx)
    }
  end


  # Terminates a random AppServer that hosts the specified App Engine app.
  #
  # Args:
  #   app: The name of the application for which we're removing a 
  #        process instance
  #
  def remove_appserver_process(app)
    @state = "Stopping an AppServer to free unused resources"
    Djinn.log_debug("Deleting appserver instance to free up unused resources")

    uac = UserAppClient.new(@userappserver_private_ip, @@secret)
    app_manager = AppManagerClient.new()
    warmup_url = "/"

    my_public = my_node.public_ip
    my_private = my_node.private_ip
    app_number = @app_info_map[app]['nginx'] - Nginx::START_PORT

    app_data = uac.get_app_data(app)

    Djinn.log_debug("Get app data for #{app} said [#{app_data}]")

    app_is_enabled = uac.does_app_exist?(app)
    Djinn.log_debug("is app #{app} enabled? #{app_is_enabled}")
    if app_is_enabled == "false"
      return
    end

    # Select a random AppServer to kill.
    ports = @app_info_map[app]['appengine']
    port = ports[rand(ports.length)]

    if !app_manager.stop_app_instance(app, port)
      Djinn.log_debug("Unable to stop instance on port #{port} app #{app_name}") 
    end

    # Delete the port number from the app_info_map
    @app_info_map[app]['appengine'].delete(port)

    HAProxy.update_app_config(app, app_number, @app_info_map[app]['appengine'],
      my_private)
    HAProxy.reload
  end 
 

  def stop_appengine()
    Djinn.log_debug("Shutting down AppEngine")

    uac = UserAppClient.new(@userappserver_private_ip, @@secret)
    app_list = uac.get_all_apps()
    my_public = my_node.public_ip

    Djinn.log_debug("All apps are [#{app_list.join(', ')}]")
    app_list.each { |app|
      if uac.does_app_exist?(app)
        Djinn.log_debug("App #{app} is enabled, so stopping it.")
        hosts = uac.get_hosts_for_app(app)
        Djinn.log_debug("[Stop appengine] hosts for #{app} is [#{hosts.join(', ')}]")
        hosts.each { |host|
          Djinn.log_debug("[Stop appengine] deleting instance for app #{app} at #{host}")
          ip, port = host.split(":")
          uac.delete_instance(app, ip, port)
        }

        Djinn.log_debug("Finished deleting instances for app #{app}")
        #Djinn.log_run("rm -fv /etc/nginx/#{app}.conf")
        Nginx.reload
      else
        Djinn.log_debug("App #{app} wasnt enabled, skipping it")
      end
    }

    APPS_LOCK.synchronize { 
      @app_names = []
      @apps_loaded = []
      @restored = false
    }
  
    Djinn.log_run("pkill -f dev_appserver")
    Djinn.log_run("pkill -f DevAppServerMain")
  end

  # Returns true on success, false otherwise
  def copy_app_to_local(appname)
    app_dir = "/var/apps/#{appname}/app"
    app_path = "#{app_dir}/#{appname}.tar.gz"

    if File.exists?(app_path)
      Djinn.log_debug("I already have a copy of app #{appname} - won't grab it remotely")
      return true
    else
      Djinn.log_debug("I don't have a copy of app #{appname} - will grab it remotely")
    end

    nodes_with_app = []
    loop {
      nodes_with_app = ZKInterface.get_app_hosters(appname)
      break if !nodes_with_app.empty?
      Djinn.log_debug("Waiting for a node to have a copy of app #{appname}")
      Kernel.sleep(5)
    }

    # Try 3 times on each node known to have this application
    nodes_with_app.each { |node|
      ssh_key = node.ssh_key
      ip = node.public_ip
      tries = 3
      loop {
        Djinn.log_debug("Trying #{ip}:#{app_path} for the application")
        Djinn.log_run("scp -o StrictHostkeyChecking=no -i #{ssh_key} #{ip}:#{app_path} #{app_path}")
        if File.exist?("#{app_path}") == true
          Djinn.log_debug("Got a copy of #{appname} from #{ip}")
          return true 
        end
        Djinn.log_debug("ERROR: Unable to get the application from #{ip}:#{app_path}! scp failed.") 
        if tries > 0
          Djinn.log_debug("Trying again in 5 seconds") 
          tries = tries - 1
          Kernel.sleep(5)
        else
          Djinn.log_debug("Giving up on node #{ip} for the application")
          break
        end
      }
    }
    Djinn.log_debug("Unable to get the application from any node")
    return false 
  end

  def start_xmpp_for_app(app, app_language)
    # create xmpp account for the app
    # for app named baz, this translates to baz@login_ip

    login_ip = get_login.public_ip
    uac = UserAppClient.new(@userappserver_public_ip, @@secret)
    xmpp_user = "#{app}@#{login_ip}"
    xmpp_pass = HelperFunctions.encrypt_password(xmpp_user, @@secret)
    uac.commit_new_user(xmpp_user, xmpp_pass, "app")

    Djinn.log_debug("Created user [#{xmpp_user}] with password [#{@@secret}] and hashed password [#{xmpp_pass}]")

    if Ejabberd.does_app_need_receive?(app, app_language)
      start_cmd = "python2.6 #{APPSCALE_HOME}/AppController/xmpp_receiver.py #{app} #{login_ip} #{@@secret}"
      stop_cmd = "ps ax | grep '#{start_cmd}' | grep -v grep | awk '{print $1}' | xargs -d '\n' kill -9"
      GodInterface.start(app, start_cmd, stop_cmd, 9999)
      Djinn.log_debug("App #{app} does need xmpp receive functionality")
    else
      Djinn.log_debug("App #{app} does not need xmpp receive functionality")
    end
  end

  def self.neptune_parse_creds(storage, job_data)
    creds = {}

    if storage == "s3"
      ['EC2_ACCESS_KEY', 'EC2_SECRET_KEY', 'S3_URL'].each { |item|
        creds[item] = job_data["@#{item}"]
      }
    end

    return creds
  end

  def start_open
    return
  end

  def stop_open
    return
  end
end
