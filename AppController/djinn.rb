#!/usr/bin/ruby -w

# Imports within Ruby's standard libraries
require 'logger'
require 'monitor'
require 'net/http'
require 'net/https'
require 'openssl'
require 'securerandom'
require 'set'
require 'socket'
require 'soap/rpc/driver'
require 'syslog'
require 'timeout'
require 'tmpdir'
require 'yaml'


# Imports for RubyGems
require 'rubygems'
require 'httparty'
require 'json'
require 'zookeeper'


# Imports for AppController libraries
$:.unshift File.join(File.dirname(__FILE__), "lib")
require 'app_controller_client'
require 'app_manager_client'
require 'backup_restore_service'
require 'blobstore'
require 'cron_helper'
require 'custom_exceptions'
require 'datastore_server'
require 'ejabberd'
require 'error_app'
require 'groomer_service'
require 'haproxy'
require 'helperfunctions'
require 'hermes_service'
require 'infrastructure_manager_client'
require 'monit_interface'
require 'nginx'
require 'search'
require 'taskqueue'
require 'taskqueue_client'
require 'terminate'
require 'user_app_client'
require 'zkinterface'
require "zookeeper_helper"

NO_OUTPUT = false


# This lock makes it so that global variables related to apps are not updated
# concurrently, preventing race conditions.
APPS_LOCK = Monitor.new()


# This lock is to ensure that only one thread is trying to start/stop
# applications.
AMS_LOCK = Mutex.new()


# This lock is to ensure that only one thread is trying to start/stop
# new nodes (it takes a long time to spawn a new VM).
SCALE_LOCK = Mutex.new()


# Prevents nodetool from being invoked concurrently.
NODETOOL_LOCK = Mutex.new()


# The name of the user to be used with reserved applications.
APPSCALE_USER = "appscale-user@local.appscale"


# The string that should be returned to the caller if they call a publicly
# exposed SOAP method but provide an incorrect secret.
BAD_SECRET_MSG = "false: bad secret"


# The String that should be returned to callers if they attempt to add or remove
# AppServers from an HAProxy config file at a node where HAProxy is not running.
NO_HAPROXY_PRESENT = "false: haproxy not running"


# The String that should be returned to callers if they attempt to add
# AppServers for an app that does not yet have nginx and haproxy set up.
NOT_READY = "false: not ready yet"


# A response that indicates that the caller made an invalid request.
INVALID_REQUEST = 'false: invalid request'


# Regular expression to determine if a file is a .tar.gz file.
TAR_GZ_REGEX = /\.tar\.gz$/


# The maximum number of seconds that we should wait when deploying Google App
# Engine applications via the AppController.
APP_UPLOAD_TIMEOUT = 180


# The location on the local file system where we store information about
# where ZooKeeper clients are located, used to backup and restore
# AppController information.
ZK_LOCATIONS_FILE = "/etc/appscale/zookeeper_locations.json"


# The location of the logrotate scripts.
LOGROTATE_DIR = '/etc/logrotate.d'


# The name of the generic appscale centralized app logrotate script.
APPSCALE_APP_LOGROTATE = 'appscale-app-logrotate.conf'


# The location of the appscale-upload-app script from appscale-tools.
UPLOAD_APP_SCRIPT = `which appscale-upload-app`.chomp


# The location of the build cache.
APPSCALE_CACHE_DIR = '/var/cache/appscale'


# The domain that hosts packages for the build.
PACKAGE_MIRROR_DOMAIN = 's3.amazonaws.com'


# The location on the package mirror where the packages are stored.
PACKAGE_MIRROR_PATH = '/appscale-build'


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
  attr_accessor :options


  # An Array of Strings, each of which corresponding to the name of an App
  # Engine app that should be loaded.
  attr_accessor :app_names


  # An Array of Strings, each of which corresponding to the name of an App
  # Engine app that has been loaded on this node.
  attr_accessor :apps_loaded


  # An Array of Strings, each of which corresponding to the name of an App
  # Engine app that should be restarted on this node.
  attr_accessor :apps_to_restart


  # A boolean that is used to let remote callers know when this AppController
  # is done initializing itself, but not necessarily done starting or
  # stopping roles.
  attr_accessor :done_initializing


  # A boolean that is used to let remote callers know when this AppController
  # is done starting all the services it is responsible for.
  attr_accessor :done_loading



  # The human-readable state that this AppController is in.
  attr_accessor :state


  # A boolean that is used to let remote callers start the shutdown process
  # on this AppController, which will cleanly shut down and terminate all
  # services on this node.
  attr_accessor :kill_sig_received


  # An Integer that indexes into @nodes, to return information about this node.
  attr_accessor :my_index


  # An Array that lists the CPU, disk, and memory usage of each machine in this
  # AppScale deployment. Used as a cache so that it does not need to be
  # generated in response to AppDashboard requests.
  attr_accessor :all_stats


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


  # A Hash that maps the names of Google App Engine apps running in this AppScale
  # deployment to the total number of requests that haproxy has processed.
  attr_accessor :total_req_rate


  # A Hash that maps the names of Google App Engine apps running in this AppScale
  # deployment to the current number of requests that haproxy has queued.
  attr_accessor :current_req_rate


  # A Hash that maps the names of Google App Engine apps running in this AppScale
  # deployment to the last time we sampled the total number of requests that
  # haproxy has processed. When combined with total_req_rate, we can infer the
  # average number of requests per second that come in for each App Engine
  # application.
  attr_accessor :last_sampling_time


  # A Time that corresponds to the last time this machine added or removed nodes
  # in this AppScale deployment. Adding or removing nodes can happen in response
  # to autoscaling requests, or (eventually) to recover from faults.
  attr_accessor :last_scaling_time


  # A Hash that maps reservation IDs generated when uploading App Engine apps
  # via the AppDashboard to the status of the uploaded app (e.g., started
  # uploading, failed because of a bad app.yaml).
  attr_accessor :app_upload_reservations


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
  APPSCALE_CONFIG_DIR = "/etc/appscale"


  # The location on the local filesystem where the AppController writes
  # the location of all the nodes which are taskqueue nodes.
  TASKQUEUE_FILE = "#{APPSCALE_CONFIG_DIR}/taskqueue_nodes"


  APPSCALE_HOME = ENV['APPSCALE_HOME']


  # The location on the local filesystem where we save data that should be
  # persisted across AppScale deployments. Currently this is Cassandra data,
  # ZooKeeper data, and Google App Engine apps that users upload.
  PERSISTENT_MOUNT_POINT = "/opt/appscale"


  # The location where we can find the Python 2.7 executable, included because
  # it is not the default version of Python installed on AppScale VMs.
  PYTHON27 = "/usr/bin/python2"


  # The message that we display to the user if they call a SOAP-accessible
  # function with a malformed input (e.g., of the wrong class or format).
  BAD_INPUT_MSG = JSON.dump({'success' => false, 'message' => 'bad input'})


  # The message that we display to the user if they want to scale up services
  # in an Xen/KVM deployment but don't have enough open nodes to do so.
  NOT_ENOUGH_OPEN_NODES = JSON.dump({'success' => false,
    'message' => 'not enough open nodes'})


  # This is the duty cycle for the main loop(s).
  DUTY_CYCLE = 10


  # How many minutes to print the stats in the logs.
  PRINT_STATS_MINUTES = 30


  # This is the time to wait before aborting after a crash. We use this
  # time to give a chance to the tools to collect the crashlog.
  WAIT_TO_CRASH = 30


  # This is a 'small' sleep that we generally use when waiting for
  # services to be up.
  SMALL_WAIT = 5


  # How often we should attempt to increase the number of AppServers on a
  # given node. It's measured as a multiplier of DUTY_CYCLE.
  SCALEUP_THRESHOLD = 5


  # How often we should attempt to decrease the number of AppServers on a
  # given node. It's measured as a multiplier of DUTY_CYCLE.
  SCALEDOWN_THRESHOLD = 15


  # When spinning new node up or down, we need to use a much longer time
  # to dampen the scaling factor, to give time to the instance to fully
  # boot, and to reap the benefit of an already running instance. This is
  # a multiplication factor we use with the above thresholds.
  SCALE_TIME_MULTIPLIER = 6


  # This is the generic retries to do.
  RETRIES = 5


  # The minimum number of requests that have to sit in haproxy's wait queue for
  # an App Engine application before we will scale up the number of AppServers
  # that serve that application.
  SCALEUP_QUEUE_SIZE_THRESHOLD = 5


  # A Float that determines how much CPU can be used before the autoscaler will
  # stop adding AppServers on a node.
  MAX_CPU_FOR_APPSERVERS = 90.00


  # We won't allow any AppEngine server to have 1 minute average load
  # (normalized on the number of CPUs) to be bigger than this constant.
  MAX_LOAD_AVG = 2.0


  # We need to leave some extra RAM available for the system to operate
  # safely.
  SAFE_MEM = 500


  # A regular expression that can be used to match any character that is not
  # acceptable to use in a hostname:port string, used to filter out unacceptable
  # characters from user input.
  NOT_FQDN_REGEX = /[^\w\d\.:\/_-]/


  # A regular expression that can be used to match any character that is not
  # acceptable to use in a hostname:port string, while also allowing the +
  # character to be used. This is used to filter out unacceptable characters
  # from user input where the plus sign is acceptable.
  NOT_FQDN_OR_PLUS_REGEX = /[^\w\d\.\+:\/_-]/


  # A regular expression that can be used to match any character that is not
  # acceptable to use in a e-mail address, used to filter out unacceptable
  # characters from user input.
  NOT_EMAIL_REGEX = /[^\w\d_@-]/


  # An Integer that determines how many log messages we should send at a time
  # to the AppDashboard, for later viewing.
  LOGS_PER_BATCH = 25


  # An Array of Strings, where each String is an appid that corresponds to an
  # application that cannot be relocated within AppScale, because system
  # services assume that they run at a specific location.
  RESERVED_APPS = [AppDashboard::APP_NAME]


  # A Fixnum that indicates what the first port is that can be used for hosting
  # Google App Engine apps.
  STARTING_APPENGINE_PORT = 20000


  # A String that is returned to callers of get_app_upload_status that provide
  # an invalid reservation ID.
  ID_NOT_FOUND = "Reservation ID not found."


  # This String is used to inform the tools that the AppController is not
  # quite ready to receive requests.
  NOT_UP_YET = "not-up-yet"


  # A String that is returned to callers of set_property that provide an invalid
  # instance variable name to set.
  KEY_NOT_FOUND = "No property exists with the given name."


  # A String indicating when we are looking for a Zookeeper connection to
  # become available.
  NO_ZOOKEEPER_CONNECTION = "No Zookeeper available: in isolated mode"


  # Where to put logs.
  LOG_FILE = "/var/log/appscale/controller-17443.log"


  # Where to put the pid of the controller.
  PID_FILE = "/var/run/appscale-controller.pid"


  # Default memory to allocate to each AppServer.
  DEFAULT_MEMORY = 400


  # List of parameters allowed in the set_parameter (and in AppScalefile
  # at this time). If a default value is specified, it will be used if the
  # parameter is unspecified. The last value (a boolean) indicates if the
  # parameter's value is of a sensitive nature and shouldn't be printed in
  # the logs.
  PARAMETER_CLASS = 0
  PARAMETER_DEFAULT = 1
  PARAMETER_SHOW = 2
  PARAMETERS_AND_CLASS = {
    'azure_subscription_id' => [ String, nil, false ],
    'azure_app_id' => [ String, nil, false ],
    'azure_app_secret_key' => [ String, nil, false ],
    'azure_tenant_id' => [ String, nil, false ],
    'azure_resource_group' => [ String, nil, false ],
    'azure_storage_account' => [ String, nil, false ],
    'azure_group_tag' => [ String, nil, false ],
    'appengine' => [ Fixnum, '2', true ],
    'appserver_timeout' => [ Fixnum, '180', true ],
    'autoscale' => [ TrueClass, 'True', true ],
    'client_secrets' => [ String, nil, false ],
    'controller_logs_to_dashboard' => [ TrueClass, 'False' ],
    'disks' => [ String, nil, true ],
    'ec2_access_key' => [ String, nil, false ],
    'ec2_secret_key' => [ String, nil, false ],
    'ec2_url' => [ String, nil, false ],
    'EC2_ACCESS_KEY' => [ String, nil, false ],
    'EC2_SECRET_KEY' => [ String, nil, false ],
    'EC2_URL' => [ String, nil, false ],
    'flower_password' => [ String, nil, false ],
    'gce_instance_type' => [ String, nil ],
    'gce_user' => [ String, nil, false ],
    'group' => [ String, nil, true ],
    'keyname' => [ String, nil, false ],
    'infrastructure' => [ String, nil, true ],
    'instance_type' => [ String, nil, true ],
    'login' => [ String, nil, true ],
    'machine' => [ String, nil, true ],
    'max_images' => [ Fixnum, '0', true ],
    'max_memory' => [ Fixnum, "#{DEFAULT_MEMORY}", true ],
    'min_images' => [ Fixnum, '1', true ],
    'region' => [ String, nil, true ],
    'replication' => [ Fixnum, '1', true ],
    'project' => [ String, nil, false ],
    'table' => [ String, 'cassandra', false ],
    'use_spot_instances' => [ TrueClass, nil, false ],
    'user_commands' => [ String, nil, true ],
    'verbose' => [ TrueClass, 'False', true ],
    'zone' => [ String, nil, true ]
  }


  # Template used for rsyslog configuration files.
  RSYSLOG_TEMPLATE_LOCATION = "#{APPSCALE_HOME}/lib/templates/rsyslog-app.conf"


  # Instance variables that we need to restore from the head node.
  DEPLOYMENT_STATE = [
    "@app_info_map",
    "@app_names",
    "@apps_loaded",
    "@nodes",
    "@options",
    "@last_decision"
  ]


  # Creates a new Djinn, which holds all the information needed to configure
  # and deploy all the services on this node.
  def initialize()
    # The password, or secret phrase, that is required for callers to access
    # methods exposed via SOAP.
    @@secret = HelperFunctions.get_secret()

    # An Array of Hashes, where each Hash contains a log message and the time
    # it was logged.
    @@logs_buffer = []

    @@log = Logger.new(STDOUT)
    @@log.level = Logger::INFO

    @my_index = nil
    @my_public_ip = nil
    @my_private_ip = nil
    @kill_sig_received = false
    @done_initializing = false
    @done_terminating = false
    @waiting_messages = []
    @waiting_messages.extend(MonitorMixin)
    @message_ready = @waiting_messages.new_cond
    @done_loading = false
    @state = "AppController just started"
    @all_stats = []
    @last_updated = 0
    @state_change_lock = Monitor.new()

    # These two variables are used to keep track of terminated or
    # unaccounted AppServers. Both needs some special cares, since we need
    # to terminate or remove them after some time.
    @unaccounted = {}
    @terminated = {}

    @initialized_apps = {}
    @total_req_rate = {}
    @current_req_rate = {}
    @last_sampling_time = {}
    @last_scaling_time = Time.now.to_i
    @app_upload_reservations = {}

    # This variable is used to keep track of the list of zookeeper servers
    # we have in this deployment.
    @zookeeper_data = []

    # This variable is used to keep track of the location files we write
    # when layout changes.
    @locations_content = ""

    # This variable keeps track of the state we read/write to zookeeper,
    # to avoid actions if nothing changed.
    @appcontroller_state = ""

    # The following variables are restored from the headnode ie they are
    # part of the common state of the running deployment.
    @app_info_map = {}
    @app_names = []
    @apps_loaded = []
    @nodes = []
    @options = {}
    @last_decision = {}

    # Make sure monit is started.
    MonitInterface.start_monit()
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
    return BAD_SECRET_MSG unless valid_secret?(secret)

    all_nodes = []
    @nodes.each { |node|
      all_nodes << node.to_hash()
    }

    return JSON.dump(all_nodes)
  end


  # A SOAP-exposed method that callers can use to get information about what
  # apps are running on this machine, as well as what ports they are bound to,
  # and what ports run nginx and haproxy in front of them.
  #
  # Args:
  #   secret: A String that authenticates callers.
  # Returns:
  #   BAD_SECRET_MSG if the caller could not be authenticated. If the caller
  #   can be authenticated, a JSON-dumped Hash containing information about
  #   applications on this machine is returned.
  def get_app_info_map(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    return JSON.dump(@app_info_map)
  end


  # A SOAP-exposed method that callers can use to tell this AppController that
  # an app hosted in this cloud needs to have its nginx reverse proxy serving
  # HTTP and HTTPS traffic on different ports.
  #
  # Args:
  #   appid: A String that names the application already running in this
  #     deployment that should be relocated.
  #   http_port: A String or Fixnum that names the port that should be used to
  #     serve HTTP traffic for this app.
  #   https_port: A String or Fixnum that names the port that should be used to
  #     serve HTTPS traffic for this app.
  #   secret: A String that authenticates callers.
  # Returns:
  #   "OK" if the relocation occurred successfully, and a String containing the
  #   reason why the relocation failed in all other cases.
  def relocate_app(appid, http_port, https_port, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    Djinn.log_debug("Received relocate_app for #{appid} for " +
        "http port #{http_port} and https port #{https_port}.")

    unless my_node.is_shadow?
      # We need to send the call to the shadow.
      Djinn.log_debug("Sending relocate_app for #{appid} to #{get_shadow}.")
      acc = AppControllerClient.new(get_shadow.private_ip, @@secret)
      begin
        return acc.relocate_app(appid, http_port, https_port)
      rescue FailedNodeException
        Djinn.log_warn("Failed to forward relocate_app call to #{get_shadow}.")
        return NOT_READY
      end
    end

    # Sanity checks on app ID and settings.
    return "Error: Can't relocate the #{appid} app." if RESERVED_APPS.include?(appid)
    begin
      http_port = Integer(http_port)
      https_port = Integer(https_port)
    rescue ArgumentError
      Djinn.log_warn("relocate_app received invalid port values.")
      return INVALID_REQUEST
    end
    APPS_LOCK.synchronize {
      if @app_info_map[appid].nil? or @app_info_map[appid]['nginx'].nil? or
          @app_info_map[appid]['nginx_https'].nil? or
          @app_info_map[appid]['haproxy'].nil?
        Djinn.log_warn("Unable to relocate due to missing app settings for: #{appid}.")
        return INVALID_REQUEST
      end

      # First, only let users relocate apps to ports that the firewall has open
      # for App Engine apps.
      if http_port != 80 and
         (http_port < Nginx::START_PORT or http_port > Nginx::END_PORT)
        return "Error: HTTP port must be 80, or in the range" +
          " #{Nginx::START_PORT}-#{Nginx::END_PORT}."
      end

      if (https_port < Nginx::START_PORT - Nginx::SSL_PORT_OFFSET or https_port >
          Nginx::END_PORT - Nginx::SSL_PORT_OFFSET) and https_port != 443
        return "Error: HTTPS port must be 443, or in the range " +
           "#{Nginx::START_PORT - Nginx::SSL_PORT_OFFSET}-" +
           "#{Nginx::END_PORT - Nginx::SSL_PORT_OFFSET}."
      end

      # We need to check if http_port and https_port are already in use by
      # another application, so we do that with find_lowest_free_port and we
      # fix the range to the single port.
      if find_lowest_free_port(http_port, http_port, appid) < 0
        return "Error: requested http port is already in use."
      end
      if find_lowest_free_port(https_port, https_port, appid) < 0
        return "Error: requested https port is already in use."
      end

      # Next, rewrite the nginx config file with the new ports
      @app_info_map[appid]['nginx'] = http_port
      @app_info_map[appid]['nginx_https'] = https_port
    }
    Djinn.log_info("Assigned ports for relocated app #{appid}.")
    my_public = my_node.public_ip

    # Finally, the AppServer takes in the port to send Task Queue tasks to
    # from a file. Update the file and restart the AppServers so they see
    # the new port. Do this in a separate thread to avoid blocking the caller.
    port_file = "#{APPSCALE_CONFIG_DIR}/port-#{appid}.txt"
    HelperFunctions.write_file(port_file, http_port)

    Thread.new {
      # Notify the UAServer about the new ports.
      uac = UserAppClient.new(my_node.private_ip, @@secret)
      success = uac.add_instance(appid, my_public, http_port, https_port)
      unless success
        Djinn.log_warn("Failed to store relocation ports for #{appid} via the uaserver.")
        return
      end

      # Notify nodes, and remove any running AppServer of the application.
      notify_restart_app_to_nodes([appid])

      # Once we've relocated the app, we need to tell the XMPPReceiver about the
      # app's new location.
      MonitInterface.restart("xmpp-#{appid}")
    }

    return "OK"
  end


  # A SOAP-exposed method that tells the AppController to terminate all services
  # in this AppScale deployment.
  #
  # Args:
  #   stop_deployment: A boolean to indicate if the whole deployment
  #                    should be stopped.
  #   secret         : A String used to authenticate callers.
  # Returns:
  #   A String indicating that the termination has started, or the reason why it
  #   failed.
  def kill(stop_deployment, secret)
    begin
      return BAD_SECRET_MSG unless valid_secret?(secret)
    rescue Errno::ENOENT
      # On appscale down, terminate may delete our secret key before we
      # can check it here.
      Djinn.log_debug("kill(): didn't find secret file. Continuing.")
    end
    @kill_sig_received = true

    Djinn.log_info("Received a stop request.")

    if my_node.is_shadow? and stop_deployment
      Djinn.log_info("Stopping all other nodes.")
      # Let's stop all other nodes.
      threads << Thread.new {
        @nodes.each { |node|
          if node.private_ip != my_node.private_ip
            acc = AppControllerClient.new(ip, @@secret)
            begin
              acc.kill(stop_deployment)
              Djinn.log_info("kill: sent kill command to node at #{ip}.")
            rescue FailedNodeException
              Djinn.log_warn("kill: failed to talk to node at #{ip} while.")
            end
          end
        }
      }
    end

    Djinn.log_info("---- Stopping AppController ----")

    return "OK"
  end

  # This method validates that the layout received is correct (both
  # syntactically and logically).
  #
  # Args:
  #   layout: this is a JSON structure containing the nodes
  #     informations (IPs, roles, instance ID etc...). These are the nodes
  #     specified in the AppScalefile at startup time.
  #   keyname: the key of this deployment, needed to initialize
  #     DjinnJobData.
  #
  # Returns:
  #   A DjinnJobData array suitale to be used in @nodes.
  #
  # Exception:
  #   AppScaleException: returns a message if the layout is not valid.
  def check_layout(layout, keyname)
    if layout.class != String
      msg = "Error: layout wasn't a String, but was a " + layout.class.to_s
      Djinn.log_error(msg)
      raise AppScaleException.new(msg)
    end
    begin
      locations = JSON.load(layout)
    rescue JSON::ParserError
      msg = "Error: got exception parsing JSON structure layout."
      Djinn.log_error(msg)
      raise AppScaleException.new(msg)
    end
    if locations.nil? || locations.empty?
      msg = "Error: layout is empty."
      Djinn.log_error(msg)
      raise AppScaleException.new(msg)
    end
    if locations.class != Array
      msg = "Error: layout is not an Array."
      Djinn.log_error(msg)
      raise AppScaleException.new(msg)
    end
    all_roles = []
    locations.each { |node|
      if node.class != Hash
        msg = "Error: node structure is not a Hash."
        Djinn.log_error(msg)
        raise AppScaleException.new(msg)
      end
      if !node['public_ip'] || !node['private_ip'] || !node['jobs'] ||
        !node['instance_id']
        msg = "Error: node layout is missing information #{node}."
        Djinn.log_error(msg)
        raise AppScaleException.new(msg)
        return msg
      elsif node['public_ip'].empty? || node['private_ip'].empty? ||
         node['jobs'].empty? || node['instance_id'].empty?
        msg = "Error: node layout is missing information #{node}."
        Djinn.log_error(msg)
        raise AppScaleException.new(msg)
      end
      if node['jobs'].class == String
        all_roles << node['jobs']
      elsif node['jobs'].class == Array
        all_roles += node['jobs']
      else
        msg = "Error: node jobs is not String or Array for #{node}."
        Djinn.log_error(msg)
        raise AppScaleException.new(msg)
      end
    }

    # Now we can check if we have the needed roles to start the
    # deployment.
    all_roles.uniq!
    ['appengine', 'shadow', 'load_balancer', 'login', 'zookeeper',
      'memcache', 'db_master', 'taskqueue_master'].each { |role|
      unless all_roles.include?(role)
        msg = "Error: layout is missing role #{role}."
        Djinn.log_error(msg)
        raise AppScaleException.new(msg)
      end
    }

    # Transform the hash into DjinnJobData and return it.
    nodes = Djinn.convert_location_array_to_class(locations, keyname)
    return nodes
  end

  # This method validate and set (if valid) the proper @options value.
  #
  # Args:
  #   options: a Hash containing the property and the value to set it to.
  #
  # Returns:
  #   A sanitized Hash of valid properties.
  def check_options(options)
    newoptions = {}
    if options.class != Hash
      Djinn.log_warn("check_options received a non-hash parameter.")
      return newoptions
    end

    options.each { |name, val|
      unless name.class == String
        Djinn.log_warn("Received an invalid property name of class #{name.class}.")
        next
      end
      key = name.gsub(NOT_EMAIL_REGEX, "")

      # Let's check if the property is a known one.
      unless PARAMETERS_AND_CLASS.has_key?(key)
        begin
          Djinn.log_warn("Removing unknown parameter '" + key.to_s + "'.")
        rescue
          Djinn.log_warn("Removing unknown paramete.")
        end
        next
      end

      # Check that the value that came in is a String or as final class of
      # the parameter. There is no boolean, so TrueClass and FalseClass
      # needs to be check both. If not, remove the parameter since we
      # won't be able to translate it.
      unless (val.class == String || val.class ==
              PARAMETERS_AND_CLASS[key][PARAMETER_CLASS] ||
              (PARAMETERS_AND_CLASS[key][PARAMETER_CLASS] == TrueClass &&
              val.class == FalseClass))
        if PARAMETERS_AND_CLASS[key][PARAMETER_SHOW]
          begin
            msg = "Removing parameter '" + key + "' with unknown value '" +\
              val.to_s + "'."
          rescue
            msg = "Removing parameter '" + key + "' with unknown value."
          end
        else
          msg = "Removing parameter '" + key + "' with unknown value."
        end
        Djinn.log_warn(msg)
        next
      end

      if PARAMETERS_AND_CLASS[key][PARAMETER_SHOW]
        msg = "Converting/checking '" + key + "' with value '" + val + "'."
      else
        msg = "Converting/checking '" + key + "."
      end
      Djinn.log_info(msg)

      # Let's check if we can convert them now to the proper class.
      if PARAMETERS_AND_CLASS[key][PARAMETER_CLASS] == Fixnum
        begin
          Integer(val)
        rescue
          if PARAMETERS_AND_CLASS[key][PARAMETER_SHOW]
            msg = "Warning: parameter '" + key + "' is not an integer (" +\
              val.to_s + "). Removing it."
          else
            msg = "Warning: parameter '" + key + "' is not an integer. Removing it."
          end
          Djinn.log_warn(msg)
          next
        end
      end

      # Booleans and Integer (basically non-String) seem to create issues
      # at the SOAP level (possibly because they are in a structure) with
      # message similar to "failed to serialize detail object". We convert
      # them here to String.
      if PARAMETERS_AND_CLASS[key][PARAMETER_CLASS] == TrueClass ||
         PARAMETERS_AND_CLASS[key][PARAMETER_CLASS] == Fixnum
        begin
          newval = val.to_s
        rescue
          msg = "Warning: cannot convert '" + key + "' to string. Removing it."
          Djinn.log_warn(msg)
          next
        end
      end

      # Strings may need to be sanitized.
      if PARAMETERS_AND_CLASS[key][PARAMETER_CLASS] == String
        # Some options shouldn't be sanitize.
        if key == 'user_commands' or key == 'azure_app_secret_key'
          newval = val
        # Keys have a relaxed sanitization process.
        elsif key.include? "_key" or key.include? "EC2_SECRET_KEY"
          newval = val.gsub(NOT_FQDN_OR_PLUS_REGEX, "")
        else
          newval = val.gsub(NOT_FQDN_REGEX, "")
        end
      end

      newoptions[key] = newval
      newval = "*****" unless PARAMETERS_AND_CLASS[key][2]
      Djinn.log_debug("Accepted option #{key}:#{newval}.")
    }

    return newoptions
  end

  def enforce_options()
    # Set the proper log level.
    new_level = Logger::INFO
    new_level = Logger::DEBUG if @options['verbose'].downcase == "true"
    @@log.level = new_level if @@log.level != new_level
  end

  # This is the method needed to get the current layout and options for
  # this deployment. The first AppController to receive this call is the
  # shadow node. It will then forward these information to all other
  # nodes.
  #
  # Args:
  #   layout: this is a JSON structure containing the node
  #     information (IPs, roles, instance ID etc...). These are the nodes
  #     specified in the AppScalefile at startup time.
  #   options: this is a Hash containing all the options and credentials
  #     (for autoscaling) pertinent to this deployment.
  def set_parameters(layout, options, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    # options is a JSON string that will be loaded into a Hash.
    if options.class != String
      msg = "Error: options wasn't a String, but was a " +
            options.class.to_s
      Djinn.log_error(msg)
      return msg
    end
    begin
      opts = JSON.load(options)
    rescue JSON::ParserError
      msg = "Error: got exception parsing JSON options."
      Djinn.log_error(msg)
      return msg
    end
    if opts.nil? || opts.empty?
      Djinn.log_info("Empty options: using defaults.")
    elsif opts.class != Hash
      msg = "Error: options is not a Hash."
      Djinn.log_error(msg)
      return msg
    else
      @options = check_options(opts)
    end

    # Let's validate we have the needed options defined.
    ['keyname', 'login', 'table'].each { |key|
      unless @options[key]
        msg = "Error: cannot find #{key} in options!" unless @options[key]
        Djinn.log_error(msg)
        return msg
      end
    }

    begin
      @state_change_lock.synchronize {
        @nodes = check_layout(layout, @options['keyname'])
      }
    rescue AppScaleException => e
      Djinn.log_error(e.message)
      return e.message
    end

    # Now let's make sure the parameters that needs to have values are
    # indeed defines, otherwise set the defaults.
    PARAMETERS_AND_CLASS.each { |key, _|
      if @options[key]
        # The parameter 'key' is defined, no need to do anything.
        next
      end
      if PARAMETERS_AND_CLASS[key][1]
         # The parameter has a default, and it's not defined. Adding
         # default value.
         @options[key] = PARAMETERS_AND_CLASS[key][1]
      end
    }
    enforce_options

    # From here on we do more logical checks on the values we received.
    # The first one is to check that max and min are set appropriately.
    # Max and min needs to be at least the number of started nodes, it
    # needs to be positive. Max needs to be no smaller than min.
    if Integer(@options['max_images']) < @nodes.length
      Djinn.log_warn("max_images is less than the number of nodes!")
      @options['max_images'] = @nodes.length.to_s
    end
    if Integer(@options['min_images']) < @nodes.length
      Djinn.log_warn("min_images is less than the number of nodes!")
      @options['min_images'] = @nodes.length.to_s
    end
    if Integer(@options['max_images']) < Integer(@options['min_images'])
      Djinn.log_warn("min_images is bigger than max_images!")
      @options['max_images'] = @options['min_images']
    end

    # We need to make sure this node is listed in the started nodes.
    find_me_in_locations()
    return "Error: Couldn't find me in the node map" if @my_index.nil?

    ENV['EC2_URL'] = @options['ec2_url']
    if @options['ec2_access_key'].nil?
      @options['ec2_access_key'] = @options['EC2_ACCESS_KEY']
      @options['ec2_secret_key'] = @options['EC2_SECRET_KEY']
      @options['ec2_url'] = @options['EC2_URL']
    end

    Djinn.log_run("mkdir -p #{PERSISTENT_MOUNT_POINT}/apps")

    Djinn.log_debug("set_parameters: set @options to #{@options}.")
    Djinn.log_debug("set_parameters: set @nodes to #{@nodes}.")

    return "OK"
  end


  # Gets the status of the current node in the AppScale deployment
  #
  # Args:
  #   secret: The shared key for authentication
  # Returns:
  #   A string with the current node's status
  #
  def status(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    stats = get_stats(secret)

    stats_str = <<-STATUS
    Currently using #{stats['cpu']} Percent CPU and #{stats['memory']} Percent Memory
    Hard disk is #{stats['disk']} Percent full
    Is currently: #{stats['roles'].join(', ')}
    Database is at #{stats['db_location']}
    Is in cloud: #{stats['cloud']}
    Current State: #{stats['state']}
    STATUS

    if my_node.is_shadow?
      apps = []
      stats['apps'].each { |key, _|
        apps << key
      }

      stats_str << "    Hosting the following apps: #{apps.join(', ')}\n"

      stats['apps'].each { |app_name, is_loaded|
        next unless is_loaded
        stats_str << "    Information for application: #{app_name}\n"
        stats_str << "        Language            : "
        if @app_info_map[app_name]['language'].nil?
          stats_str << "Unknown\n"
        else
          stats_str << "#{@app_info_map[app_name]['language']}\n"
        end
        stats_str << "        Number of AppServers: "
        if @app_info_map[app_name]['appengine'].nil?
          stats_str << "Unknown\n"
        else
          running = 0
          pending = 0
          @app_info_map[app_name]['appengine'].each { |location|
             _host, port = location.split(":")
             if Integer(port) > 0
               running += 1
             else
               pending += 1
             end
          }
          stats_str << "#{running} running"
          if pending > 0
            stats_str << ", #{pending} pending"
          end
          stats_str << "\n"
        end
        stats_str << "        HTTP port           : "
        if @app_info_map[app_name]['nginx'].nil?
          stats_str << "Unknown\n"
        else
          stats_str << "#{@app_info_map[app_name]['nginx']}\n"
        end
        stats_str << "        HTTPS port          : "
        if @app_info_map[app_name]['nginx_https'].nil?
          stats_str << "Unknown\n"
        else
          stats_str << "#{@app_info_map[app_name]['nginx_https']}\n"
        end
      }
    end

    return stats_str
  end

  # Upload a Google App Engine application into this AppScale deployment.
  #
  # Args:
  #   archived_file: A String, with the path to the compressed file containing
  #     the app.
  #   file_suffix: A String indicating what suffix the file should have.
  #   email: A String with the email address of the user that will own this app.
  #   secret: A String with the shared key for authentication.
  # Returns:
  #   A JSON-dumped Hash with fields indicating if the upload process began
  #   successfully, and a reservation ID that can be used with
  #   get_app_upload_status to see if the app has successfully uploaded or not.
  def upload_app(archived_file, file_suffix, email, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    unless my_node.is_shadow?
      Djinn.log_debug("Sending upload_app call to shadow.")
      acc = AppControllerClient.new(get_shadow.private_ip, @@secret)
      begin
        remote_file = [archived_file, file_suffix].join('.')
        HelperFunctions.scp_file(archived_file, remote_file,
                                 get_shadow.private_ip, get_shadow.ssh_key)
        return acc.upload_app(remote_file, file_suffix, email)
      rescue FailedNodeException => except
        Djinn.log_warn("Failed to forward upload_app call to shadow (#{get_shadow}).")
        return NOT_READY
      end
    end

    reservation_id = HelperFunctions.get_random_alphanumeric()
    @app_upload_reservations[reservation_id] = {'status' => 'starting'}

    Djinn.log_debug(
      "Received a request to upload app at #{archived_file}, with suffix " +
      "#{file_suffix}, with admin user #{email}.")

    Thread.new {
      # If the dashboard is on the same node as the shadow, the archive needs
      # to be copied to a location that includes the suffix.
      unless archived_file.match(/#{file_suffix}$/)
        new_location = [archived_file, file_suffix].join('.')
        Djinn.log_debug("Copying #{archived_file} to #{new_location}")
        FileUtils.copy(archived_file, new_location)
        archived_file = new_location
      end

      Djinn.log_debug("Uploading file at location #{archived_file}")
      keyname = @options['keyname']
      command = "#{UPLOAD_APP_SCRIPT} --file '#{archived_file}' " +
        "--email #{email} --keyname #{keyname} 2>&1"
      output = Djinn.log_run(command)
      if output.include?("Your app can be reached at the following URL")
        result = "true"
      else
        result = output
      end

      @app_upload_reservations[reservation_id]['status'] = result
      File.delete(archived_file)
    }

    return JSON.dump({
      'reservation_id' => reservation_id,
      'status' => 'starting'
    })
  end

  # Checks the status of the App Engine app uploading with the given reservation
  # ID.
  #
  # Args:
  #   reservation_id: A String that corresponds to the reservation ID given when
  #     the app upload process began.
  #   secret: A String with the shared key for authentication.
  # Returns:
  #   A String that indicates what the state is of the uploaded application. If
  #   the given reservation ID was not found, ID_NOT_FOUND is returned. If the
  #   caller attempts to authenticate with an invalid secret, BAD_SECRET_MSG is
  #   returned.
  def get_app_upload_status(reservation_id, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    unless my_node.is_shadow?
      Djinn.log_debug("Sending get_upload_status call to shadow.")
      acc = AppControllerClient.new(get_shadow.private_ip, @@secret)
      begin
        return acc.get_app_upload_status(reservation_id)
      rescue FailedNodeException
        Djinn.log_warn(
          "Failed to forward get_app_upload_status call to #{get_shadow}.")
        return NOT_READY
      end
    end

    if @app_upload_reservations.has_key?(reservation_id) &&
       @app_upload_reservations[reservation_id]['status']
      return @app_upload_reservations[reservation_id]['status']
    else
      return ID_NOT_FOUND
    end
  end

  # Gets the statistics of all the nodes in the AppScale deployment.
  #
  # Args:
  #   secret: A string with the shared key for authentication.
  # Returns:
  #   A JSON string with the statistics of the nodes.
  def get_stats_json(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    unless my_node.is_shadow?
      Djinn.log_debug("Sending get_stats_json call to shadow.")
      acc = AppControllerClient.new(get_shadow.private_ip, @@secret)
      begin
        return acc.get_stats_json()
      rescue FailedNodeException
        Djinn.log_warn(
          "Failed to forward get_stats_json call to #{get_shadow}.")
        return NOT_READY
      end
    end

    return JSON.dump(@all_stats)
  end


  # Updates our locally cached information about the CPU, memory, and disk
  # usage of each machine in this AppScale deployment.
  def update_node_info_cache()
    new_stats = []

    Thread.new {
      @nodes.each { |node|
        ip = node.private_ip
        if ip == my_node.private_ip
          new_stats << get_stats(@@secret)
        else
          acc = AppControllerClient.new(ip, @@secret)
          begin
            new_stats << acc.get_stats()
          rescue FailedNodeException
            Djinn.log_warn("Failed to get status update from node at #{ip}, so " +
              "not adding it to our cached info.")
          end
        end
      }
      @all_stats = new_stats
    }
  end


  # Gets the database information of the AppScale deployment.
  #
  # Args:
  #   secret: A string with the shared key for authentication.
  # Returns:
  #   A JSON string with the database information.
  def get_database_information(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    tree = { :table => @options['table'], :replication => @options['replication'],
      :keyname => @options['keyname'] }
    return JSON.dump(tree)
  end

  # Gets the statistics of only this node.
  #
  # Args:
  #   secret: A string with the shared key for authentication.
  # Returns:
  #   A Hash with the statistics of this node.
  def get_stats(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    usage = HelperFunctions.get_usage()
    mem = sprintf("%3.2f", usage['mem'])
    usagecpu = sprintf("%3.2f", usage['cpu'])

    jobs = my_node.jobs or ["none"]
    # don't use an actual % below, or it will cause a string format exception
    stats = {
      'ip' => my_node.public_ip,
      'private_ip' => my_node.private_ip,
      'cpu' => usagecpu,
      'num_cpu' => usage['num_cpu'],
      'load' => usage['load'],
      'memory' => mem,
      'free_memory' => Integer(usage['free_mem']),
      'disk' => usage['disk'],
      'roles' => jobs,
      'cloud' => my_node.cloud,
      'state' => @state
    }

    # As of 2.5.0, db_locations is used by the tools to understand when
    # the AppController is setup and ready to go: we make sure here to
    # follow that rule.
    if @done_initializing
      stats['db_location'] = get_db_master.public_ip
    else
      stats['db_location'] = NOT_UP_YET
    end

    stats['apps'] = {}
    @app_names.each { |name|
      next if RESERVED_APPS.include?(name)
      stats['apps'][name] = @apps_loaded.include?(name)
    }
    return stats
  end


  # Runs the Groomer service that the Datastore provides, which cleans up
  # deleted entries and generates statistics about the entities stored for each
  # application.
  #
  # Args:
  #   secret: A String with the shared key for authentication.
  # Returns:
  #   'OK' if the groomer was invoked, and BAD_SECRET_MSG if the user failed to
  #   authenticate correctly.
  def run_groomer(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    Thread.new {
      run_groomer_command = `which appscale-groomer`.chomp
      if my_node.is_db_master?
        Djinn.log_run(run_groomer_command)
      else
        db_master = get_db_master()
        HelperFunctions.run_remote_command(db_master.private_ip,
          run_groomer_command, db_master.ssh_key, NO_OUTPUT)
      end
    }

    return 'OK'
  end


  # Queries the AppController for a list of instance variables whose names match
  # the given regular expression, as well as the values associated with each
  # match.
  #
  # Args:
  #   property_regex: A String that will be used as the regular expression,
  #     determining which instance variables should be returned.
  #   secret: A String with the shared key for authentication.
  #
  # Returns:
  #   A JSON-dumped Hash mapping each instance variable matching the given regex
  #   to the value it is bound to.
  def get_property(property_regex, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    unless my_node.is_shadow?
      # We need to send the call to the shadow.
      Djinn.log_debug("Sending get_property for #{appid} to #{get_shadow}.")
      acc = AppControllerClient.new(get_shadow.private_ip, @@secret)
      begin
        return acc.get_property(property_regex)
      rescue FailedNodeException
        Djinn.log_warn("Failed to forward get_property call to #{get_shadow}.")
        return NOT_READY
      end
    end

    Djinn.log_info("Received request to get properties matching #{property_regex}.")
    properties = {}
    PARAMETERS_AND_CLASS.each { |key, val|
      begin
        if key =~ /\A#{property_regex}\Z/
          unless val[2]
            properties[key] = "*****"
            next
          end
          if @options[key].nil?
            properties[key] = val[1]
          else
            properties[key] = @options[key]
          end
        end
      rescue RegexpError
        Djinn.log_warn("get_property: got invalid regex (#{property_regex}).")
      end
    }

    Djinn.log_debug("Caller asked for instance variables matching regex " +
      "#{property_regex}, returning response #{properties.inspect}")
    return JSON.dump(properties)
  end


  # Sets the named instance variable to the given value.
  #
  # Args:
  #   property_name: A String naming the instance variable that should be set.
  #   property_value: A String or Fixnum that provides the value for the given
  #     property name.
  #   secret: A String with the shared key for authentication.
  #
  # Returns:
  #   A String containing:
  #     - 'OK' if the value was successfully set.
  #     - KEY_NOT_FOUND if there is no instance variable with the given name.
  #     - NOT_READY if this node is not shadow, and cannot talk to shadow.
  #     - BAD_SECRET_MSG if the caller could not be authenticated.
  def set_property(property_name, property_value, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    if property_name.class != String or property_value.class != String
      Djinn.log_warn("set_property: received non String parameters.")
      return KEY_NOT_FOUND
    end

    unless my_node.is_shadow?
      # We need to send the call to the shadow.
      Djinn.log_debug("Sending set_property for #{appid} to #{get_shadow}.")
      acc = AppControllerClient.new(get_shadow.private_ip, @@secret)
      begin
        return acc.set_property(property_name, property_value)
      rescue FailedNodeException
        Djinn.log_warn("Failed to forward set_property call to #{get_shadow}.")
        return NOT_READY
      end
    end

    Djinn.log_info("Received request to change #{property_name} to #{property_value}.")
    opts = {}
    opts[property_name] = property_value
    newopts = check_options(opts)

    # If we don't have any option to set, property was invalid.
    if newopts.length == 0
      Djinn.log_info("Failed to set property '#{property_name}'.")
      return KEY_NOT_FOUND
    end


    # Let's keep an old copy of the options: we'll need them to check if
    # something changed and we need to act.
    old_options = @options.clone
    newopts.each { |key, val|
      # We give some extra information to the user about some properties.
      if key == "keyname"
        Djinn.log_warn("Changing keyname can break your deployment!")
      end
      if key == "max_memory"
        Djinn.log_warn("max_memory will be enforced on new AppServers only.")
      end
      if key == "min_images"
        unless is_cloud?
          Djinn.log_warn("min_images is not used in non-cloud infrastructures.")
        end
        if Integer(val) < Integer(@options['min_images'])
          Djinn.log_warn("Invalid input: cannot lower min_images!")
          return "min_images cannot be less than the nodes defined in ips_layout"
        end
      end
      if key == "max_images"
        unless is_cloud?
          Djinn.log_warn("max_images is not used in non-cloud infrastructures.")
        end
        if Integer(val) < Integer(@options['min_images'])
          Djinn.log_warn("Invalid input: max_images is smaller than min_images!")
          return "max_images is smaller than min_images."
        end
      end
      if key == "flower_password"
        TaskQueue.stop_flower
        TaskQueue.start_flower(@options['flower_password'])
      end
      if key == "replication"
        Djinn.log_warn("replication cannot be changed at runtime.")
        next
      end
      @options[key] = val
      Djinn.log_info("Successfully set #{key} to #{val}.")
    }
    # Act upon changes.
    enforce_options unless old_options == @options

    return 'OK'
  end

  # Checks ZooKeeper to see if the deployment ID exists.
  # Returns:
  #   A boolean indicating whether the deployment ID has been set or not.
  def deployment_id_exists(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    return ZKInterface.exists?(DEPLOYMENT_ID_PATH)
  end

  # Retrieves the deployment ID from ZooKeeper.
  # Returns:
  #   A string that contains the deployment ID.
  def get_deployment_id(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    begin
      return ZKInterface.get(DEPLOYMENT_ID_PATH)
    rescue FailedZooKeeperOperationException => e
      Djinn.log_warn("(get_deployment_id) failed talking to zookeeper " +
        "with #{e.message}.")
      return
    end
  end

  # Sets deployment ID in ZooKeeper.
  # Args:
  #   id: A string that contains the deployment ID.
  def set_deployment_id(secret, id)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    begin
      ZKInterface.set(DEPLOYMENT_ID_PATH, id, false)
    rescue FailedZooKeeperOperationException => e
      Djinn.log_warn("(set_deployment_id) failed talking to zookeeper " +
        "with #{e.message}.")
    end
    return
  end

  # Enables or disables datastore writes on this node.
  # Args:
  #   read_only: A string that indicates whether to turn read-only mode on or
  #     off.
  def set_node_read_only(read_only, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return INVALID_REQUEST unless %w(true false).include?(read_only)
    read_only = read_only == 'true'

    DatastoreServer.set_read_only_mode(read_only)
    if read_only
      GroomerService.stop()
    else
      GroomerService.start()
    end

    return 'OK'
  end

  # Enables or disables datastore writes on this deployment.
  # Args:
  #   read_only: A string that indicates whether to turn read-only mode on or
  #     off.
  def set_read_only(read_only, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return INVALID_REQUEST unless %w(true false).include?(read_only)

    @nodes.each { | node |
      if node.is_db_master? or node.is_db_slave?
        acc = AppControllerClient.new(node.private_ip, @@secret)
        response = acc.set_node_read_only(read_only)
        return response unless response == 'OK'
      end
    }

    return 'OK'
  end

  # Checks if the primary database node is ready. For Cassandra, this is needed
  # because the seed node needs to start before the other nodes.
  # Args:
  #   secret: A string that authenticates the caller.
  # Returns:
  #   A string indicating whether or not the primary database node is ready.
  def primary_db_is_up(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    primary_ip = get_db_master.private_ip
    unless my_node.is_db_master?
      Djinn.log_debug("Asking #{primary_ip} if database is ready.")
      acc = AppControllerClient.new(get_db_master.private_ip, @@secret)
      begin
        return acc.primary_db_is_up()
      rescue FailedNodeException
        Djinn.log_warn("Unable to ask #{primary_ip} if database is ready.")
        return NOT_READY
      end
    end

    lock_obtained = NODETOOL_LOCK.try_lock
    begin
      return NOT_READY unless lock_obtained
      output = `"#{NODETOOL}" status`
      ready = false
      output.split("\n").each { |line|
        ready = true if line.start_with?('UN') && line.include?(primary_ip)
      }
      return "#{ready}"
    ensure
      NODETOOL_LOCK.unlock
    end
  end

  # Queries the UserAppServer to see if the named application exists,
  # and if it is listening to any port.
  #
  # Args:
  #   appname: The name of the app that we should check for existence.
  # Returns:
  #   A boolean indicating whether or not the user application exists.
  def does_app_exist(appname, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    begin
      uac = UserAppClient.new(my_node.private_ip, @@secret)
      return uac.does_app_exist?(appname)
    rescue FailedNodeException
      Djinn.log_warn("Failed to talk to the UserAppServer to check if the  " +
        "application #{appname} exists")
    end
  end

  # Resets a user's password.
  #
  # Args:
  #   username: The email address for the user whose password will be changed.
  #   password: The SHA1-hashed password that will be set as the user's password.
  def reset_password(username, password, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    begin
      uac = UserAppClient.new(my_node.private_ip, @@secret)
      return uac.change_password(username, password)
    rescue FailedNodeException
      Djinn.log_warn("Failed to talk to the UserAppServer while resetting " +
        "the user's password.")
    end
  end

  # Queries the UserAppServer to see if the given user exists.
  #
  # Args:
  #   username: The email address registered as username for the user's application.
  def does_user_exist(username, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    begin
      uac = UserAppClient.new(my_node.private_ip, @@secret)
      return uac.does_user_exist?(username)
    rescue FailedNodeException
      Djinn.log_warn("Failed to talk to the UserAppServer to check if the " +
        "the user #{username} exists.")
    end
  end

  # Creates a new user account, with the given username and hashed password.
  #
  # Args:
  #   username: An email address that should be set as the new username.
  #   password: A sha1-hashed password that is bound to the given username.
  #   account_type: A str that indicates if this account can be logged into
  #     by XMPP users.
  def create_user(username, password, account_type, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    begin
      uac = UserAppClient.new(my_node.private_ip, @@secret)
      return uac.commit_new_user(username, password, account_type)
    rescue FailedNodeException
      Djinn.log_warn("Failed to talk to the UserAppServer while committing " +
        "the user #{username}.")
    end
  end

  # Grants the given user the ability to perform any administrative action.
  #
  # Args:
  #   username: The e-mail address that should be given administrative authorizations.
  def set_admin_role(username, is_cloud_admin, capabilities, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    begin
      uac = UserAppClient.new(my_node.private_ip, @@secret)
      return uac.set_admin_role(username, is_cloud_admin, capabilities)
    rescue FailedNodeException
      Djinn.log_warn("Failed to talk to the UserAppServer while setting admin role " +
        "for the user #{username}.")
    end
  end

  # Retrieve application metadata from the UAServer.
  #
  #  Args:
  #    app_id: A string containing the application ID.
  #  Returns:
  #    A JSON-encoded string containing the application metadata.
  def get_app_data(app_id, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    begin
      uac = UserAppClient.new(my_node.private_ip, @@secret)
      return uac.get_app_data(app_id)
    rescue FailedNodeException
      Djinn.log_warn("Failed to talk to the UserAppServer while getting the app " +
        "admin for the application #{app_id}.")
    end
  end

  # Tells the UserAppServer to reserve the given app_id for
  # a particular user.
  #
  # Args:
  #   username: A str representing the app administrator's e-mail address.
  #   app_id: A str representing the application ID to reserve.
  #   app_language: The runtime (Python 2.5/2.7, Java, or Go) that the app
  #     runs over.
  def reserve_app_id(username, app_id, app_language, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    begin
      uac = UserAppClient.new(my_node.private_ip, @@secret)
      return uac.commit_new_app_name(username, app_id, app_language)
    rescue FailedNodeException
      Djinn.log_warn("Failed to talk to the UserAppServer while reserving app id " +
        "for the application #{app_id}.")
    end
  end

  # Removes an application and stops all AppServers hosting this application.
  #
  # Args:
  #   app_name: The application to stop
  #   secret: Shared key for authentication
  #
  def stop_app(app_name, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    unless my_node.is_shadow?
      Djinn.log_debug("Sending stop_app call for #{app_name} to shadow.")
      acc = AppControllerClient.new(get_shadow.private_ip, @@secret)
      begin
        return acc.stop_app(app_name)
      rescue FailedNodeException => except
        Djinn.log_warn("Failed to forward stop_app call to shadow (#{get_shadow}).")
        return NOT_READY
      end
    end

    app_name.gsub!(/[^\w\d\-]/, "")
    return "false: #{app_name} is a reserved app." if RESERVED_APPS.include?(app_name)
    Djinn.log_info("Shutting down app named [#{app_name}]")
    result = ""

    # Since stopping an application can take some time, we do it in a
    # thread.
    Thread.new {
      begin
        uac = UserAppClient.new(my_node.private_ip, @@secret)
        if not uac.does_app_exist?(app_name)
          Djinn.log_info("(stop_app) #{app_name} does not exist.")
        else
          result = uac.delete_app(app_name)
          Djinn.log_debug("(stop_app) delete_app returned: #{result}.")
        end
      rescue FailedNodeException
        Djinn.log_warn("(stop_app) delete_app: failed to talk " +
          "to the UserAppServer.")
      end

      # If this node has any information about AppServers for this app,
      # clear that information out.
      APPS_LOCK.synchronize {
        @app_info_map.delete(app_name) unless @app_info_map[app_name].nil?
        @apps_loaded = @apps_loaded - [app_name]
        @app_names = @app_names - [app_name]
      }

      # To prevent future deploys from using the old application code, we
      # force a removal of the application status on disk (for example the
      # code and cronjob) right now.
      check_stopped_apps
    }

    return "true"
  end

  # Stop taskqueue worker on this local machine.
  #
  # Args:
  #   app: The application ID.
  def maybe_stop_taskqueue_worker(app)
    if my_node.is_taskqueue_master? or my_node.is_taskqueue_slave?
      Djinn.log_info("Stopping TaskQueue workers for app #{app}")
      tqc = TaskQueueClient.new(my_node.private_ip)
      begin
        result = tqc.stop_worker(app)
        Djinn.log_info("Stopped TaskQueue workers for app #{app}: #{result}")
      rescue FailedNodeException
        Djinn.log_warn("Failed to stop TaskQueue workers for app #{app}")
      end
    end
  end


  # Reload the queue information of an app and reload the queues if needed.
  #
  # Args:
  #   app: The application ID.
  def maybe_reload_taskqueue_worker(app)
    if my_node.is_taskqueue_master? or my_node.is_taskqueue_slave?
      tqc = TaskQueueClient.new(my_node.private_ip)
      begin
        result = tqc.reload_worker(app)
        Djinn.log_info("Checking TaskQueue worker for app #{app}: #{result}")
      rescue FailedNodeException
        Djinn.log_warn("Failed to reload TaskQueue workers for app #{app}")
      end
    end
  end


  # Tell all nodes to restart some applications.
  #
  # Args:
  #   apps_to_restart: An Array containing the app_id to restart.
  def notify_restart_app_to_nodes(apps_to_restart)
    return if apps_to_restart.empty?

    Djinn.log_info("Remove old AppServers for #{apps_to_restart}.")
    APPS_LOCK.synchronize {
      apps_to_restart.each{ |app|
        @app_info_map[app]['appengine'].clear
      }
    }

    Djinn.log_info("Notify nodes to restart #{apps_to_restart}.")
    @nodes.each_index { |index|
      result = ""
      ip = @nodes[index].private_ip
      next if my_node.private_ip == ip

      acc = AppControllerClient.new(ip, @@secret)
      begin
        result = acc.set_apps_to_restart(apps_to_restart)
      rescue FailedNodeException
        Djinn.log_warn("Couldn't tell #{ip} to restart #{apps_to_restart}.")
      end
      Djinn.log_debug("Set apps to restart at #{ip} returned #{result}.")
    }
  end


  # Start a new, or update an old version of applications. This method
  # assumes that the application tarball(s) have already been uploaded.
  # Only the leader will update the application, so the message is
  # forwarded if arrived to the wrong node.
  #
  # Args:
  #   apps: An Array containing the app_id to start or update.
  #   secret: A String containing the deployment secret.
  def update(apps, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    # Few sanity checks before acting.
    return "apps was not an Array but was a #{apps.class}." if apps.class != Array
    unless my_node.is_shadow?
       Djinn.log_debug("Sending update call for #{apps} to shadow.")
       acc = AppControllerClient.new(get_shadow.private_ip, @@secret)
       begin
         return acc.update(apps)
       rescue FailedNodeException => except
         Djinn.log_warn("Failed to forward update call to shadow (#{get_shadow}).")
         return NOT_READY
       end
    end

    RESERVED_APPS.each { |reserved_app|
      if apps.include?(reserved_app)
        Djinn.log_warn("Cannot update reserved app #{reserved_app}.")
        apps.delete(reserved_app)
      end
    }
    Djinn.log_info("Received request to update these apps: #{apps.join(', ')}.")

    # Begin by marking the apps that should be running.
    apps_to_restart = []
    failed_apps = []
    APPS_LOCK.synchronize {
      # Get a list of the apps we need to restart.
      apps_to_restart = @apps_loaded & apps
      Djinn.log_debug("Apps to restart are #{apps_to_restart}.")

      # Next, check if the language of the application is correct.
      apps.each { |app|
        if @app_info_map[app] && @app_info_map[app]['language'] &&
          @app_info_map[app]['language'] != get_app_language(app)
          failed_apps << app
        end
      }
    }
    failed_apps.each { |app|
      apps_to_restart.delete(app)
      stop_app(app, @@secret)
      Djinn.log_error("Disabled #{app} since language doesn't match our record.")
    }

    # Make sure we have the latest code deployed.
    apps.each { |appid|
      APPS_LOCK.synchronize {
        setup_app_dir(appid, true)
      }
    }

    unless apps_to_restart.empty?
      apps_to_restart.each { |appid|
        location = "#{PERSISTENT_MOUNT_POINT}/apps/#{appid}.tar.gz"
        begin
          ZKInterface.clear_app_hosters(appid)
          ZKInterface.add_app_entry(appid, my_node.private_ip, location)
        rescue FailedZooKeeperOperationException => e
          Djinn.log_warn("(update) couldn't talk with zookeeper while " +
            "working on app #{appid} with #{e.message}.")
        end
      }

      # Notify nodes, and remove any running AppServer of the application.
      notify_restart_app_to_nodes(apps_to_restart)
    end

    APPS_LOCK.synchronize {
      @app_names |= apps
    }
    Djinn.log_debug("Done updating apps!")

    return "OK"
  end

  # Adds the list of apps that should be restarted to this node's list of apps
  # that should be restarted.
  #
  # Args:
  #   apps_to_restart: An Array of Strings, where each String is an appid
  #     corresponding to an application that should be restarted.
  #   secret: The String that authenticates the caller.
  # Returns:
  #   A String indicating that the SOAP call succeeded, or the reason why it
  #   did not.
  def set_apps_to_restart(apps_to_restart, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return INVALID_REQUEST if apps_to_restart.class != Array

    Djinn.log_debug("Apps to restart called for [#{apps_to_restart.join(', ')}]")
    restart_apps = []
    APPS_LOCK.synchronize {
      apps_to_restart.each { |app|
        unless @apps_loaded.include?(app)
          Djinn.log_warn("Ignoring request to restart non-running app #{app}.")
          next
        end
        restart_apps << app
      }
    }

    # Make sure we pull a new version of the application code. Since it
    # can take some time, we do it in a thread.
    Thread.new {
      restart_apps.each{ |app|
        APPS_LOCK.synchronize {
          setup_app_dir(app, true)
        }
      }
    }

    return "OK"
  end

  def get_all_public_ips(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    public_ips = []
    @nodes.each { |node|
      public_ips << node.public_ip
    }
    return JSON.dump(public_ips)
  end

  def job_start(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    Djinn.log_info("==== Starting AppController (pid: #{Process.pid}) ====")

    # This pid is used to control this deployment using the init script.
    HelperFunctions.write_file(PID_FILE, "#{Process.pid}")

    # We reload our old IPs (if we find them) so we can check later if
    # they changed and act accordingly.
    begin
      @my_private_ip = HelperFunctions.read_file("#{APPSCALE_CONFIG_DIR}/my_private_ip")
      @my_public_ip = HelperFunctions.read_file("#{APPSCALE_CONFIG_DIR}/my_public_ip")
    rescue Errno::ENOENT
      Djinn.log_warn("my_public_ip or my_private_ip disappeared.")
      @my_private_ip = nil
      @my_public_ip = nil
    end

    # If we have the ZK_LOCATIONS_FILE, the deployment has already been
    # configured and started. We need to check if we are a zookeeper host
    # and start it if needed.
    if File.exists?(ZK_LOCATIONS_FILE)
      # We need to check our saved IPs with the list of zookeeper nodes
      # (IPs can change in cloud environments).
      if @my_private_ip.nil?
        @state = "Cannot find my old private IP address."
        HelperFunctions.log_and_crash(@state, WAIT_TO_CRASH)
      end

      # Restore the initial list of zookeeper nodes.
      zookeeper_data = HelperFunctions.read_json_file(ZK_LOCATIONS_FILE)
      @zookeeper_data = zookeeper_data['locations']
      if @zookeeper_data.include?(@my_private_ip) && !is_zookeeper_running?
        # We are a zookeeper host and we need to start it.
        begin
          start_zookeeper(false)
        rescue FailedZooKeeperOperationException
          @state = "Couldn't start Zookeeper."
          HelperFunctions.log_and_crash(@state, WAIT_TO_CRASH)
        end
      end
      pick_zookeeper(@zookeeper_data)
    end

    # We need to wait for the 'state', that is the deployment layouts and
    # the options for this deployment. It's either a save state from a
    # previous start, or it comes from the tools. If the tools communicate
    # the deployment's data, then we are the headnode.
    unless restore_appcontroller_state()
      # Remove old copies of the RESERVED apps code. We need a fresh copy
      # every time we boot.
      RESERVED_APPS.each { |reserved_app|
        app_dir = "#{HelperFunctions.get_app_path(reserved_app)}/app"
        app_path = "#{PERSISTENT_MOUNT_POINT}/apps/#{reserved_app}.tar.gz"
        FileUtils.rm_rf([app_dir, app_path])
      }
      erase_old_data()
      wait_for_data()
    end
    parse_options()

    # Load datastore helper.
    # TODO: this should be the class or module.
    table = @options['table']
    # require db_file
    begin
      require "#{table}_helper"
    rescue => e
      backtrace = e.backtrace.join("\n")
      HelperFunctions.log_and_crash("Unable to find #{table} helper." +
        " Please verify datastore type: #{e}\n#{backtrace}")
    end

    # We reset the kill signal received since we are starting now.
    @kill_sig_received = false

    # From here on we have the basic local state that allows to operate.
    # In particular we know our roles, and the deployment layout. Let's
    # start attaching any permanent disk we may have associated with us.
    start_infrastructure_manager
    mount_persistent_storage

    find_me_in_locations
    write_database_info
    update_firewall

    # If we are the headnode, we may need to start/setup all other nodes.
    # Better do it early on, since it may take some time for the other
    # nodes to start up.
    if my_node.is_shadow?
      build_uncommitted_changes

      Djinn.log_info("Preparing other nodes for this deployment.")
      initialize_nodes_in_parallel(@nodes)
    end

    # Initialize the current server and starts all the API and essential
    # services. The functions are idempotent ie won't restart already
    # running services and can be ran multiple time with no side effect.
    initialize_server
    start_stop_api_services

    # Now that we are done loading, we can set the monit job to check the
    # AppController. At this point we are resilient to failure (ie the AC
    # will restart if needed).
    set_appcontroller_monit()
    @done_loading = true

    pick_zookeeper(@zookeeper_data)
    write_our_node_info()
    wait_for_nodes_to_finish_loading(@nodes)

    # This variable is used to keep track of the last time we printed some
    # statistics to the log.
    last_print = Time.now.to_i

    until @kill_sig_received do
      # We want to ensure monit stays up all the time, since we rely on
      # it for services and AppServers.
      unless MonitInterface.start_monit()
        Djinn.log_warn("Monit was not running: restarted it.")
      end

      write_database_info
      update_firewall
      write_zookeeper_locations

      # This call will block if we cannot reach a zookeeper node, but will
      # be very fast if we have an available connection. The function sets
      # the state in case we are looking for a zookeeper server.
      pick_zookeeper(@zookeeper_data)

      @state = "Done starting up AppScale, now in heartbeat mode"

      # We save the current @options and roles to check if
      # restore_appcontroller_state modifies them.
      old_options = @options.clone
      old_jobs = my_node.jobs

      # The following is the core of the duty cycle: start new apps,
      # restart apps, terminate non-responsive AppServers, and autoscale.
      # Every other node syncs its state with the login node state.
      if my_node.is_shadow?
        flush_log_buffer()
        send_instance_info_to_dashboard()
        update_node_info_cache()
        backup_appcontroller_state()

        APPS_LOCK.synchronize {
          starts_new_apps_or_appservers()
          scale_appservers_within_nodes()
        }
        if SCALE_LOCK.locked?
          Djinn.log_debug("Another thread is already working with the" +
              " InfrastructureManager.")
        else
          Thread.new {
            SCALE_LOCK.synchronize {
              scale_appservers_across_nodes()
            }
          }
        end
      elsif !restore_appcontroller_state()
        Djinn.log_warn("Cannot talk to zookeeper: in isolated mode.")
        next
      end

      # We act here if options or roles for this node changed.
      check_role_change(old_options, old_jobs)

      # Check the running, terminated, pending AppServers.
      check_running_apps

      # Detect applications that have been undeployed and terminate all
      # running AppServers.
      check_stopped_apps

      # Load balancers and shadow need to check/update nginx/haproxy.
      if my_node.is_load_balancer?
        APPS_LOCK.synchronize {
          check_haproxy
        }
      end

      # Print stats in the log recurrently; works as a heartbeat mechanism.
      if last_print < (Time.now.to_i - 60 * PRINT_STATS_MINUTES)
        if my_node.is_shadow? && @options['autoscale'].downcase != "true"
          Djinn.log_info("--- This deployment has autoscale disabled.")
        end
        stats = JSON.parse(get_all_stats(secret))
        Djinn.log_info("--- Node at #{stats['public_ip']} has " +
          "#{stats['memory']['available']/(1024*1024)}MB memory available " +
          "and knows about these apps #{stats['apps']}.")
        last_print = Time.now.to_i
      end

      Kernel.sleep(DUTY_CYCLE)
    end
  end

  def is_appscale_terminated(secret)
    begin
      bad_secret = JSON.dump({'status'=>BAD_SECRET_MSG})
      return bad_secret unless valid_secret?(secret)
    rescue Errno::ENOENT
      # On appscale down, terminate may delete our secret key before we
      # can check it here.
      Djinn.log_debug("run_terminate(): didn't find secret file. Continuing.")
    end
    return @done_terminating
  end


  def run_terminate(clean, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    if my_node.is_shadow?
      begin
        bad_secret = JSON.dump({'status'=>BAD_SECRET_MSG})
        return bad_secret unless valid_secret?(secret)
      rescue Errno::ENOENT
        # On appscale down, terminate may delete our secret key before we
        # can check it here.
        Djinn.log_debug("run_terminate(): didn't find secret file. Continuing.")
      end
      Djinn.log_info("Received a stop request.")
      Djinn.log_info("Stopping all other nodes.")
      Thread.new {
        terminate_appscale_in_parallel(clean){|node| send_client_message(node)}
        @done_terminating = true
      }
      # Return a "request id" for future use in sending and receiving messages.
      return SecureRandom.hex
    end
  end


  def terminate_appscale(node_to_terminate, clean)
    ip = node_to_terminate.private_ip
    Djinn.log_info("Running terminate.rb on the node at IP address #{ip}")
    ssh_key = node_to_terminate.ssh_key

    # Add ' clean' as parameter to terminate.rb if clean is true
    extra_command = clean.downcase == 'true' ? ' clean' : ''

    # Run terminate.rb on node
    begin
      Timeout.timeout(WAIT_TO_CRASH) {
        HelperFunctions.sleep_until_port_is_open(ip, SSH_PORT)
      }
    rescue Timeout::Error => e
      # Return ip, status, and output of terminated node
      return {'ip'=>ip, 'status'=> false,
              'output'=>"Waiting for port #{SSH_PORT} returned #{e.message}"}
    end
    output = HelperFunctions.run_remote_command(ip,
        "ruby /root/appscale/AppController/terminate.rb#{extra_command}",
        ssh_key, true)

    # terminate.rb will print "OK" if it ran successfully
    status = output.chomp!("OK").nil? ? false : true

    # Get the output of 'ps x' from node
    output += HelperFunctions.run_remote_command(ip, 'ps x', ssh_key, true)
    Djinn.log_debug("#{ip} terminated:#{status}\noutput:#{output}")

    # Return ip, status, and output of terminated node
    return {'ip'=>ip, 'status'=> status, 'output'=>output}
  end


  def terminate_appscale_in_parallel(clean)
    # Let's stop all other nodes.
    threads = []
    @nodes.each { |node|
      if node.private_ip != my_node.private_ip
        threads << Thread.new {
          Thread.current[:output] = terminate_appscale(node, clean)
        }
      end
    }

    threads.each do |t|
      t.join
      yield t[:output]
    end

    return "OK"
  end


  # Adds message to queue so it can be received by client.
  def send_client_message(message)
    @waiting_messages.synchronize {
      @waiting_messages.push(message)
      Djinn.log_debug(@waiting_messages)
      @message_ready.signal
    }
  end

  # Method ran by client to access the messages in @waiting_messages. Client
  # must send a timeout so that the server will not clear the messages.
  def receive_server_message(timeout, secret)
    was_queue_emptied = false
    begin
      Timeout.timeout(timeout.to_i) {
        begin
          bad_secret = JSON.dump({'status'=>BAD_SECRET_MSG})
          return bad_secret unless valid_secret?(secret)
        rescue Errno::ENOENT
          # On appscale down, terminate may delete our secret key before we
          # can check it here.
          Djinn.log_debug("run_terminate(): didn't find secret file. Continuing.")
        end
        # Client will process "Error" and try again unless appscale is
        # terminated
        if @done_terminating and @waiting_messages.empty?
          return "Error: Done Terminating and No Messages"
        end
        @waiting_messages.synchronize {
          @message_ready.wait_while {@waiting_messages.empty?}
          message = JSON.dump(@waiting_messages)
          @waiting_messages.clear
          was_queue_emptied = true
          return message
        }
      }
    # Client will process "Error" and try again unless appscale is terminated
    rescue Timeout::Error
      Djinn.log_debug("Timed out trying to receive server message. Queue empty:
                     #{was_queue_emptied}")
      return "Error: Server Timed Out"
    end
  end

  # Starts the InfrastructureManager service on this machine, which exposes
  # a SOAP interface by which we can dynamically add and remove nodes in this
  # AppScale deployment.
  def start_infrastructure_manager()
    iaas_script = "#{APPSCALE_HOME}/InfrastructureManager/infrastructure_manager_service.py"
    start_cmd = "#{PYTHON27} #{iaas_script}"
    stop_cmd = "#{PYTHON27} #{APPSCALE_HOME}/scripts/stop_service.py " +
          "#{iaas_script} #{PYTHON27}"
    port = InfrastructureManagerClient::SERVER_PORT
    env = {
      'APPSCALE_HOME' => APPSCALE_HOME,
      'EC2_HOME' => ENV['EC2_HOME'],
      'JAVA_HOME' => ENV['JAVA_HOME']
    }

    MonitInterface.start(:iaas_manager, start_cmd, stop_cmd, [port], env,
                         start_cmd, nil, nil, nil)
    Djinn.log_info("Started InfrastructureManager successfully!")
  end


  def stop_infrastructure_manager
    Djinn.log_info("Stopping InfrastructureManager")
    MonitInterface.stop(:iaas_manager)
  end


  def get_online_users_list(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    online_users = []

    lb_node = get_load_balancer
    ip = lb_node.public_ip
    key = lb_node.ssh_key
    raw_list = `ssh -i #{key} -o StrictHostkeyChecking=no root@#{ip} 'ejabberdctl connected-users'`
    raw_list.split("\n").each { |userdata|
      online_users << userdata.split("/")[0]
    }

    return online_users
  end


  # This function adds this node to the list of possible sources for the
  # application 'appname' tarball source. Others nodes will be able to get
  # the tarball from this node.
  #
  # Args:
  #   appname: The application ID.
  #   location: Full path for the tarball of the application.
  #   secret: The deployment current secret.
  # Returns:
  #   A Boolean indicating the success of the operation.
  def done_uploading(appname, location, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    unless File.exists?(location)
      Djinn.log_warn("The #{appname} app was not found at #{location}.")
      return false
    end

    RETRIES.downto(0) {
      begin
        ZKInterface.add_app_entry(appname, my_node.private_ip, location)
        Djinn.log_info("This node is now hosting #{appname} source (#{location}).")
        return true
      rescue FailedZooKeeperOperationException => except
        Djinn.log_warn("(done_uploading) couldn't talk to zookeeper " +
          "with #{except.message}.")
      end
      Kernel.sleep(SMALL_WAIT)
    }
    Djinn.log_warn("Failed to notify zookeeper this node hosts #{appname}.")
    return false
  end


  # This function removes this node from the list of possible sources for
  # the application 'appname' tarball source.
  #
  # Args:
  #   appname: The application ID.
  #   location: Full path for the tarball of the application.
  #   secret: The deployment current secret.
  # Returns:
  #   A Boolean indicating the success of the operation.
  def not_hosting_app(appname, location, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    unless File.exists?(location)
      Djinn.log_warn("The #{appname} app was still found at #{location}.")
    end

    begin
      ZKInterface.remove_app_entry(appname, my_node.private_ip)
      return true
    rescue FailedZooKeeperOperationException => except
      # We just warn here and don't retry, since the shadow may have
      # already cleaned up the hosters.
      Djinn.log_warn("not_hosting_app: got exception talking to " +
        "zookeeper: #{except.message}.")
    end

    return false
  end


  def is_app_running(appname, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    hosters = ZKInterface.get_app_hosters(appname, @options['keyname'])
    hosters_w_appengine = []
    hosters.each { |node|
      hosters_w_appengine << node if node.is_appengine?
    }

    app_running = !hosters_w_appengine.empty?
    Djinn.log_debug("Is app #{appname} running? #{app_running}")
    return app_running
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
    return BAD_SECRET_MSG unless valid_secret?(secret)

    ips_hash = JSON.load(ips_hash)
    if ips_hash.class != Hash
      Djinn.log_warn("Was expecting ips_hash to be a Hash, not " +
        "a #{ips_hash.class}")
      return BAD_INPUT_MSG
    end

    Djinn.log_info("Received a request to start additional roles on " +
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
    Djinn.log_info("Starting new roles in cloud with following info: " +
      "#{ips_to_roles.inspect}")

    num_of_vms = ips_to_roles.keys.length
    roles = ips_to_roles.values
    disks = Array.new(num_of_vms, nil)  # no persistent disks
    Djinn.log_info("Need to spawn up #{num_of_vms} VMs")
    imc = InfrastructureManagerClient.new(@@secret)

    begin
      new_nodes_info = imc.spawn_vms(num_of_vms, @options, roles, disks)
    rescue FailedNodeException, AppScaleException => exception
      Djinn.log_error("Couldn't spawn #{num_of_vms} VMs with roles #{roles} " +
        "because: #{exception.message}")
      return []
    end

    # initialize them and wait for them to start up
    Djinn.log_debug("info about new nodes is " +
      "[#{new_nodes_info.join(', ')}]")

    add_nodes(new_nodes_info)
    update_hosts_info()

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
    Djinn.log_info("Starting new roles in virt with following info: " +
      "#{ips_to_roles.inspect}")

    nodes_info = []
    ips_to_roles.each { |ip, roles|
      Djinn.log_info("Will add roles #{roles.join(', ')} to new " +
        "node at IP address #{ip}")
      nodes_info << {
        "public_ip" => ip,
        "private_ip" => ip,
        "jobs" => roles,
        "disk" => nil
      }
    }

    add_nodes(nodes_info)
    update_hosts_info()

    return nodes_info
  end


  # Starts the given roles by using open nodes, spawning new nodes, or some
  # combination of the two.
  #
  # Args:
  #   nodes_needed:  An Array, where each item is an Array of the roles to
  #     start on each node.
  #   instance_type: A String with the type of instance to start.
  #   secret: A String with the deployment secret key.
  # Returns:
  #  A String with 'OK' or the Error string.
  def start_new_roles_on_nodes(nodes_needed, instance_type, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    # TODO: we should validate the roles type, to ensure they are valid.
    if nodes_needed.class != Array || instance_type.class != String
      Djinn.log_error("Invalid parameter type (nodes_needed, or instance_type).")
      return BAD_INPUT_MSG
    end

    Djinn.log_info("Received a request to acquire nodes with roles " +
      "#{nodes_needed.join(', ')}, with instance type #{instance_type}.")

    vms_to_use = []

    # We look for 'open' nodes first.
    @state_change_lock.synchronize {
      @nodes.each { |node|
        if node.is_open?
          Djinn.log_info("Will use node #{node} to run new roles")
          node.jobs = nodes_needed[vms_to_use.length]
          vms_to_use << node
        end
      }
    }
    Djinn.log_info("Using #{vms_to_use.length} open nodes to run new roles.")

    vms_to_spawn = nodes_needed.length - vms_to_use.length

    if vms_to_spawn > 0
      unless is_cloud?
        Djinn.log_error("Still need #{vms_to_spawn} more nodes, but we " +
        "aren't in a cloud environment, so we can't acquire more nodes - " +
        "failing the caller's request.")
        return NOT_ENOUGH_OPEN_NODES
      end

      Djinn.log_info("Need to spawn up #{vms_to_spawn} VMs.")
      # Make sure the user has said it is ok to add more VMs before doing so.
      allowed_vms = Integer(@options['max_images']) - @nodes.length
      if allowed_vms < vms_to_spawn
        Djinn.log_info("Can't spawn up #{vms_to_spawn} VMs, because that " +
          "would put us over the user-specified limit of #{@options['max_images']} " +
          "VMs. Instead, spawning up #{allowed_vms}.")
        vms_to_spawn = allowed_vms
        if vms_to_spawn <= 0
          Djinn.log_error("Reached the maximum number of VMs that we " +
            "can use in this cloud deployment, so not spawning more nodes.")
          return "Reached maximum number of VMs we can use."
        end
      end

      disks = Array.new(vms_to_spawn, nil)  # no persistent disks

      # Start up vms_to_spawn vms.
      imc = InfrastructureManagerClient.new(@@secret)
      begin
        new_nodes_info = imc.spawn_vms(vms_to_spawn, @options, nodes_needed, disks)
      rescue FailedNodeException, AppScaleException => exception
        Djinn.log_error("Couldn't spawn #{vms_to_spawn} VMs with roles " +
          "open because: #{exception.message}")
        return exception.message
      end

      # Initialize them and integrate them with our nodes.
      Djinn.log_debug("info about new nodes is " +
        "[#{new_nodes_info.join(', ')}]")
      add_nodes(new_nodes_info)
    end

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
    keyname = @options['keyname']
    new_nodes = Djinn.convert_location_array_to_class(node_info, keyname)

    # Since an external thread can modify @nodes, let's put a lock around
    # it to prevent race conditions.
    @state_change_lock.synchronize {
      @nodes.concat(new_nodes)
      @nodes.uniq!
    }
    Djinn.log_debug("Changed nodes to #{@nodes}")

    update_firewall()
    initialize_nodes_in_parallel(new_nodes)
  end


  # Cleans out temporary files that may have been written by a previous
  # AppScale deployment.
  def erase_old_data()
    Djinn.log_run("rm -f ~/.appscale_cookies")

    Nginx.clear_sites_enabled()
    HAProxy.clear_sites_enabled()
    Djinn.log_run("echo '' > /root/.ssh/known_hosts") # empty it out but leave the file there
    CronHelper.clear_app_crontabs()
  end


  def wait_for_nodes_to_finish_loading(nodes)
    Djinn.log_info("Waiting for nodes to finish loading")

    nodes.each { |node|
      if ZKInterface.is_node_done_loading?(node.private_ip)
        Djinn.log_info("Node at #{node.private_ip} has finished loading.")
        next
      else
        Djinn.log_info("Node at #{node.private_ip} has not yet finished " +
          "loading - will wait for it to finish.")
        Kernel.sleep(SMALL_WAIT)
        redo
      end
    }

    Djinn.log_info("Nodes have finished loading")
    return
  end


  # This method logs a message that is useful to know when debugging AppScale,
  # but is too extraneous to know when AppScale normally runs.
  #
  # Messages are logged both to STDOUT as well as to @@logs_buffer, which is
  # sent to the AppDashboard for viewing via a web UI.
  #
  # Args:
  #   message: A String containing the message to be logged.
  def self.log_debug(message)
    @@log.debug(message)
    self.log_to_buffer(Logger::DEBUG, message)
  end


  # This method logs a message that is useful to know when AppScale normally
  # runs.
  #
  # Args:
  #   message: A String containing the message to be logged.
  def self.log_info(message)
    @@log.info(message)
    self.log_to_buffer(Logger::INFO, message)
  end


  # This method logs a message that is useful to know when the AppController
  # experiences an unexpected event.
  #
  # Args:
  #   message: A String containing the message to be logged.
  def self.log_warn(message)
    @@log.warn(message)
    self.log_to_buffer(Logger::WARN, message)
  end


  # This method logs a message that corresponds to an erroneous, but
  # recoverable, event.
  #
  # Args:
  #   message: A String containing the message to be logged.
  def self.log_error(message)
    @@log.error(message)
    self.log_to_buffer(Logger::ERROR, message)
  end


  # This method logs a message that immediately precedes the death of this
  # AppController.
  #
  # Args:
  #   message: A String containing the message to be logged.
  def self.log_fatal(message)
    @@log.fatal(message)
    self.log_to_buffer(Logger::FATAL, message)
  end

  # Use syslogd to log a message to the combined application log.
  #
  # Args:
  #   app_id: A String containing the app ID.
  #   message: A String containing the message to log.
  def self.log_app_error(app_id, message)
    Syslog.open("app___#{app_id}", Syslog::LOG_PID, Syslog::LOG_USER) { |s|
      s.err message
    }
  end

  # Appends this log message to a buffer, which will be periodically sent to
  # the AppDashbord.
  #
  # Only sends the message if it has content (as some empty messages are the
  # result of exec'ing commands that produce no output), and if its log level
  # is at least as great as the log level that we want to capture logs for.
  #
  # Args:
  #   level: An Integer in the set of Logger levels (e.g., Logger::DEBUG,
  #     Logger::INFO) that indicates the severity of this log message.
  #   message: A String containing the message to be logged.
  def self.log_to_buffer(level, message)
    return if message.empty?
    return if level < @@log.level
    time = Time.now
    @@logs_buffer << {
      'timestamp' => time.to_i,
      'level' => level + 1,  # Python and Java are one higher than Ruby
      'message' => message
    }
    return
  end


  # Logs and runs the given command, which is assumed to be trusted and thus
  # needs no filtering on our part. Obviously this should not be executed by
  # anything that the user could inject input into. Returns the output of
  # the command that was executed.
  def self.log_run(command)
    Djinn.log_debug("Running #{command}")
    output = `#{command}`
    if $?.exitstatus != 0
      Djinn.log_debug("Command #{command} failed with #{$?.exitstatus}" +
          " and output: #{output}.")
    end
    return output
  end


  # This method converts an Array of Strings (where each String contains all the
  # information about a single node) to an Array of DjinnJobData objects, which
  # provide convenience methods that make them easier to operate on than just
  # raw String objects.
  def self.convert_location_array_to_class(nodes, keyname)
    array_of_nodes = []
    nodes.each { |node|
      converted = DjinnJobData.new(node, keyname)
      array_of_nodes << converted
    }

    return array_of_nodes
  end


  # This method is the opposite of the previous method, and is needed when an
  # AppController wishes to pass node information to other AppControllers via
  # SOAP (as SOAP accepts Arrays and Strings but not DjinnJobData objects).
  def self.convert_location_class_to_json(layout)
    if layout.class != Array
      @state = "Locations is not an Array, but a #{layout.class}."
      HelperFunctions.log_and_crash(@state, WAIT_TO_CRASH)
    end

    layout_array = []
    layout.each { |location|
      layout_array << location.to_hash
    }
    return JSON.dump(layout_array)
  end

  def get_shadow()
    @nodes.each { |node|
      return node if node.is_shadow?
    }

    @state = "No shadow nodes found."
    HelperFunctions.log_and_crash(@state, WAIT_TO_CRASH)
  end

  def get_db_master()
    @nodes.each { |node|
      return node if node.is_db_master?
    }

    @state = "No DB master nodes found."
    HelperFunctions.log_and_crash(@state, WAIT_TO_CRASH)
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

  def get_load_balancer()
    @nodes.each { |node|
      return node if node.is_load_balancer?
    }

    @state = "No load balancer nodes found."
    HelperFunctions.log_and_crash(@state, WAIT_TO_CRASH)
  end

  def valid_secret?(secret)
    @@secret = HelperFunctions.get_secret
    if secret != @@secret
      failed_match_msg = "Incoming secret [#{secret}] failed to match " + \
        " known secret [#{@@secret}]"
      Djinn.log_error(failed_match_msg)
    end
    return secret == @@secret
  end

  # Collects all AppScale-generated logs from all machines, and places them in
  # a tarball in the AppDashboard running on this machine. This enables users
  # to download it for debugging purposes.
  #
  # Args:
  #   secret: A String password that is used to authenticate SOAP callers.
  def gather_logs(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    uuid = HelperFunctions.get_random_alphanumeric()
    Djinn.log_info("Generated uuid #{uuid} for request to gather logs.")

    Thread.new {
      # Begin by copying logs on all machines to this machine.
      local_log_dir = "#{Dir.tmpdir}/#{uuid}"
      remote_log_dir = "/var/log/appscale"
      FileUtils.mkdir_p(local_log_dir)
      @nodes.each { |node|
        this_nodes_logs = "#{local_log_dir}/#{node.private_ip}"
        FileUtils.mkdir_p(this_nodes_logs)
        Djinn.log_run("scp -r -i #{node.ssh_key} -o StrictHostkeyChecking=no " +
          "2>&1 root@#{node.private_ip}:#{remote_log_dir} #{this_nodes_logs}")
      }

      # Next, tar.gz it up in the dashboard app so that users can download it.
      dashboard_log_location = "#{HelperFunctions.get_app_path(AppDashboard::APP_NAME)}/app/static/download-logs/#{uuid}.tar.gz"
      Djinn.log_info("Done gathering logs - placing logs at " +
        dashboard_log_location)
      Djinn.log_run("tar -czf #{dashboard_log_location} #{local_log_dir}")
      FileUtils.rm_rf(local_log_dir)
    }

    return uuid
  end


  # Instructs Nginx and HAProxy to begin routing traffic for the named
  # application to a new AppServer.
  #
  # This method should be called at the AppController running the login role,
  # as it is the node that receives application traffic from the outside.
  #
  # Args:
  #   app_id: A String that identifies the application that runs the new
  #     AppServer.
  #   ip: A String that identifies the private IP address where the new
  #     AppServer runs.
  #   port: A Fixnum that identifies the port where the new AppServer runs at
  #     ip.
  #   secret: A String that is used to authenticate the caller.
  #
  # Returns:
  #   "OK" if the addition was successful. In case of failures, the following
  #   Strings may be returned:
  #   - BAD_SECRET_MSG: If the caller cannot be authenticated.
  #   - NO_HAPROXY_PRESENT: If this node does not run HAProxy (and thus cannot
  #     add AppServers to HAProxy config files).
  #   - NOT_READY: If this node runs HAProxy, but hasn't allocated ports for
  #     it and nginx yet. Callers should retry at a later time.
  def add_routing_for_appserver(app_id, ip, port, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    unless my_node.is_shadow?
       # We need to send the call to the shadow.
       Djinn.log_debug("Sending routing call for #{app_id} to shadow.")
       acc = AppControllerClient.new(get_shadow.private_ip, @@secret)
       begin
         return acc.add_routing_for_appserver(app_id, ip, port)
       rescue FailedNodeException => except
         Djinn.log_warn("Failed to forward routing call to shadow (#{get_shadow}).")
         return NOT_READY
       end
    end

    APPS_LOCK.synchronize {
      if @app_info_map[app_id].nil? or @app_info_map[app_id]['appengine'].nil?
        return NOT_READY
      elsif @app_info_map[app_id]['appengine'].include?("#{ip}:#{port}")
        Djinn.log_warn("Already registered AppServer for app #{app_id} at #{ip}:#{port}.")
        return INVALID_REQUEST
      end

      Djinn.log_debug("Add routing for app #{app_id} at #{ip}:#{port}.")

      # Find and remove an entry for this AppServer node and app.
      match = @app_info_map[app_id]['appengine'].index("#{ip}:-1")
      if match
        @app_info_map[app_id]['appengine'].delete_at(match)
      else
        Djinn.log_warn("Received a no matching request for: #{ip}:#{port}.")
      end
      @app_info_map[app_id]['appengine'] << "#{ip}:#{port}"


      # Now that we have at least one AppServer running, we can start the
      # cron job of the application.
      CronHelper.update_cron(get_load_balancer.public_ip,
        @app_info_map[app_id]['nginx'], @app_info_map[app_id]['language'], app_id)
    }

    return "OK"
  end

  # Instruct HAProxy to begin routing traffic to the BlobServers.
  #
  # Args:
  #   secret: A String that is used to authenticate the caller.
  #
  # Returns:
  #   "OK" if the addition was successful. In case of failures, the following
  #   Strings may be returned:
  #   - BAD_SECRET_MSG: If the caller cannot be authenticated.
  #   - NO_HAPROXY_PRESENT: If this node does not run HAProxy.
  def add_routing_for_blob_server(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NO_HAPROXY_PRESENT unless my_node.is_load_balancer?

    Djinn.log_debug('Adding BlobServer routing.')
    servers = []
    get_all_appengine_nodes.each { |ip|
      servers << {'ip' => ip, 'port' => BlobServer::SERVER_PORT}
    }
    HAProxy.create_app_config(servers, my_node.private_ip,
      BlobServer::HAPROXY_PORT, BlobServer::NAME)
  end


  # Creates an Nginx/HAProxy configuration file for the Users/Apps soap server.
  def configure_uaserver()
    all_db_private_ips = []
    @nodes.each { | node |
      if node.is_db_master? or node.is_db_slave?
        all_db_private_ips.push(node.private_ip)
      end
    }
    HAProxy.create_ua_server_config(all_db_private_ips,
      my_node.private_ip, UserAppClient::HAPROXY_SERVER_PORT)
    Nginx.create_uaserver_config(my_node.private_ip)
  end

  def configure_db_nginx()
    all_db_private_ips = []
    @nodes.each { | node |
      if node.is_db_master? or node.is_db_slave?
        all_db_private_ips.push(node.private_ip)
      end
    }
    Nginx.create_datastore_server_config(all_db_private_ips, DatastoreServer::PROXY_PORT)
  end

  # Creates HAProxy configuration for the TaskQueue REST API.
  def configure_tq_routing()
    all_tq_ips = []
    @nodes.each { | node |
      if node.is_taskqueue_master? || node.is_taskqueue_slave?
        all_tq_ips.push(node.private_ip)
      end
    }
    HAProxy.create_tq_endpoint_config(all_tq_ips, my_node.private_ip,
                                      TaskQueue::HAPROXY_REST_PORT)

    # We don't need Nginx for backend TaskQueue servers, only for REST support.
    Nginx.create_taskqueue_rest_config(my_node.private_ip)
  end

  def remove_tq_endpoints
    HAProxy.remove_tq_endpoints
  end

  def write_database_info()
    table = @options['table']
    replication = @options['replication']
    keyname = @options['keyname']

    tree = { :table => table, :replication => replication, :keyname => keyname }
    db_info_path = "#{APPSCALE_CONFIG_DIR}/database_info.yaml"
    File.open(db_info_path, "w") { |file| YAML.dump(tree, file) }
  end


  def update_firewall()
    Djinn.log_debug("Resetting firewall.")

    # We force the write of locations, to ensure we have an up-to-date
    # list of nodes in the firewall.
    write_locations
    if FIREWALL_IS_ON
      Djinn.log_run("bash #{APPSCALE_HOME}/firewall.conf")
    end
  end


  def backup_appcontroller_state()
    local_state = {}
    APPS_LOCK.synchronize {
      local_state = {'@@secret' => @@secret }
      DEPLOYMENT_STATE.each { |var|
        if var == "@nodes"
          v = Djinn.convert_location_class_to_json(@nodes)
        else
          v = instance_variable_get(var)
        end
        local_state[var] = v
      }
    }
    if @appcontroller_state == local_state.to_s
      Djinn.log_debug("backup_appcontroller_state: no changes.")
      return
    end

    Djinn.log_debug("backup_appcontroller_state:"+local_state.to_s)

    begin
      ZKInterface.write_appcontroller_state(local_state)
    rescue FailedZooKeeperOperationException => e
      Djinn.log_warn("Couldn't talk to zookeeper whle backing up " +
        "appcontroller state with #{e.message}.")
    end
    @appcontroller_state = local_state.to_s
  end


  # Takes actions if options or roles changed.
  #
  # Args:
  #   old_options: this is a clone of @options. We will compare it with
  #     the current value.
  #   old_jobs: this is a list of roles. It will be compared against the
  #     current list of jobs for this node.
  def check_role_change(old_options, old_jobs)
    if old_jobs != my_node.jobs
      Djinn.log_info("Roles for this node are now: #{my_node.jobs}.")
      start_stop_api_services
    end

    # Finally some @options may have changed.
    enforce_options unless old_options == @options
  end


  # Restores the state of each of the instance variables that the AppController
  # holds by pulling it from ZooKeeper (previously populated by the Shadow
  # node, who always has the most up-to-date version of this data).
  #
  # Returns:
  #   A boolean indicating if the state is restored or current with the master.
  def restore_appcontroller_state
    json_state=""

    unless File.exists?(ZK_LOCATIONS_FILE)
      Djinn.log_info("#{ZK_LOCATIONS_FILE} doesn't exist: not restoring data.")
      return false
    end

    loop {
      begin
        json_state = ZKInterface.get_appcontroller_state()
      rescue => e
        Djinn.log_debug("Saw exception #{e.message} reading appcontroller state.")
        json_state = ""
        Kernel.sleep(SMALL_WAIT)
      end
      break unless json_state.empty?
      Djinn.log_warn("Unable to get state from zookeeper: trying again.")
      pick_zookeeper(@zookeeper_data)
    }
    if @appcontroller_state == json_state
      Djinn.log_debug("Reload state: no changes.")
      return true
    end

    Djinn.log_debug("Reload state : #{json_state}.")
    APPS_LOCK.synchronize {
      @@secret = json_state['@@secret']
      keyname = json_state['@options']['keyname']

      # Puts json_state.
      json_state.each { |k, v|
        next if k == "@@secret"
        v = Djinn.convert_location_array_to_class(JSON.load(v), keyname) if k == "@nodes"
        instance_variable_set(k, v) if DEPLOYMENT_STATE.include?(k)
      }

      # Check to see if our IP address has changed. If so, we need to update all
      # of our internal state to use the new public and private IP anywhere the
      # old ones were present.
      unless HelperFunctions.get_all_local_ips().include?(@my_private_ip)
        Djinn.log_info("IP changed old private:#{@my_private_ip} public:#{@my_public_ip}.")
        update_state_with_new_local_ip()
        Djinn.log_info("IP changed new private:#{@my_private_ip} public:#{@my_public_ip}.")
      end
      Djinn.log_debug("app_info_map after restore is #{@app_info_map}.")
    }

    # Now that we've restored our state, update the pointer that indicates
    # which node in @nodes is ours
    find_me_in_locations

    return true
  end


  # Updates all instance variables stored within the AppController with the new
  # public and private IP addreses of this machine.
  #
  # The issue here is that an AppController may back up state when running, but
  # when it is restored, its IP address changes (e.g., when taking AppScale down
  # then starting it up on new machines in a cloud deploy). This method searches
  # through internal AppController state to update any place where the old
  # public and private IP addresses were used, replacing them with the new one.
  def update_state_with_new_local_ip()
    # First, find out this machine's private IP address. If multiple eth devices
    # are present, use the same one we used last time.
    all_local_ips = HelperFunctions.get_all_local_ips()
    if all_local_ips.length < 1
      Djinn.log_and_crash("Couldn't detect any IP address on this machine!")
    end
    new_private_ip = all_local_ips[0]

    # Next, find out this machine's public IP address. In a cloud deployment, we
    # have to rely on the metadata server, while in a cluster deployment, it's
    # the same as the private IP.
    if ["ec2", "euca", "gce"].include?(@options['infrastructure'])
      new_public_ip = HelperFunctions.get_public_ip_from_metadata_service()
    else
      new_public_ip = new_private_ip
    end

    # Finally, replace anywhere that the old public or private IP addresses were
    # used with the new one.
    old_public_ip = @my_public_ip
    old_private_ip = @my_private_ip

    @nodes.each { |node|
      if node.public_ip == old_public_ip
        node.public_ip = new_public_ip
      end

      if node.private_ip == old_private_ip
        node.private_ip = new_private_ip
      end
    }

    if @options['login'] == old_public_ip
      @options['login'] = new_public_ip
    end

    @app_info_map.each { |_app_id, app_info|
      next if app_info['appengine'].nil?

      changed = false
      new_app_info = []
      app_info['appengine'].each { |location|
        host, port = location.split(":")
        if host == old_private_ip
          host = new_private_ip
          changed = true
        end
        new_app_info << "#{host}:#{port}"

        app_info['appengine'] = new_app_info if changed
      }
    }

    @all_stats = []

    @my_public_ip = new_public_ip
    @my_private_ip = new_private_ip
  end


  # Writes any custom configuration data in /etc/appscale to ZooKeeper.
  def set_custom_config()
    cassandra_config = {'num_tokens' => 256}
    begin
      contents = File.read("#{APPSCALE_CONFIG_DIR}/cassandra")
      cassandra_config = JSON.parse(contents)
    rescue Errno::ENOENT
      Djinn.log_debug('No custom cassandra configuration found.')
    rescue JSON::ParserError
      Djinn.log_error('Invalid JSON in custom cassandra configuration.')
    end
    ZKInterface.ensure_path('/appscale/config')
    ZKInterface.set('/appscale/config/cassandra', JSON.dump(cassandra_config),
                    false)
    Djinn.log_info('Set custom cassandra configuration.')
  end

  # Updates the file that says where all the ZooKeeper nodes are
  # located so that this node has the most up-to-date info if it needs to
  # restore the data down the line.
  def write_zookeeper_locations()
    zookeeper_data = { 'last_updated_at' => @last_updated,
      'locations' => []
    }

    @nodes.each { |node|
      if node.is_zookeeper?
        unless zookeeper_data['locations'].include? node.private_ip
          zookeeper_data['locations'] << node.private_ip
        end
      end
    }

    # Let's see if it changed since last time we got the list.
    zookeeper_data['locations'].sort!
    if zookeeper_data['locations'] != @zookeeper_data
      # Save the latest list of zookeeper nodes: needed to restart the
      # deployment.
      HelperFunctions.write_json_file(ZK_LOCATIONS_FILE, zookeeper_data)
      @zookeeper_data = zookeeper_data['locations']
      Djinn.log_debug("write_zookeeper_locations: updated list of zookeeper servers")
    end
  end

  # This function makes sure we have a zookeeper connection active to one
  # of the ZK servers.
  def pick_zookeeper(zk_list)
    if zk_list.length < 1
      HelperFunctions.log_and_crash("Don't have valid zookeeper servers.")
    end
    loop {
      break if ZKInterface.is_connected?

      @state = NO_ZOOKEEPER_CONNECTION

      ip = zk_list.sample()
      Djinn.log_info("Trying to use zookeeper server at #{ip}.")
      ZKInterface.init_to_ip(HelperFunctions.local_ip, ip.to_s)
    }
    Djinn.log_debug("Found zookeeper server.")
  end

  # Backs up information about what this node is doing (roles, apps it is
  # running) to ZooKeeper, for later recovery or updates by other nodes.
  def write_our_node_info()
    # Since more than one AppController could write its data at the same
    # time, get a lock before we write to it.
    begin
      ZKInterface.lock_and_run {
        @last_updated = ZKInterface.add_ip_to_ip_list(my_node.private_ip)
        ZKInterface.write_node_information(my_node, @done_loading)
      }
    rescue => e
      Djinn.log_info("(write_our_node_info) saw exception #{e.message}")
    end

    return
  end


  # Returns the buffer that contains all logs yet to be sent to the Admin
  # Console for viewing.
  #
  # Returns:
  #   An Array of Hashes, where each Hash has information about a single log
  #     line.
  def self.get_logs_buffer()
    return @@logs_buffer
  end


  # Sends all of the logs that have been buffered up to the Admin Console for
  # viewing in a web UI.
  def flush_log_buffer()
    APPS_LOCK.synchronize {
      loop {
        break if @@logs_buffer.empty?
        encoded_logs = JSON.dump({
          'service_name' => 'appcontroller',
          'host' => my_node.public_ip,
          'logs' => @@logs_buffer.shift(LOGS_PER_BATCH),
        })

        # We send logs to dashboard only if controller_logs_to_dashboard
        # is set to True. This will incur in higher traffic to the
        # database, depending on the verbosity and the deployment.
        if @options['controller_logs_to_dashboard'].downcase == "true"
          begin
            url = URI.parse("https://#{get_load_balancer.public_ip}:" +
              "#{AppDashboard::LISTEN_SSL_PORT}/logs/upload")
            http = Net::HTTP.new(url.host, url.port)
            http.verify_mode = OpenSSL::SSL::VERIFY_NONE
            http.use_ssl = true
            response = http.post(url.path, encoded_logs,
              {'Content-Type'=>'application/json'})
            Djinn.log_debug("Done flushing logs to AppDashboard. " +
              "Response is: #{response.body}.")
          rescue
            # Don't crash the AppController because we weren't able to send over
            # the logs - just continue on.
            Djinn.log_debug("Ignoring exception talking to dashboard.")
          end
        end
      }
    }
  end


  # Sends information about the AppServer processes hosting App Engine apps on
  # this machine to the AppDashboard, for later viewing.
  def send_instance_info_to_dashboard()
    APPS_LOCK.synchronize {
      instance_info = []
      @app_info_map.each_pair { |appid, app_info|
        next if app_info['appengine'].nil?
        app_info['appengine'].each { |location|
          host, port = location.split(":")
          next if Integer(port) < 0
          instance_info << {
            'appid' => appid,
            'host' => host,
            'port' => Integer(port),
            'language' => app_info['language']
          }
        }
      }

      begin
        url = URI.parse("https://#{get_load_balancer.public_ip}:" +
          "#{AppDashboard::LISTEN_SSL_PORT}/apps/stats/instances")
        http = Net::HTTP.new(url.host, url.port)
        http.use_ssl = true
        http.verify_mode = OpenSSL::SSL::VERIFY_NONE
        response = http.post(url.path, JSON.dump(instance_info),
          {'Content-Type'=>'application/json'})
        Djinn.log_debug("Done sending instance info to AppDashboard. Info is: " +
          "#{instance_info.inspect}. Response is: #{response.body}.")
      rescue OpenSSL::SSL::SSLError, NotImplementedError, Errno::EPIPE,
        Errno::ECONNRESET => e
        backtrace = e.backtrace.join("\n")
        Djinn.log_warn("Error in send_instance_info: #{e.message}\n#{backtrace}")
        retry
      rescue => exception
        # Don't crash the AppController because we weren't able to send over
        # the instance info - just continue on.
        Djinn.log_warn("Couldn't send instance info to the AppDashboard " +
          "because of a #{exception.class} exception.")
      end
    }
  end


  # Informs the AppDashboard that the named AppServer is no longer running, so
  # that it no longer displays that AppServer in its instance information.
  #
  # Args:
  #   appid: A String that names the application whose AppServer was removed.
  #   location: A String that identifies the host and port that the AppServer
  #     was removed off of.
  def delete_instance_from_dashboard(appid, location)
    begin
      host, port = location.split(":")
      instance_info = [{
        'appid' => appid,
        'host' => host,
        'port' => Integer(port)
      }]

      url = URI.parse("https://#{get_load_balancer.public_ip}:" +
        "#{AppDashboard::LISTEN_SSL_PORT}/apps/stats/instances")
      http = Net::HTTP.new(url.host, url.port)
      http.use_ssl = true
      http.verify_mode = OpenSSL::SSL::VERIFY_NONE
      request = Net::HTTP::Delete.new(url.path)
      request.body = JSON.dump(instance_info)
      response = http.request(request)
      Djinn.log_debug("Sent delete_instance to AppDashboard. Info is: " +
        "#{instance_info.inspect}. Response is: #{response.body}.")
    rescue => exception
      # Don't crash the AppController because we weren't able to send over
      # the instance info - just continue on.
      Djinn.log_warn("Couldn't delete instance info to AppDashboard because" +
        " of a #{exception.class} exception.")
    end
  end


  # Removes information associated with the given IP address from our local
  # cache (@nodes) as well as the remote node storage mechanism (in ZooKeeper).
  def remove_node_from_local_and_zookeeper(ip)
    # First, remove our local copy
    index_to_remove = nil
    @nodes.each_index { |i|
      if @nodes[i].private_ip == ip
        index_to_remove = i
        break
      end
    }
    @state_change_lock.synchronize {
      @nodes.delete(@nodes[index_to_remove])
    }

    # Then remove the remote copy
    begin
      ZKInterface.remove_node_information(ip)
      @last_updated = ZKInterface.remove_ip_from_ip_list(ip)
    rescue FailedZooKeeperOperationException => e
      Djinn.log_warn("(remove_node_from_local_and_zookeeper) issues " +
        "talking to zookeeper with #{e.message}.")
    end
  end


  def wait_for_data()
    loop {
      break if got_all_data()
      if @kill_sig_received
        Djinn.log_fatal("Received kill signal, aborting startup")
        HelperFunctions.log_and_crash("Received kill signal, aborting startup")
      else
        Djinn.log_info("Waiting for data from the load balancer or cmdline tools")
        Kernel.sleep(SMALL_WAIT)
      end
    }

  end

  def parse_options
    keypath = @options['keyname'] + ".key"
    Djinn.log_debug("Keypath is #{keypath}, keyname is #{@options['keyname']}")
    my_key_dir = "#{APPSCALE_CONFIG_DIR}/keys/#{my_node.cloud}"
    my_key_loc = "#{my_key_dir}/#{keypath}"
    Djinn.log_debug("Creating directory #{my_key_dir} for my ssh key #{my_key_loc}")
    FileUtils.mkdir_p(my_key_dir)
    Djinn.log_run("chmod 600 #{APPSCALE_CONFIG_DIR}/ssh.key")
    Djinn.log_run("cp -p #{APPSCALE_CONFIG_DIR}/ssh.key #{my_key_loc}")

    # AWS and Euca need some evironmental variables.
    if ["ec2", "euca"].include?(@options['infrastructure'])
      ENV['EC2_ACCESS_KEY'] = @options['ec2_access_key']
      ENV['EC2_SECRET_KEY'] = @options['ec2_secret_key']
      ENV['EC2_URL'] = @options['ec2_url']
    end
  end

  def got_all_data()
    Djinn.log_debug("[got_all_data]: checking nodes.")
    return false if @nodes == []
    Djinn.log_debug("[got_all_data]: checking options.")
    return false if @options == {}
    Djinn.log_debug("[got_all_data]: done.")
    return true
  end


  # Searches through @nodes to try to find out which node is ours. Strictly
  # speaking, we assume that our node is identifiable by private IP, but
  # we also check our public IPs (for AWS and GCE) in case the user got it
  # wrong.
  def find_me_in_locations()
    @my_index = nil
    all_local_ips = HelperFunctions.get_all_local_ips()
    Djinn.log_debug("Searching for a node with any of these private IPs: " +
      "#{all_local_ips.join(', ')}")
    Djinn.log_debug("All nodes are: #{@nodes.join(', ')}")

    @nodes.each_with_index { |node, index|
      all_local_ips.each { |ip|
        if ip == node.private_ip
          @my_index = index
          HelperFunctions.set_local_ip(node.private_ip)
          @my_public_ip = node.public_ip
          @my_private_ip = node.private_ip
          return
        end
      }
    }

    # We haven't found our ip in the nodes layout: let's try to give
    # better debugging info to the user.
    public_ip = HelperFunctions.get_public_ip_from_metadata_service()
    @nodes.each { |node|
      if node.private_ip == public_ip
        HelperFunctions.log_and_crash("Found my public ip (#{public_ip}) " +
            "but not my private ip in @nodes. Please correct it. @nodes=#{@nodes}")
      end
      if node.public_ip == public_ip
        HelperFunctions.log_and_crash("Found my public ip (#{public_ip}) " +
            "in @nodes but my private ip is not matching! @nodes=#{@nodes}.")
      end
    }

    HelperFunctions.log_and_crash("Can't find my node in @nodes: #{@nodes}. " +
      "My local IPs are: #{all_local_ips.join(', ')}")
  end


  # Starts all of the services that this node has been assigned to run.
  # Also starts all services that all nodes run in an AppScale deployment.
  def start_stop_api_services
    @state = "Starting API Services."
    Djinn.log_info("#{@state}")

    threads = []
    threads << Thread.new {
      if my_node.is_zookeeper?
        unless is_zookeeper_running?
          configure_zookeeper(@nodes, @my_index)
          begin
            start_zookeeper(false)
          rescue FailedZooKeeperOperationException
            @state = "Couldn't start Zookeeper."
            HelperFunctions.log_and_crash(@state, WAIT_TO_CRASH)
          end
          Djinn.log_info("Done configuring zookeeper.")
        end
      else
        # Zookeeper shouldn't be running here.
        stop_zookeeper
      end
    }

    if my_node.is_shadow?
      pick_zookeeper(@zookeeper_data)
      set_custom_config
      start_log_server
    else
      stop_log_server
    end

    if my_node.is_db_master? or my_node.is_db_slave?
      db_master = nil
      @nodes.each { |node|
        db_master = node.private_ip if node.jobs.include?('db_master')
      }
      setup_db_config_files(db_master)

      threads << Thread.new {
        Djinn.log_info("Starting database services.")
        db_nodes = @nodes.count{|node| node.is_db_master? or node.is_db_slave?}
        needed_nodes = needed_for_quorum(db_nodes,
                                         Integer(@options['replication']))
        if my_node.is_db_master?
          start_db_master(false, needed_nodes, db_nodes)
          prime_database
        else
          start_db_slave(false, needed_nodes, db_nodes)
        end
      }
    else
      stop_db_master
      stop_db_slave
    end

    # We now wait for the essential services to go up.
    Djinn.log_info("Waiting for DB services ... ")
    threads.each { |t| t.join() }

    Djinn.log_info('Ensuring necessary database tables are present')
    sleep(SMALL_WAIT) until system("#{PRIME_SCRIPT} --check > /dev/null 2>&1")

    Djinn.log_info('Ensuring data layout version is correct')
    layout_script = `which appscale-data-layout`.chomp
    unless system("#{layout_script} --db-type cassandra > /dev/null 2>&1")
      HelperFunctions.log_and_crash(
        'Unexpected data layout version. Please run "appscale upgrade".')
    end

    if my_node.is_db_master? or my_node.is_db_slave?
      # Always colocate the Datastore Server and UserAppServer (soap_server).
      @state = "Starting up SOAP Server and Datastore Server"
      start_datastore_server()

      # Start the UserAppServer and wait till it's ready.
      start_soap_server()
      Djinn.log_info("Done starting database services.")
    else
      stop_soap_server
      stop_datastore_server
    end

    # All nodes wait for the UserAppServer now. The call here is just to
    # ensure the UserAppServer is talking to the persistent state.
    HelperFunctions.sleep_until_port_is_open(@my_private_ip,
      UserAppClient::SSL_SERVER_PORT, USE_SSL)
    uac = UserAppClient.new(@my_private_ip, @@secret)
    begin
      uac.does_app_exist?("not-there")
    rescue FailedNodeException
      Djinn.log_debug("UserAppServer not ready yet: retrying.")
      retry
    end
    @done_initializing = true
    Djinn.log_info("UserAppServer is ready.")

    # The services below depends directly or indirectly on the UAServer to
    # be operational. So we start them after we test the UAServer.
    threads = []
    if my_node.is_db_master? or my_node.is_db_slave? or my_node.is_zookeeper?
      threads << Thread.new {
        if my_node.is_db_master? or my_node.is_db_slave?
          start_groomer_service
        end

        start_backup_service
      }
    else
      stop_groomer_service
      stop_backup_service
    end

    if my_node.is_memcache?
      threads << Thread.new {
        start_memcache
      }
    else
      stop_memcache
    end

    if my_node.is_load_balancer?
      threads << Thread.new {
        start_ejabberd()
        configure_tq_routing
      }
    else
      remove_tq_endpoints
      stop_ejabberd
    end

    # The headnode needs to ensure we have the appscale user, and it needs
    # to prepare the dashboard to be started.
    if my_node.is_shadow?
      threads << Thread.new {
        create_appscale_user()
        prep_app_dashboard()
      }
    end

    if !my_node.is_open?
      threads << Thread.new {
        start_app_manager_server
      }
    else
      stop_app_manager_server
    end

    if my_node.is_appengine?
      threads << Thread.new {
        start_blobstore_server
      }
    else
      stop_blobstore_server
    end

    if my_node.is_search?
      threads << Thread.new {
        start_search_role
      }
    else
      stop_search_role
    end

    if my_node.is_taskqueue_master?
      threads << Thread.new {
        start_taskqueue_master()
      }
    elsif my_node.is_taskqueue_slave?
      threads << Thread.new {
        start_taskqueue_slave()
      }
    else
      stop_taskqueue
    end

    # App Engine apps rely on the above services to be started, so
    # join all our threads here
    Djinn.log_info("Waiting for all services to finish starting up")
    threads.each { |t| t.join() }
    Djinn.log_info("API services have started on this node")

    # Leader node starts additional services.
    if my_node.is_shadow?
      update_node_info_cache()
      start_hermes()
      TaskQueue.start_flower(@options['flower_password'])
    else
      TaskQueue.stop_flower
      stop_hermes
    end
  end


  # Creates database tables in the underlying datastore to hold information
  # about the users that interact with AppScale clouds, and about the
  # applications that AppScale hosts (including data that the apps themselves
  # read and write).
  #
  # Raises:
  #   SystemExit: If the database could not be primed for use with AppScale,
  #     after ten retries.
  def prime_database()
    table = @options['table']
    prime_script = `which appscale-prime-#{table}`.chomp
    replication = Integer(@options['replication'])
    retries = 10
    Djinn.log_info('Ensuring necessary tables have been created')
    loop {
      prime_cmd = "#{prime_script} --replication #{replication} >> " +
        '/var/log/appscale/prime_db.log 2>&1'
      return if system(prime_cmd)
      retries -= 1
      Djinn.log_warn("Failed to prime database. #{retries} retries left.")

      # If this has failed 10 times in a row, it's probably a
      # "Column ID mismatch" error that seems to be caused by creating tables
      # as the cluster is settling. Running a repair may fix the issue.
      if retries == 1
        @state = 'Running a Cassandra repair.'
        Djinn.log_warn(@state)
        system("#{NODETOOL} repair")
      end

      break if retries.zero?
      Kernel.sleep(SMALL_WAIT)
    }

    @state = "Failed to prime #{table}."
    HelperFunctions.log_and_crash(@state, WAIT_TO_CRASH)
  end


  # Delete all apps running on this instance.
  def erase_app_instance_info()
    uac = UserAppClient.new(my_node.private_ip, @@secret)
    begin
      result = uac.delete_all_apps()
      Djinn.log_info("UserAppServer delete_all_apps returned: #{result}.")
    rescue FailedNodeException
      Djinn.log_warn("Couldn't call delete_all_apps from UserAppServer.")
      return
    end
  end


  def start_backup_service()
    BackupRecoveryService.start()
  end

  def start_blobstore_server()
    # Each node has an nginx configuration to reach the datastore. Use it
    # to make sure we are fault-tolerant.
    BlobServer.start(my_node.private_ip, DatastoreServer::LISTEN_PORT_NO_SSL)
    return true
  end

  def start_search_role
    Search.start_master(false)
  end

  def stop_search_role
    Search.stop
  end

  def start_taskqueue_master()
    verbose = @options['verbose'].downcase == "true"
    TaskQueue.start_master(false, verbose)
    HAProxy.create_tq_server_config(my_node.private_ip,
                                    TaskQueue::HAPROXY_PORT)
    return true
  end


  def stop_taskqueue
    TaskQueue.stop
  end


  def start_taskqueue_slave()
    # All slaves connect to the master to start
    master_ip = nil
    @nodes.each { |node|
      master_ip = node.private_ip if node.is_taskqueue_master?
    }

    verbose = @options['verbose'].downcase == "true"
    TaskQueue.start_slave(master_ip, false, verbose)
    HAProxy.create_tq_server_config(my_node.private_ip,
                                    TaskQueue::HAPROXY_PORT)
    return true
  end

  # Starts the application manager which is a SOAP service in charge of
  # starting and stopping applications.
  def start_app_manager_server()
    @state = "Starting up AppManager"
    env_vars = {}
    app_manager_script = "#{APPSCALE_HOME}/AppManager/app_manager_server.py"
    start_cmd = "#{PYTHON27} #{app_manager_script}"
    stop_cmd = "#{PYTHON27} #{APPSCALE_HOME}/scripts/stop_service.py " +
          "#{app_manager_script} #{PYTHON27}"
    port = AppManagerClient::SERVER_PORT
    MonitInterface.start(:appmanagerserver, start_cmd, stop_cmd, [port],
                         env_vars, start_cmd, nil, nil, nil)
  end

  # Starts the Hermes service on this node.
  def start_hermes()
    @state = "Starting Hermes"
    Djinn.log_info("Starting Hermes service.")
    HermesService.start()
    Djinn.log_info("Done starting Hermes service.")
  end

  def stop_hermes
    HermesService.stop
  end

  # Starts the groomer service on this node. The groomer cleans the datastore of deleted
  # items and removes old logs.
  def start_groomer_service()
    @state = "Starting Groomer Service"
    Djinn.log_info("Starting groomer service.")
    GroomerService.start()
    Djinn.log_info("Done starting groomer service.")
  end

  def start_soap_server()
    db_master_ip = nil
    @nodes.each { |node|
      db_master_ip = node.private_ip if node.is_db_master?
    }
    HelperFunctions.log_and_crash("db master ip was nil") if db_master_ip.nil?

    db_local_ip = my_node.private_ip

    table = @options['table']

    env_vars = {}

    env_vars['APPSCALE_HOME'] = APPSCALE_HOME
    env_vars['MASTER_IP'] = db_master_ip
    env_vars['LOCAL_DB_IP'] = db_local_ip

    if table == "simpledb"
      env_vars['SIMPLEDB_ACCESS_KEY'] = @options['SIMPLEDB_ACCESS_KEY']
      env_vars['SIMPLEDB_SECRET_KEY'] = @options['SIMPLEDB_SECRET_KEY']
    end

    soap_script = `which appscale-uaserver`.chomp
    start_cmd = "#{soap_script} -t #{table}"
    stop_cmd = "#{PYTHON27} #{APPSCALE_HOME}/scripts/stop_service.py " +
          "#{soap_script} /usr/bin/python"
    port = UserAppClient::SERVER_PORT

    MonitInterface.start(:uaserver, start_cmd, stop_cmd, [port], env_vars,
                         start_cmd, nil, nil, nil)
  end

  def start_datastore_server
    db_master_ip = nil
    verbose = @options['verbose'].downcase == 'true'
    @nodes.each { |node|
      db_master_ip = node.private_ip if node.is_db_master?
    }
    HelperFunctions.log_and_crash("db master ip was nil") if db_master_ip.nil?

    table = @options['table']
    DatastoreServer.start(db_master_ip, my_node.private_ip, table, verbose)
    HAProxy.create_datastore_server_config(my_node.private_ip, DatastoreServer::PROXY_PORT, table)

    # Let's wait for the datastore to be active.
    HelperFunctions.sleep_until_port_is_open(my_node.private_ip, DatastoreServer::PROXY_PORT)
  end

  # Starts the Log Server service on this machine
  def start_log_server
    log_server_pid = "/var/run/appscale-logserver.pid"
    log_server_file = "/var/log/appscale/log_service-7422.log"
    start_cmd = "twistd --pidfile=#{log_server_pid}  --logfile " +
                "#{log_server_file} appscale-logserver"
    stop_cmd = "/bin/bash -c 'kill $(cat #{log_server_pid})'"
    port = 7422
    env = {
        'APPSCALE_HOME' => APPSCALE_HOME,
        'PYTHONPATH' => "#{APPSCALE_HOME}/LogService/"
    }

    MonitInterface.start(:log_service, start_cmd, stop_cmd, [port], env,
                         nil, nil, log_server_pid, nil)
    Djinn.log_info("Started Log Server successfully!")
  end


  def stop_log_server
    Djinn.log_info("Stopping Log Server")
    MonitInterface.stop(:log_service)
  end


  # Stops the Backup/Recovery service.
  def stop_backup_service()
    BackupRecoveryService.stop()
  end

  # Stops the blobstore server.
  def stop_blobstore_server
    BlobServer.stop
  end

  # Stops the User/Apps soap server.
  def stop_soap_server
    MonitInterface.stop(:uaserver)
  end

  # Stops the AppManager service
  def stop_app_manager_server
    MonitInterface.stop(:appmanagerserver)
  end

  # Stops the groomer service.
  def stop_groomer_service()
    Djinn.log_info("Stopping groomer service.")
    GroomerService.stop()
    Djinn.log_info("Done stopping groomer service.")
  end

  # Stops the datastore server.
  def stop_datastore_server
    DatastoreServer.stop()
  end

  def is_hybrid_cloud?
    if @options['infrastructure'].nil?
      false
    else
      @options['infrastructure'] == "hybrid"
    end
  end

  def is_cloud?
    return ['ec2', 'euca', 'gce', 'azure'].include?(@options['infrastructure'])
  end

  def restore_from_db?
    @options['restore_from_tar'] || @options['restore_from_ebs']
  end

  def build_taskqueue()
    Djinn.log_info('Building uncommitted taskqueue changes')
    extras = TaskQueue::OPTIONAL_FEATURES.join(',')
    if system('pip install --upgrade --no-deps ' +
              "#{APPSCALE_HOME}/AppTaskQueue[#{extras}] > /dev/null 2>&1")
      Djinn.log_info('Finished building taskqueue')
    else
      Djinn.log_error('Unable to build taskqueue')
    end
  end

  def build_datastore()
    Djinn.log_info('Building uncommitted datastore changes')
    if system('pip install --upgrade --no-deps ' +
              "#{APPSCALE_HOME}/AppDB > /dev/null 2>&1")
      Djinn.log_info('Finished building datastore')
    else
      Djinn.log_error('Unable to build datastore')
    end
  end

  def build_java_appserver()
    Djinn.log_info('Building uncommitted Java AppServer changes')

    # Cache package if it doesn't exist.
    java_sdk_archive = 'appengine-java-sdk-1.8.4.zip'
    local_archive = "#{APPSCALE_CACHE_DIR}/#{java_sdk_archive}"
    unless File.file?(local_archive)
      Net::HTTP.start(PACKAGE_MIRROR_DOMAIN) do |http|
        resp = http.get("#{PACKAGE_MIRROR_PATH}/#{java_sdk_archive}")
        open(local_archive, 'wb') do |file|
          file.write(resp.body)
        end
      end
    end

    java_server = "#{APPSCALE_HOME}/AppServer_Java"
    unzip = "unzip -o #{local_archive} -d #{java_server} > /dev/null 2>&1"
    install = "ant -f #{java_server}/build.xml install > /dev/null 2>&1"
    clean = "ant -f #{java_server}/build.xml clean-build > /dev/null 2>&1"
    if system(unzip) && system(install) && system(clean)
      Djinn.log_info('Finished building Java AppServer')
    else
      Djinn.log_error('Unable to build Java AppServer')
    end
  end

  # Run a build on modified directories so that changes will take effect.
  def build_uncommitted_changes()
    status = `git -C #{APPSCALE_HOME} status`
    build_taskqueue if status.include?('AppTaskQueue')
    build_datastore if status.include?('AppDB')
    build_java_appserver if status.include?('AppServer_Java')
  end

  def initialize_nodes_in_parallel(node_info)
    threads = []
    node_info.each { |slave|
      next if slave.private_ip == my_node.private_ip
      threads << Thread.new {
        initialize_node(slave)
      }
    }

    threads.each { |t| t.join }
    Djinn.log_info("Done initializing nodes.")
  end

  def initialize_node(node)
    copy_encryption_keys(node)
    validate_image(node)
    rsync_files(node)
    run_user_commands(node)
    start_appcontroller(node)
  end

  def validate_image(node)
    ip = node.public_ip
    key = node.ssh_key
    HelperFunctions.ensure_image_is_appscale(ip, key)
    HelperFunctions.ensure_version_is_supported(ip, key)
    HelperFunctions.ensure_db_is_supported(ip, @options['table'], key)
  end

  def copy_encryption_keys(dest_node)
    ip = dest_node.private_ip
    Djinn.log_info("Copying SSH keys to node at IP address #{ip}")
    ssh_key = dest_node.ssh_key
    HelperFunctions.sleep_until_port_is_open(ip, SSH_PORT)

    # Get the username to use for ssh (depends on environments).
    if ["ec2", "euca"].include?(@options['infrastructure'])
      # Add deployment key to remote instance's authorized_keys.
      user_name = "ubuntu"
      enable_root_login(ip, ssh_key, user_name)
    elsif @options['infrastructure'] == "gce"
      # Since GCE v1beta15, SSH keys don't immediately get injected to newly
      # spawned VMs. It takes around 30 seconds, so sleep a bit longer to be
      # sure.
      Djinn.log_debug("Waiting for SSH keys to get injected to #{ip}.")
      Kernel.sleep(60)

    elsif @options['infrastructure'] == 'azure'
      user_name = 'azureuser'
      enable_root_login(ip, ssh_key, user_name)
    end

    Kernel.sleep(SMALL_WAIT)

    secret_key_loc = "#{APPSCALE_CONFIG_DIR}/secret.key"
    cert_loc = "#{APPSCALE_CONFIG_DIR}/certs/mycert.pem"
    key_loc = "#{APPSCALE_CONFIG_DIR}/certs/mykey.pem"

    HelperFunctions.scp_file(secret_key_loc, secret_key_loc, ip, ssh_key)
    HelperFunctions.scp_file(cert_loc, cert_loc, ip, ssh_key)
    HelperFunctions.scp_file(key_loc, key_loc, ip, ssh_key)

    cloud_keys_dir = File.expand_path("#{APPSCALE_CONFIG_DIR}/keys/cloud1")
    make_dir = "mkdir -p #{cloud_keys_dir}"

    HelperFunctions.run_remote_command(ip, make_dir, ssh_key, NO_OUTPUT)
    HelperFunctions.scp_file(ssh_key, "#{APPSCALE_CONFIG_DIR}/ssh.key", ip, ssh_key)

    # Finally, on GCE, we need to copy over the user's credentials, in case
    # nodes need to attach persistent disks.
    return if @options['infrastructure'] != "gce"

    client_secrets = "#{APPSCALE_CONFIG_DIR}/client_secrets.json"
    gce_oauth = "#{APPSCALE_CONFIG_DIR}/oauth2.dat"

    if File.exists?(client_secrets)
      HelperFunctions.scp_file(client_secrets, client_secrets, ip, ssh_key)
    end

    HelperFunctions.scp_file(gce_oauth, gce_oauth, ip, ssh_key)
  end

  # Logs into the named host and alters its ssh configuration to enable the
  # root user to directly log in.
  def enable_root_login(ip, ssh_key, user_name)
    options = '-o StrictHostkeyChecking=no -o NumberOfPasswordPrompts=0'
    backup_keys = 'sudo cp -p /root/.ssh/authorized_keys ' +
        '/root/.ssh/authorized_keys.old'
    Djinn.log_run("ssh -i #{ssh_key} #{options} 2>&1 #{user_name}@#{ip} " +
                      "'#{backup_keys}'")

    merge_keys = 'sudo sed -n ' +
        '"/Please login/d; w/root/.ssh/authorized_keys" ' +
        "~#{user_name}/.ssh/authorized_keys /root/.ssh/authorized_keys.old"
    Djinn.log_run("ssh -i #{ssh_key} #{options} 2>&1 #{user_name}@#{ip} " +
                      "'#{merge_keys}'")
  end

  def rsync_files(dest_node)
    appdb = "#{APPSCALE_HOME}/AppDB"
    app_manager = "#{APPSCALE_HOME}/AppManager"
    app_task_queue = "#{APPSCALE_HOME}/AppTaskQueue"
    controller = "#{APPSCALE_HOME}/AppController"
    iaas_manager = "#{APPSCALE_HOME}/InfrastructureManager"
    lib = "#{APPSCALE_HOME}/lib"
    app_dashboard = "#{APPSCALE_HOME}/AppDashboard"
    scripts = "#{APPSCALE_HOME}/scripts"
    server = "#{APPSCALE_HOME}/AppServer"
    server_java = "#{APPSCALE_HOME}/AppServer_Java"
    xmpp_receiver = "#{APPSCALE_HOME}/XMPPReceiver"
    log_service = "#{APPSCALE_HOME}/LogService"

    ssh_key = dest_node.ssh_key
    ip = dest_node.private_ip
    options = "-e 'ssh -i #{ssh_key}' -arv --filter '- *.pyc'"

    HelperFunctions.shell("rsync #{options} #{controller}/* root@#{ip}:#{controller}")
    HelperFunctions.shell("rsync #{options} #{server}/* root@#{ip}:#{server}")
    HelperFunctions.shell("rsync #{options} #{server_java}/* root@#{ip}:#{server_java}")
    HelperFunctions.shell("rsync #{options} #{app_dashboard}/* root@#{ip}:#{app_dashboard}")
    HelperFunctions.shell("rsync #{options} --exclude='logs/*' #{appdb}/* root@#{ip}:#{appdb}")
    HelperFunctions.shell("rsync #{options} #{app_manager}/* root@#{ip}:#{app_manager}")
    HelperFunctions.shell("rsync #{options} #{iaas_manager}/* root@#{ip}:#{iaas_manager}")
    HelperFunctions.shell("rsync #{options} #{xmpp_receiver}/* root@#{ip}:#{xmpp_receiver}")
    HelperFunctions.shell("rsync #{options} #{lib}/* root@#{ip}:#{lib}")
    HelperFunctions.shell("rsync #{options} #{app_task_queue}/* root@#{ip}:#{app_task_queue}")
    HelperFunctions.shell("rsync #{options} #{scripts}/* root@#{ip}:#{scripts}")
    HelperFunctions.shell("rsync #{options} #{log_service}/* root@#{ip}:#{log_service}")
    if dest_node.is_appengine?
      locations_json = "#{APPSCALE_CONFIG_DIR}/locations-#{@options['keyname']}.json"
      loop {
        break if File.exists?(locations_json)
        Djinn.log_warn("Locations JSON file does not exist on head node yet, #{dest_node.private_ip} is waiting ")
        Kernel.sleep(SMALL_WAIT)
      }
      Djinn.log_info("Copying locations.json to #{dest_node.private_ip}")
      HelperFunctions.shell("rsync #{options} #{locations_json} root@#{ip}:#{locations_json}")
    end

    # Run a build on modified directories so that changes will take effect.
    get_status = 'git -C appscale status'
    ssh_opts = "-i #{ssh_key} -o StrictHostkeyChecking=no " +
      '-o NumberOfPasswordPrompts=0'
    status = `ssh #{ssh_opts} root@#{ip} #{get_status}`

    if status.include?('AppTaskQueue')
      Djinn.log_info("Building uncommitted taskqueue changes on #{ip}")
      extras = TaskQueue::OPTIONAL_FEATURES.join(',')
      build_tq = 'pip install --upgrade --no-deps ' +
        "#{APPSCALE_HOME}/AppTaskQueue[#{extras}]"
      if system(%Q[ssh #{ssh_opts} root@#{ip} "#{build_tq}" > /dev/null 2>&1])
        Djinn.log_info("Finished building taskqueue on #{ip}")
      else
        Djinn.log_error("Unable to build taskqueue on #{ip}")
      end
    end

    if status.include?('AppDB')
      Djinn.log_info("Building uncommitted datastore changes on #{ip}")
      build_ds = "pip install --upgrade --no-deps #{APPSCALE_HOME}/AppDB"
      if system(%Q[ssh #{ssh_opts} root@#{ip} "#{build_ds}" > /dev/null 2>&1])
        Djinn.log_info("Finished building datastore on #{ip}")
      else
        Djinn.log_error("Unable to build datastore on #{ip}")
      end
    end

    if status.include?('AppServer_Java')
      Djinn.log_info("Building uncommitted Java AppServer changes on #{ip}")

      java_sdk_archive = 'appengine-java-sdk-1.8.4.zip'
      remote_archive = "#{APPSCALE_CACHE_DIR}/#{java_sdk_archive}"
      mirrored_package = "http://#{PACKAGE_MIRROR_DOMAIN}" +
        "#{PACKAGE_MIRROR_PATH}/#{java_sdk_archive}"
      get_package = "if [ ! -f #{remote_archive} ]; " +
        "then curl -o #{remote_archive} #{mirrored_package} ; fi"
      system(%Q[ssh #{ssh_opts} root@#{ip} "#{get_package}" > /dev/null 2>&1])

      build = [
        "unzip -o #{remote_archive} -d #{server_java}",
        "ant -f #{server_java}/build.xml install",
        "ant -f #{server_java}/build.xml clean-build"
      ].join(' && ')
      if system(%Q[ssh #{ssh_opts} root@#{ip} "#{build}" > /dev/null 2>&1])
        Djinn.log_info("Finished building Java AppServer on #{ip}")
      else
        Djinn.log_error("Unable to build Java AppServer on #{ip}")
      end
    end
  end


  # Writes locations (IP addresses) for the various nodes fulfilling
  # specific roles, in the local filesystems. These files will be updated
  # as the deployment adds or removes nodes.
  def write_locations
    all_ips = []
    load_balancer_ips = []
    login_ips = @options['login'].split(/[\s,]+/)
    master_ips = []
    memcache_ips = []
    num_of_nodes = @nodes.length.to_s
    search_ips = []
    slave_ips = []
    taskqueue_ips = []

    my_public = my_node.public_ip
    my_private = my_node.private_ip

    # Populate the appropriate list.
    @nodes.each { |node|
      all_ips << node.private_ip
      load_balancer_ips << node.private_ip if node.is_load_balancer?
      master_ips << node.private_ip if node.is_db_master?
      memcache_ips << node.private_ip if node.is_memcache?
      search_ips << node.private_ip if node.is_search?
      slave_ips << node.private_ip if node.is_db_slave?
      taskqueue_ips << node.private_ip if node.is_taskqueue_master? ||
        node.is_taskqueue_slave?
    }
    slave_ips << master_ips[0] if slave_ips.empty?

    # Turn the arrays into string.
    all_ips_content = all_ips.join("\n") + "\n"
    memcache_content = memcache_ips.join("\n") + "\n"
    load_balancer_content = load_balancer_ips.join("\n") + "\n"
    taskqueue_content = taskqueue_ips.join("\n") + "\n"
    login_content = login_ips.join("\n") + "\n"
    master_content = master_ips.join("\n") + "\n"
    search_content = search_ips.join("\n") + "\n"
    slaves_content = slave_ips.join("\n") + "\n"

    new_content = all_ips_content + login_content + load_balancer_content +
      master_content + memcache_content + my_public + my_private +
      num_of_nodes + taskqueue_content + search_content + slaves_content

    # If nothing changed since last time we wrote locations file(s), skip it.
    if new_content != @locations_content
      @locations_content = new_content

      # For the taskqueue, let's shuffle the entries, and then put
      # ourselves as first option, if we are a taskqueue node.
      taskqueue_ips.shuffle!
      if my_node.is_taskqueue_master? || my_node.is_taskqueue_slave?
        taskqueue_ips.delete(my_private)
        taskqueue_ips.unshift(my_private)
      end
      taskqueue_content = taskqueue_ips.join("\n") + "\n"

      head_node_private_ip = get_shadow.private_ip
      HelperFunctions.write_file("#{APPSCALE_CONFIG_DIR}/head_node_private_ip",
                                 "#{head_node_private_ip}\n")

      Djinn.log_info("All private IPs: #{all_ips}.")
      HelperFunctions.write_file("#{APPSCALE_CONFIG_DIR}/all_ips", all_ips_content)

      Djinn.log_info("Load balancer location(s): #{load_balancer_ips}.")
      load_balancer_file = "#{APPSCALE_CONFIG_DIR}/load_balancer_ips"
      HelperFunctions.write_file(load_balancer_file, load_balancer_content)

      Djinn.log_info("Deployment public name(s)/IP(s): #{login_ips}.")
      login_file = "#{APPSCALE_CONFIG_DIR}/login_ip"
      HelperFunctions.write_file(login_file, login_content)

      Djinn.log_info("Memcache locations: #{memcache_ips}.")
      memcache_file = "#{APPSCALE_CONFIG_DIR}/memcache_ips"
      HelperFunctions.write_file(memcache_file, memcache_content)

      Djinn.log_info("Taskqueue locations: #{taskqueue_ips}.")
      HelperFunctions.write_file(TASKQUEUE_FILE,  taskqueue_content)

      Djinn.log_info("Database master is at #{master_ips}, slaves are at #{slave_ips}.")
      HelperFunctions.write_file("#{APPSCALE_CONFIG_DIR}/masters", "#{master_content}")

      unless slaves_content.chomp.empty?
        HelperFunctions.write_file("#{APPSCALE_CONFIG_DIR}/slaves",
                                   slaves_content)
      end

      Djinn.log_info("My public IP is #{my_public}, and my private is #{my_private}.")
      HelperFunctions.write_file("#{APPSCALE_CONFIG_DIR}/my_public_ip", "#{my_public}")
      HelperFunctions.write_file("#{APPSCALE_CONFIG_DIR}/my_private_ip", "#{my_private}")

      Djinn.log_info("Writing num_of_nodes as #{num_of_nodes}.")
      HelperFunctions.write_file("#{APPSCALE_CONFIG_DIR}/num_of_nodes", "#{num_of_nodes}\n")

      Djinn.log_info("Search service locations: #{search_ips}.")
      unless search_content.chomp.empty?
        HelperFunctions.write_file(Search::SEARCH_LOCATION_FILE,
                                   search_content)
      end
    end
  end


  # Updates files on this machine with information about our hostname
  # and a mapping of where other machines are located.
  def update_hosts_info()
    # If we are running in Docker, don't try to set the hostname.
    if system("grep docker /proc/1/cgroup > /dev/null")
      return
    end

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


  # Reset the drain flags on HAProxy for to-be-terminated AppServers.
  def reset_drain
    @apps_loaded.each{ |app|
      unless @terminated[app].nil?
        @terminated[app].each { |location|
          HAProxy.ensure_no_pending_request(app, location)
        }
      end
    }
  end


  # Writes new nginx and haproxy configuration files for the App Engine
  # applications hosted in this deployment. Callers should invoke this
  # method whenever there is a change in the number of machines hosting
  # App Engine apps.
  def regenerate_routing_config()
    Djinn.log_debug("Regenerating nginx and haproxy config files for apps.")
    my_public = my_node.public_ip
    my_private = my_node.private_ip
    login_ip = get_shadow.private_ip

    @apps_loaded.each { |app|
      # Check that we have the application information needed to
      # regenerate the routing configuration.
      appservers = []
      unless (@app_info_map[app].nil? or @app_info_map[app]['nginx'].nil? or
              @app_info_map[app]['nginx_https'].nil? or
              @app_info_map[app]['haproxy'].nil? or
              @app_info_map[app]['appengine'].nil? or
              @app_info_map[app]['language'].nil?)
        http_port = @app_info_map[app]['nginx']
        https_port = @app_info_map[app]['nginx_https']
        proxy_port = @app_info_map[app]['haproxy']
        app_language = @app_info_map[app]['language']
        Djinn.log_debug("Regenerating nginx config for app #{app}, on http " +
          "port #{http_port}, https port #{https_port}, and haproxy port " +
          "#{proxy_port}.")

        # Let's see if we already have any AppServers running for this
        # application. We count also the ones we need to terminate.
        @app_info_map[app]['appengine'].each { |location|
          _, port = location.split(":")
          next if Integer(port) < 0
          appservers << location
        }
        unless @terminated[app].nil?
          to_remove = []
          @terminated[app].each { |location, when_detected|
            # Let's make sure it doesn't receive traffic, and see how many
            # sessions are still active.
            if Time.now.to_i > when_detected + Integer(@options['appserver_timeout'])
              Djinn.log_info("#{location} has ran out of time: removing it.")
              to_remove << location
            elsif HAProxy.ensure_no_pending_request(app, location) <= 0
              Djinn.log_info("#{location} has no more sessions: removing it.")
              to_remove << location
            else
              appservers << location
            end
          }
          to_remove.each{ |location| @terminated[app].delete(location) }
        end
      end

      if appservers.empty?
        # If no AppServer is running, we clear the routing and the crons.
        Djinn.log_debug("Removing routing for #{app} since no AppServer is running.")
        Nginx.remove_app(app)
        CronHelper.clear_app_crontab(app)
        HAProxy.remove_app(app)
      else
        begin
          static_handlers = HelperFunctions.parse_static_data(app)
        rescue => except
          # This specific exception may be a JSON parse error.
          error_msg = "ERROR: Unable to parse app.yaml file for #{app}. "\
            "Exception of #{except.class} with message #{except.message}"
          place_error_app(app, error_msg, app_language)
          static_handlers = []
        end

        # If nginx config files have been updated, we communicate the app's
        # ports to the UserAppServer to make sure we have the latest info.
        if Nginx.write_fullproxy_app_config(app, http_port, https_port,
            my_public, my_private, proxy_port, static_handlers, login_ip,
            app_language)
          uac = UserAppClient.new(my_node.private_ip, @@secret)
          begin
            if uac.add_instance(app, my_public, http_port, https_port)
              Djinn.log_info("Committed application info for #{app} " +
                "to user_app_server")
            end
          rescue FailedNodeException
            Djinn.log_warn("Failed to talk to UAServer to add_instance for #{app}.")
          end
        end

        HAProxy.update_app_config(my_private, app,
          @app_info_map[app]['haproxy'], appservers)
      end

      # We need to set the drain on haproxy on the terminated AppServers,
      # since a reload of HAProxy would have reset them. We do it for each
      # app in order to minimize the window of a terminated AppServer
      # being reinstead as active by HAProxy.
      reset_drain
    }
    Djinn.log_debug("Done updating nginx and haproxy config files.")
  end


  def my_node()
    if @my_index.nil?
      find_me_in_locations()
    end

    if @my_index.nil?
      Djinn.log_debug("My index is nil - is nodes nil? #{@nodes.nil?}")
      if @nodes.nil?
        Djinn.log_debug("My nodes is nil also, timing error? race condition?")
      else
        HelperFunctions.log_and_crash("Couldn't find our position in #{@nodes}")
      end
    end

    return @nodes[@my_index]
  end

  # If we are in cloud mode, we should mount any volume containing our
  # local state.
  def mount_persistent_storage
    # If we don't have any disk to attach, we are done.
    return unless my_node.disk

    imc = InfrastructureManagerClient.new(@@secret)
    begin
      device_name = imc.attach_disk(@options, my_node.disk, my_node.instance_id)
    rescue FailedNodeException
      Djinn.log_warn("Failed to talk to InfrastructureManager while attaching disk")
      # TODO: this logic (and the following) to retry forever is not
      # healhy.
      Kernel.sleep(SMALL_WAIT)
      retry
    end
    loop {
      if File.exists?(device_name)
        Djinn.log_info("Device #{device_name} exists - mounting it.")
        break
      else
        Djinn.log_info("Device #{device_name} does not exist - waiting for " +
          "it to exist.")
        Kernel.sleep(SMALL_WAIT)
      end
    }
    Djinn.log_run("mkdir -p #{PERSISTENT_MOUNT_POINT}")

    # Check if the device is already mounted (for example we restarted the
    # AppController).
    if system("mount | grep -E '^#{device_name} '  > /dev/null 2>&1")
      Djinn.log_info("Device #{device_name} is already mounted.")
      return
    end

    # We need to mount and possibly format the disk.
    mount_output = Djinn.log_run("mount -t ext4 #{device_name} " +
      "#{PERSISTENT_MOUNT_POINT} 2>&1")
    if mount_output.empty?
      Djinn.log_info("Mounted persistent disk #{device_name}, without " +
        "needing to format it.")
    else
      Djinn.log_info("Formatting persistent disk #{device_name}.")
      Djinn.log_run("mkfs.ext4 -F #{device_name}")
      Djinn.log_info("Mounting persistent disk #{device_name}.")
      Djinn.log_run("mount -t ext4 #{device_name} #{PERSISTENT_MOUNT_POINT}" +
        " 2>&1")
    end

    Djinn.log_run("mkdir -p #{PERSISTENT_MOUNT_POINT}/apps")

    # Finally, RabbitMQ expects data to be present at /var/lib/rabbitmq.
    # Make sure there is data present there and that it points to our
    # persistent disk.
    if File.directory?("#{PERSISTENT_MOUNT_POINT}/rabbitmq")
      Djinn.log_run("rm -rf /var/lib/rabbitmq")
    else
      Djinn.log_run("mv /var/lib/rabbitmq #{PERSISTENT_MOUNT_POINT}")
    end
    Djinn.log_run("ln -s #{PERSISTENT_MOUNT_POINT}/rabbitmq /var/lib/rabbitmq")
    return
  end

  # This function performs basic setup ahead of starting the API services.
  def initialize_server()
    if not HAProxy.is_running?
      HAProxy.initialize_config()
      HAProxy.start()
      Djinn.log_info("HAProxy configured and started.")
    else
      Djinn.log_info("HAProxy already configured.")
    end
    if not Nginx.is_running?
      Nginx.initialize_config()
      Nginx.start()
      Djinn.log_info("Nginx configured and started.")
    else
      Djinn.log_info("Nginx already configured and running.")
    end

    # As per trusty's version of haproxy, we need to have a listening
    # socket for the daemon to start: we do use the uaserver to configured
    # a default route.
    configure_uaserver()

    # Volume is mounted, let's finish the configuration of static files.
    if my_node.is_shadow? and not my_node.is_appengine?
      write_app_logrotate()
      Djinn.log_info("Copying logrotate script for centralized app logs")
    end
    configure_db_nginx
    write_locations

    update_hosts_info
    if FIREWALL_IS_ON
      Djinn.log_run("bash #{APPSCALE_HOME}/firewall.conf")
    end
    write_zookeeper_locations
  end

  # Sets up logrotate for this node's centralized app logs.
  # This method is called only when the appengine role does not run
  # on the head node.
  def write_app_logrotate()
    template_dir = File.join(File.dirname(__FILE__), "../lib/templates")
    FileUtils.cp("#{template_dir}/#{APPSCALE_APP_LOGROTATE}",
      "#{LOGROTATE_DIR}/appscale-app")
  end

  # Runs any commands provided by the user in their AppScalefile on the given
  # machine.
  #
  # Args:
  # - node: A DjinnJobData that represents the machine where the given commands
  #   should be executed.
  def run_user_commands(node)
    if @options['user_commands'].class == String
      begin
        commands = JSON.load(@options['user_commands'])
      rescue JSON::ParserError
        commands = @options['user_commands']
      end

      if commands.class == String
        commands = [commands]
      end
    else
      commands = []
    end
    Djinn.log_debug("commands are #{commands}, of class #{commands.class.name}")

    if commands.empty?
      Djinn.log_debug("No user-provided commands were given.")
      return
    end

    ip = node.private_ip
    ssh_key = node.ssh_key
    commands.each { |command|
      HelperFunctions.run_remote_command_without_output(ip, command, ssh_key)
    }
  end

  def set_appcontroller_monit()
    Djinn.log_debug("Configuring AppController monit.")
    env = {
      'HOME' => '/root',
      'PATH' => '$PATH:/usr/local/bin',
      'APPSCALE_HOME' => APPSCALE_HOME,
      'EC2_HOME' => ENV['EC2_HOME'],
      'JAVA_HOME' => ENV['JAVA_HOME']
    }
    start = "/usr/bin/ruby -w /root/appscale/AppController/djinnServer.rb"
    stop = "/usr/sbin/service appscale-controller stop"

    # Let's make sure we don't have 2 jobs monitoring the controller.
    FileUtils.rm_rf("/etc/monit/conf.d/controller-17443.cfg")

    begin
      MonitInterface.start(:controller, start, stop, [SERVER_PORT], env,
                           start, nil, nil, nil)
    rescue
      Djinn.log_warn("Failed to set local AppController monit: retrying.")
      retry
    end
  end

  def start_appcontroller(node)
    ip = node.private_ip

    # Start the AppController on the remote machine.
    remote_cmd = "/usr/sbin/service appscale-controller start"
    tries = RETRIES
    begin
      result = HelperFunctions.run_remote_command(ip, remote_cmd, node.ssh_key, true)
    rescue => except
      backtrace = except.backtrace.join("\n")
      remote_start_msg = "[remote_start] Unforeseen exception when " + \
        "talking to #{ip}: #{except}\nBacktrace: #{backtrace}"
      tries -= 1
      if tries > 0
        Djinn.log_warn(remote_start_msg)
        retry
      else
        @state = remote_start_msg
        HelperFunctions.log_and_crash(@state, WAIT_TO_CRASH)
      end
    end
    Djinn.log_info("Starting AppController for #{ip} returned #{result}.")

    # If the node is already initialized, it may belong to another
    # deployment: stop the initialization process.
    acc = AppControllerClient.new(ip, @@secret)
    tries = RETRIES
    begin
      if acc.is_done_initializing?
        Djinn.log_warn("The node at #{ip} was already initialized!")
        return
      end
    rescue FailedNodeException => except
      tries -= 1
      if tries > 0
        Djinn.log_debug("AppController at #{ip} not responding yet: retrying.")
        retry
      else
        @state = "Couldn't talk to AppController at #{ip} for #{except.message}."
        HelperFunctions.log_and_crash(@state, WAIT_TO_CRASH)
      end
    end
    Djinn.log_debug("Sending data to #{ip}.")

    layout = Djinn.convert_location_class_to_json(@nodes)
    options = JSON.dump(@options)
    begin
      result = acc.set_parameters(layout, options)
    rescue FailedNodeException => e
      @state = "Couldn't set parameters on node at #{ip} for #{e.message}."
      HelperFunctions.log_and_crash(@state, WAIT_TO_CRASH)
    end
    Djinn.log_info("Parameters set on node at #{ip} returned #{result}.")
  end

  def start_memcache()
    @state = "Starting up memcache"
    Djinn.log_info("Starting up memcache")
    port = 11211
    start_cmd = "/usr/bin/memcached -m 64 -p #{port} -u root"
    stop_cmd = "#{PYTHON27} #{APPSCALE_HOME}/scripts/stop_service.py " +
          "/usr/bin/memcached #{port}"
    MonitInterface.start(:memcached, start_cmd, stop_cmd, [port], nil,
                         start_cmd, nil, nil, nil)
  end

  def stop_memcache()
    MonitInterface.stop(:memcached)
  end

  def start_ejabberd()
    @state = "Starting up XMPP server"
    my_public = my_node.public_ip
    Ejabberd.stop()
    Djinn.log_run("rm -f /var/lib/ejabberd/*")
    Ejabberd.write_auth_script(my_public, get_db_master.private_ip, @@secret)
    Ejabberd.write_config_file(my_public)
    Ejabberd.start()
  end

  def stop_ejabberd()
    Ejabberd.stop()
  end

  # Create the system user used to start and run system's applications.
  def create_appscale_user()
    uac = UserAppClient.new(my_node.private_ip, @@secret)
    password = SecureRandom.base64
    begin
      result = uac.commit_new_user(APPSCALE_USER, password, "app")
      Djinn.log_info("Created/confirmed system user: (#{result})")
    rescue FailedNodeException
      Djinn.log_warn("Failed to talk to the UserAppServer while committing " +
        "the system user.")
    end
  end

  # Start the AppDashboard web service which allows users to login, upload
  # and remove apps, and view the status of the AppScale deployment. Other
  # nodes will need to delete the old source since we regenerate each
  # 'up'.
  def prep_app_dashboard()
    @state = "Preparing AppDashboard"
    Djinn.log_info("Preparing AppDashboard")

    my_public = my_node.public_ip
    my_private = my_node.private_ip

    # Reserve dashboard app ID.
    result = reserve_app_id(APPSCALE_USER, AppDashboard::APP_NAME,
      AppDashboard::APP_LANGUAGE, @@secret)
    Djinn.log_debug("reserve_app_id for dashboard returned: #{result}.")

    # Create, upload, and unpack the application.
    AppDashboard.start(my_public, my_private,
        PERSISTENT_MOUNT_POINT, @@secret)
    APPS_LOCK.synchronize {
      setup_app_dir(AppDashboard::APP_NAME, true)
    }

    # Assign the specific ports to it.
    APPS_LOCK.synchronize {
      if @app_info_map[AppDashboard::APP_NAME].nil?
        @app_info_map[AppDashboard::APP_NAME] = {
          'nginx' => AppDashboard::LISTEN_PORT,
          'nginx_https' => AppDashboard::LISTEN_SSL_PORT,
          'haproxy' => AppDashboard::PROXY_PORT,
          'appengine' => [],
          'language' => AppDashboard::APP_LANGUAGE,
          'max_memory' => DEFAULT_MEMORY,
          'min_appengines' => 3
        }
      end
      @app_names << AppDashboard::APP_NAME
    }
  end

  # Stop the AppDashboard web service.
  def stop_app_dashboard()
    Djinn.log_info("Shutting down AppDashboard")
    AppDashboard.stop()
  end

  def start_shadow()
    Djinn.log_info("Starting Shadow role")
  end

  def stop_shadow()
    Djinn.log_info("Stopping Shadow role")
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
  #   language: The language the application is written in.
  def place_error_app(app_name, err_msg, language)
    Djinn.log_error("Placing error application for #{app_name} because of: #{err_msg}")
    ea = ErrorApp.new(app_name, err_msg)
    ea.generate(language)
  end


  # Login nodes will compares the list of applications that should be
  # running according to the UserAppServer with the list we have on the
  # load balancer, and marks the missing apps for start during the next
  # cycle.
  def starts_new_apps_or_appservers()
    uac = UserAppClient.new(my_node.private_ip, @@secret)
    Djinn.log_debug("Checking applications that should be running.")
    begin
      app_list = uac.get_all_apps()
    rescue FailedNodeException => except
      Djinn.log_warn("starts_new_apps_or_appservers: failed to get apps (#{except}).")
      app_list = []
    end
    Djinn.log_debug("Apps to check: #{app_list}.") unless app_list.empty?
    app_list.each { |app|
      begin
        # If app is not enabled or if we already know of it, we skip it.
        next if @app_names.include?(app)
        begin
          next unless uac.is_app_enabled?(app)
        rescue FailedNodeException
          Djinn.log_warn("Failed to talk to the UserAppServer about " +
            "application #{app}.")
          next
        end

        # If we don't have a record for this app, we start it.
        Djinn.log_info("Adding #{app} to running apps.")

        # We query the UserAppServer looking for application data, in
        # particular ports and language.
        result = uac.get_app_data(app)
        app_data = JSON.load(result)
        Djinn.log_debug("#{app} metadata: #{app_data}")

        app_language = app_data['language']
        Djinn.log_info("Restoring app #{app} (language #{app_language})" +
          " with ports #{app_data['hosts']}.")

        @app_info_map[app] = {} if @app_info_map[app].nil?
        @app_info_map[app]['language'] = app_language if app_language
        if app_data['hosts'].values[0]
          if app_data['hosts'].values[0]['http']
            @app_info_map[app]['nginx'] = app_data['hosts'].values[0]['http']
          end
          if app_data['hosts'].values[0]['https']
            @app_info_map[app]['nginx_https'] = app_data['hosts'].values[0]['https']
          end
        end
        @app_names = @app_names + [app]
      rescue FailedNodeException
        Djinn.log_warn("Couldn't check if app #{app} exists on #{db_private_ip}")
      end
    }
    @app_names.uniq!

    # And now starts applications.
    @state = "Preparing to run AppEngine apps if needed."

    apps_to_load = @app_names - @apps_loaded
    apps_to_load.each { |app|
      setup_appengine_application(app)
    }
  end

  # This function ensures that applications we are not aware of (that is
  # they are not accounted for) will be terminated and, potentially old
  # sources, will be removed.
  def check_stopped_apps()
    # The running AppServers on this node must match the login node view.
    # Only one thread talking to the AppManagerServer at a time.
    if AMS_LOCK.locked?
      Djinn.log_debug("Another thread already working with AppManager.")
      return
    end

    uac = UserAppClient.new(my_node.private_ip, @@secret)
    Djinn.log_debug("Checking applications that have been stopped.")
    app_list = HelperFunctions.get_loaded_apps()
    app_list.each { |app|
      next if @app_names.include?(app)
      next if RESERVED_APPS.include?(app)
      begin
        next if uac.is_app_enabled?(app)
      rescue FailedNodeException
        Djinn.log_warn("Failed to talk to the UserAppServer about app #{app}.")
        next
      end

      Djinn.log_info("#{app} is no longer running: removing old states.")

      if my_node.is_load_balancer?
        stop_xmpp_for_app(app)
        Nginx.remove_app(app)

        # Since the removal of an app from HAProxy can cause a reset of
        # the drain flags, let's set them again.
        HAProxy.remove_app(app)
        reset_drain
      end

      if my_node.is_appengine?
        AMS_LOCK.synchronize {
          Djinn.log_debug("Calling AppManager to stop app #{app}.")
          app_manager = AppManagerClient.new(my_node.private_ip)
          begin
            if app_manager.stop_app(app)
              Djinn.log_info("Asked AppManager to shut down app #{app}.")
            else
              Djinn.log_warn("AppManager is unable to stop app #{app}.")
            end
          rescue FailedNodeException
            Djinn.log_warn("Failed to talk to AppManager about stopping #{app}.")
          end

          begin
            ZKInterface.remove_app_entry(app, my_node.private_ip)
          rescue FailedZooKeeperOperationException => except
            Djinn.log_warn("check_stopped_apps: got exception talking to " +
              "zookeeper: #{except.message}.")
          end
        }
      end

      if my_node.is_shadow?
        Djinn.log_info("Removing log configuration for #{app}.")
        FileUtils.rm_f(get_rsyslog_conf(app))
        HelperFunctions.shell("service rsyslog restart")
      end

      Djinn.log_run("rm -rf #{HelperFunctions.get_app_path(app)}")
      CronHelper.clear_app_crontab(app)
      maybe_stop_taskqueue_worker(app)
      Djinn.log_debug("Done cleaning up after stopped application #{app}.")
    }
  end


  # LoadBalancers needs to do some extra work to drain AppServers before
  # removing them, and to detect when AppServers failed or terminated.
  def check_haproxy
    @apps_loaded.each{ |app|
      running, failed = HAProxy.list_servers(app)
      if my_node.is_shadow?
        failed.each{ |appserver|
          Djinn.log_warn("Detected failed AppServer for #{app}: #{appserver}.")
          @app_info_map[app]['appengine'].delete(appserver)
        }
      end
      running.each{ |appserver|
        unless @app_info_map[app]['appengine'].nil?
          next if @app_info_map[app]['appengine'].include?(appserver)
        end
        @terminated[app] = {} if @terminated[app].nil?
        @terminated[app][appserver] = Time.now.to_i
        delete_instance_from_dashboard(app, appserver)
        Djinn.log_info("Terminated AppServer #{appserver} will not received requests.")
      }
    }
    regenerate_routing_config
  end

  # All nodes will compare the list of AppServers they should be running,
  # with the list of AppServers actually running, and make the necessary
  # adjustments. Effectively only login node and appengine nodes will run
  # AppServers (login node runs the dashboard).
  def check_running_apps()
    # The running AppServers on this node must match the login node view.
    # Only one thread talking to the AppManagerServer at a time.
    if AMS_LOCK.locked?
      Djinn.log_debug("Another thread already working with AppManager.")
      return
    end

    to_start = []
    no_appservers = []
    my_apps = []
    to_end = []
    APPS_LOCK.synchronize {
      @app_info_map.each { |app, info|
        # Machines with a taskqueue role need to ensure that the latest
        # queue configuration files are loaded and that we have the
        # queue.yaml from the application.
        setup_app_dir(app)
        maybe_reload_taskqueue_worker(app)

        # The remainer of this loop is for AppEngine nodes only, so we
        # need to do work only if we have AppServers.
        next unless info['appengine']

        if info['appengine'].length > HelperFunctions::NUM_ENTRIES_TO_PRINT
          Djinn.log_debug("Checking #{app} with #{info['appengine'].length} AppServers.")
        else
          Djinn.log_debug("Checking #{app} running at #{info['appengine']}.")
        end
        info['appengine'].each { |location|
          host, port = location.split(":")
          next if @my_private_ip != host

          if Integer(port) < 0
            to_start << app
            no_appservers << app
          elsif not MonitInterface.is_running?("#{app}-#{port}")
            Djinn.log_warn("Didn't find the AppServer for #{app} at port #{port}.")
            to_end << "#{app}:#{port}"
          else
            my_apps << "#{app}:#{port}"
          end
        }
      }
    }
    # Let's make sure we have the proper list of apps with no currently
    # running AppServers.
    my_apps.each { |appserver|
      app, _ = appserver.split(":")
      no_appservers.delete(app)
      @unaccounted.delete(appserver)
    }
    Djinn.log_debug("Running AppServers on this node: #{my_apps}.") unless my_apps.empty?

    # Check that all the AppServers running are indeed known to the
    # head node.
    MonitInterface.running_appengines().each { |appengine|
      # Nothing to do if we already account for this AppServer.
      next if my_apps.include?(appengine)

      # Here we have an AppServer which is not listed in @app_info_map. We
      # have 2 options: it may be coming up and it's not registered yet,
      # or it has been terminated. In either case, we give a grace period
      # and then we terminate it. The time needs to be at least
      # 'appserver_timeout' for termination.
      app, _ = appengine.split(":")
      if @unaccounted[appengine].nil?
        Djinn.log_debug("Found unaccounted AppServer #{appengine} for #{app}.")
        @unaccounted[appengine] = Time.now.to_i
      end
      been_here = Time.now.to_i - @unaccounted[appengine]
      if been_here > Integer(@options['appserver_timeout']) * 2
        Djinn.log_debug("AppServer #{appengine} for #{app} timed out.")
        to_end << appengine
        next
      end
      if to_start.include?(app) && been_here < DUTY_CYCLE * 3
        Djinn.log_debug("Ignoring request for #{app} since we have pending AppServers.")
        to_start.delete(app)
        no_appservers.delete(app)
      end
    }
    Djinn.log_debug("First AppServers to start: #{no_appservers}.") unless no_appservers.empty?
    Djinn.log_debug("AppServers to start: #{to_start}.") unless to_start.empty?
    Djinn.log_debug("AppServers to terminate: #{to_end}.") unless to_end.empty?

    # Now we do the talking with the appmanagerserver. Since it may take
    # some time to start/stop apps, we do this in a thread. We do one
    # operation at a time since it is expensive and we want to
    # re-evaluate.
    Thread.new {
      AMS_LOCK.synchronize {
        # We then start or terminate AppServers as needed. We do it one a
        # time since it's lengthy proposition and we want to revisit the
        # decision each time.
        if !no_appservers[0].nil?
          app = no_appservers[0]
          Djinn.log_info("Starting first AppServer for app: #{app}.")
          ret = add_appserver_process(app, @app_info_map[app]['nginx'],
            @app_info_map[app]['nginx_https'], @app_info_map[app]['language'])
          Djinn.log_debug("add_appserver_process returned: #{ret}.")
        elsif !to_start[0].nil?
          app = to_start[0]
          Djinn.log_info("Starting AppServer for app: #{app}.")
          ret = add_appserver_process(app, @app_info_map[app]['nginx'],
            @app_info_map[app]['nginx_https'], @app_info_map[app]['language'])
          Djinn.log_debug("add_appserver_process returned: #{ret}.")
        elsif !to_end[0].nil?
          Djinn.log_info("Terminate the following AppServer: #{to_end[0]}.")
          app, port = to_end[0].split(":")
          ret = remove_appserver_process(app, port)
          @unaccounted.delete(to_end[0])
          Djinn.log_debug("remove_appserver_process returned: #{ret}.")
        end
      }
    }
  end

  # This functions returns the language of the application as recorded in
  # the metadata.
  # Args
  #   app: A String naming the application.
  # Returns:
  #   language: returns python27, java, php or go depending on the
  #       language of the app
  def get_app_language(app)
    app_language = ""

    # Let's get the application language as we have in the metadata (this
    # will be the latest from the user).
    uac = UserAppClient.new(my_node.private_ip, @@secret)
    loop {
      begin
        result = uac.get_app_data(app)
        app_data = JSON.load(result)
        Djinn.log_debug("Got application data for #{app}: #{app_data}.")

        # Let's make sure the application is enabled.
        result = uac.enable_app(app)
        Djinn.log_debug("enable_app returned #{result}.")
        app_language = app_data['language']
        break
      rescue FailedNodeException
        # Failed to talk to the UserAppServer: let's try again.
        Djinn.log_debug("Failed to talk to UserAppServer for #{app}.")
      end
      Djinn.log_info("Waiting for app data to have instance info for app named #{app}")
      Kernel.sleep(SMALL_WAIT)
    }

    return app_language
  end

  # Small utility function that returns the full path for the rsyslog
  # configuration for each application.
  #
  # Args:
  #   app: A String containing the application ID.
  # Returns:
  #   path: A String with the path to the rsyslog configuration file.
  def get_rsyslog_conf(app)
    return "/etc/rsyslog.d/10-#{app}.conf"
  end

  # Performs all of the preprocessing needed to start an App Engine application
  # on this node. This method then starts the actual app by calling the AppManager.
  #
  # Args:
  #   app: A String containing the appid for the app to start.
  def setup_appengine_application(app)
    @state = "Setting up AppServers for #{app}"
    Djinn.log_debug("setup_appengine_application: got a new app #{app}.")

    # Let's create an entry for the application if we don't already have it.
    @app_info_map[app] = {} if @app_info_map[app].nil?
    @app_info_map[app]['language'] = get_app_language(app)

    # Use already assigned ports, or otherwise assign new ports to the
    # application.
    if @app_info_map[app]['nginx'].nil?
      @app_info_map[app]['nginx'] = find_lowest_free_port(
        Nginx::START_PORT, Nginx::END_PORT)
    end
    if @app_info_map[app]['nginx_https'].nil?
      @app_info_map[app]['nginx_https'] = find_lowest_free_port(
        Nginx.get_ssl_port_for_app(Nginx::START_PORT),
        Nginx.get_ssl_port_for_app(Nginx::END_PORT))
    end
    if @app_info_map[app]['haproxy'].nil?
      @app_info_map[app]['haproxy'] = find_lowest_free_port(
        HAProxy::START_PORT)
    end
    if @app_info_map[app]['appengine'].nil?
      @app_info_map[app]['appengine'] = []
    end
    if !@app_info_map[app]['nginx'] or
        !@app_info_map[app]['nginx_https'] or
        !@app_info_map[app]['haproxy']
      # Free possibly allocated ports and return an error if we couldn't
      # get all ports.
      @app_info_map[app]['nginx'] = nil
      @app_info_map[app]['nginx_https'] = nil
      @app_info_map[app]['haproxy'] = nil
      Djinn.log_error("Cannot find an available port for application #{app}")
      return
    end
    Djinn.log_debug("setup_appengine_application: info for #{app}: #{@app_info_map[app]}.")

    nginx_port = @app_info_map[app]['nginx']
    https_port = @app_info_map[app]['nginx_https']
    proxy_port = @app_info_map[app]['haproxy']

    port_file = "#{APPSCALE_CONFIG_DIR}/port-#{app}.txt"
    HelperFunctions.write_file(port_file, "#{@app_info_map[app]['nginx']}")
    Djinn.log_debug("App #{app} will be using nginx port #{nginx_port}, " +
      "https port #{https_port}, and haproxy port #{proxy_port}")

    # Setup rsyslog to store application logs.
    app_log_config_file = get_rsyslog_conf(app)
    begin
      existing_app_log_config = File.open(app_log_config_file, 'r').read()
    rescue Errno::ENOENT
      existing_app_log_config = ''
    end
    app_log_template = HelperFunctions.read_file(RSYSLOG_TEMPLATE_LOCATION)
    app_log_config = app_log_template.gsub("{0}", app)
    unless existing_app_log_config == app_log_config
      Djinn.log_info("Installing log configuration for #{app}.")
      HelperFunctions.write_file(app_log_config_file, app_log_config)
      HelperFunctions.shell("service rsyslog restart")
    end
    begin
      start_xmpp_for_app(app, nginx_port, @app_info_map[app]['language'])
    rescue FailedNodeException
      Djinn.log_warn("Failed to start xmpp for application #{app}")
    end

    @apps_loaded << app unless @apps_loaded.include?(app)
  end


  # Finds the lowest numbered port that is free to serve a new process.
  #
  # Callers should make sure to store the port returned by this process in
  # @app_info_map, preferably within the use of the APPS_LOCK (so that a
  # different caller doesn't get the same value).
  #
  # Args:
  #   starting_port: we look for ports starting from this port.
  #   ending_port:   we look up to this port, if 0, we keep going.
  #   appid:         if ports are used by this app, we ignore them, if
  #                  nil we check all the applications ports.
  #
  # Returns:
  #   A Fixnum corresponding to the port number that a new process can be bound
  #   to.
  def find_lowest_free_port(starting_port, ending_port=0, appid="")
    possibly_free_port = starting_port
    loop {
      # If we have ending_port, we need to check the upper limit too.
      break if ending_port > 0 and possibly_free_port > ending_port

      # Make sure the port is not already allocated to any application.
      # This is important when applications start at the same time since
      # there can be a race condition allocating ports.
      in_use = false
      @app_info_map.each { |app, info|
        # If appid is defined, let's ignore its ports.
        next if app == appid

        # Make sure we have the variables to look into: if we catch an app
        # early on, it may not have them.
        %w(nginx nginx_https haproxy).each { |key|
          next unless info[key]
          begin
            in_use = true if possibly_free_port == Integer(info[key])
          rescue ArgumentError
            next
          end
        }

        # These ports are allocated on the AppServers nodes.
        if info['appengine']
          info['appengine'].each { |location|
            _, port = location.split(":")
            in_use = true if possibly_free_port == Integer(port)
          }
        end

        break if in_use
      }

      # Check if the port is really available.
      unless in_use
        actually_available = Djinn.log_run("lsof -i:#{possibly_free_port} -sTCP:LISTEN")
        if actually_available.empty?
          Djinn.log_debug("Port #{possibly_free_port} is available for use.")
          return possibly_free_port
        end
      end

      # Let's try the next available port.
      Djinn.log_debug("Port #{possibly_free_port} is in use, so skipping it.")
      possibly_free_port += 1
    }
    return -1
  end


  # Adds or removes AppServers within a node based on the number of requests
  # that each application has received as well as the number of requests that
  # are sitting in haproxy's queue, waiting to be served.
  def scale_appservers_within_nodes
    @apps_loaded.each { |app_name|
      initialize_scaling_info_for_app(app_name)

      # Get the desired changes in the number of AppServers.
      delta_appservers = get_scaling_info_for_app(app_name)
      if delta_appservers > 0
        Djinn.log_debug("Considering scaling up app #{app_name}.")
        try_to_scale_up(app_name, delta_appservers)
      elsif delta_appservers < 0
        Djinn.log_debug("Considering scaling down app #{app_name}.")
        try_to_scale_down(app_name, delta_appservers.abs)
      else
        Djinn.log_debug("Not scaling app #{app_name} up or down right now.")
      end
    }
  end


  # Sets up information about the request rate and number of requests in
  # haproxy's queue for the given application.
  #
  # Args:
  #   app_name: The name of the application to set up scaling info
  #   force: A boolean value that indicates if we should reset the scaling
  #     info even in the presence of existing scaling info.
  def initialize_scaling_info_for_app(app_name, force=false)
    return if @initialized_apps[app_name] and !force

    @current_req_rate[app_name] = 0
    @total_req_rate[app_name] = 0
    @last_sampling_time[app_name] = Time.now.to_i
    (@last_decision[app_name] = 0) unless @last_decision.has_key?(app_name)
    @initialized_apps[app_name] = true
  end


  # Queries haproxy to see how many requests are queued for a given application
  # and how many requests are served at a given time.
  # Args:
  #   app_name: The name of the application to get info for.
  #   update_dashboard: Indicates if we should sent the info to the
  #     dashboard.
  # Returns:
  #   an Integer: the number of AppServers desired (a positive number
  #     means we want more, a negative that we want to remove some, and 0
  #     for no changes).
  def get_scaling_info_for_app(app_name, update_dashboard=true)
    if @app_info_map[app_name].nil? || !@app_names.include?(app_name)
      Djinn.log_info("Not scaling app #{app_name}, since we aren't " +
        "hosting it anymore.")
      return 0
    end

    # Let's make sure we have the minimum number of AppServers running.
    Djinn.log_debug("Evaluating app #{app_name} for scaling.")
    if @app_info_map[app_name]['appengine'].nil?
      num_appengines = 0
    else
      num_appengines = @app_info_map[app_name]['appengine'].length
    end
    min = @app_info_map[app_name]['min_appengines']
    min = Integer(@options['appengine']) if min.nil?
    if num_appengines < min
      Djinn.log_info("#{app_name} needs #{min - num_appengines} more AppServers.")
      @last_decision[app_name] = 0
      return min - num_appengines
    end

    # We only run @options['appengine'] AppServers per application if
    # austoscale is disabled.
    return 0 if @options['autoscale'].downcase != "true"

    # We need the haproxy stats to decide upon what to do.
    total_requests_seen, total_req_in_queue, time_requests_were_seen =
      HAProxy.get_haproxy_stats(app_name)

    if time_requests_were_seen == :no_backend
      Djinn.log_warn("Didn't see any request data - not sure whether to scale up or down.")
      return 0
    end

    update_request_info(app_name, total_requests_seen, time_requests_were_seen,
      total_req_in_queue, update_dashboard)

    if total_req_in_queue.zero?
      if Time.now.to_i - @last_decision[app_name] < SCALEDOWN_THRESHOLD * DUTY_CYCLE
        Djinn.log_debug("Not enough time as passed to scale down app #{app_name}")
        return 0
      end
      Djinn.log_debug("No requests are enqueued for app #{app_name} - " +
        "advising that we scale down within this machine.")
      return -1
    end

    if total_req_in_queue > SCALEUP_QUEUE_SIZE_THRESHOLD
      if Time.now.to_i - @last_decision[app_name] < SCALEUP_THRESHOLD * DUTY_CYCLE
        Djinn.log_debug("Not enough time as passed to scale up app #{app_name}")
        return 0
      end
      Djinn.log_debug("#{total_req_in_queue} requests are enqueued for app " +
        "#{app_name} - advising that we scale up within this machine.")
      return Integer(total_req_in_queue / SCALEUP_QUEUE_SIZE_THRESHOLD)
    end

    Djinn.log_debug("#{total_req_in_queue} requests are enqueued for app " +
      "#{app_name} - advising that don't scale either way on this machine.")
    return 0
  end


  # Updates internal state about the number of requests seen for the given App
  # Engine app, as well as how many requests are currently enqueued for it.
  # Some of this information is also sent to the AppDashboard for viewing by
  # users.
  #
  # Args:
  #   app_name: A String that indicates the name this Google App Engine
  #     application is registered as.
  #   total_requests_seen: An Integer that indicates how many requests haproxy
  #     has received for the given application since we reloaded it (which
  #     occurs when we start the app or add/remove AppServers).
  #   time_requests_were_seen: An Integer that represents the epoch time when we
  #     got request info from haproxy.
  #   total_req_in_queue: An Integer that represents the current number of
  #     requests waiting to be served.
  #   update_dashboard: A boolean to indicate if we send the information
  #     to the dashboard.
  def update_request_info(app_name, total_requests_seen,
    time_requests_were_seen, total_req_in_queue,  update_dashboard)
    Djinn.log_debug("Time now is #{time_requests_were_seen}, last " +
      "time was #{@last_sampling_time[app_name]}")
    Djinn.log_debug("Total requests seen now is #{total_requests_seen}, last " +
      "time was #{@total_req_rate[app_name]}")
    Djinn.log_debug("Requests currently in the queue #{total_req_in_queue}")
    requests_since_last_sampling = total_requests_seen - @total_req_rate[app_name]
    time_since_last_sampling = time_requests_were_seen - @last_sampling_time[app_name]
    if time_since_last_sampling.zero?
      time_since_last_sampling = 1
    end

    average_request_rate = Float(requests_since_last_sampling) / Float(time_since_last_sampling)
    if average_request_rate < 0
      Djinn.log_info("Saw negative request rate for app #{app_name}, so " +
        "resetting our haproxy stats for this app.")
      initialize_scaling_info_for_app(app_name, true)
      return
    end

    if update_dashboard
      send_request_info_to_dashboard(app_name, time_requests_were_seen,
        average_request_rate)
    end

    Djinn.log_debug("Total requests will be set to #{total_requests_seen} " +
      "for app #{app_name}, with last sampling time #{time_requests_were_seen}")
    @current_req_rate[app_name] = total_req_in_queue
    @total_req_rate[app_name] = total_requests_seen
    @last_sampling_time[app_name] = time_requests_were_seen
  end


  # Try to add an AppServer for the specified application, ensuring
  # that a minimum number of AppServers is always kept.
  #
  # Args:
  #   app_name: A String containing the application ID.
  #   delta_appservers: The desired number of new AppServers.
  # Returns:
  #   A boolean indicating if a new AppServer was requested.
  def try_to_scale_up(app_name, delta_appservers)
    # Select an appengine machine if it has enough resources to support
    # another AppServer for this app.
    available_hosts = []

    # We count now the number of AppServers running on each node: we will
    # need to consider the maximum amount of memory allocated to it, in
    # order to not overprovision the appengine node.
    appservers_count = {}
    current_hosts = Set.new()
    max_memory = {}
    @app_info_map.each_pair { |appid, app_info|
      next if app_info['appengine'].nil?

      # We need to keep track of the theoretical max memory used by all
      # the AppServervers.
      max_app_mem = @app_info_map[appid]['max_memory']
      max_app_mem = Integer(@options['max_memory']) if max_app_mem.nil?

      app_info['appengine'].each { |location|
        host, port = location.split(":")
        if appservers_count[host].nil?
          appservers_count[host] = 1
          max_memory[host] = max_app_mem
        else
          appservers_count[host] += 1
          max_memory[host] += max_app_mem
        end

        # We also see which host is running the application we need to
        # scale. We will need later on to prefer hosts not running this
        # app.
        current_hosts << host if app_name == appid
      }
    }

    # Get the memory limit for this application.
    max_app_mem = @app_info_map[app_name]['max_memory']
    max_app_mem = Integer(@options['max_memory']) if max_app_mem.nil?

    # Let's consider the last system load readings we have, to see if the
    # node can run another AppServer.
    get_all_appengine_nodes.each { |host|
      @all_stats.each { |node|
        next if node['private_ip'] != host

        # TODO: this is a temporary fix waiting for when we phase in
        # get_all_stats. Since we don't have the total memory, we
        # reconstruct it here.
        total = (Float(node['free_memory'])*100)/(100-Float(node['memory']))

        # Check how many new AppServers of this app, we can run on this
        # node (as theoretical maximum memory usage goes).
        max_memory[host] = 0 if max_memory[host].nil?
        max_new_total = Integer((total - max_memory[host] - SAFE_MEM)/ max_app_mem)
        Djinn.log_debug("Check for total memory usage: #{host} can run #{max_new_total}" +
          " AppServers for #{app_name}.")
        break if max_new_total <= 0

        # Now we do a similar calculation but for the current amount of
        # free memory on this node.
        host_free_mem = Integer(node['free_memory'])
        max_new_free = Integer((host_free_mem - SAFE_MEM) / max_app_mem)
        Djinn.log_debug("Check for free memory usage: #{host} can run #{max_new_free}" +
          " AppServers for #{app_name}.")
        break if max_new_free <= 0

        # The host needs to have normalized average load less than
        # MAX_LOAD_AVG, current CPU usage less than 90%.
        if Float(node['cpu']) > MAX_CPU_FOR_APPSERVERS ||
            Float(node['load']) / Float(node['num_cpu']) > MAX_LOAD_AVG
          Djinn.log_debug("#{host} CPUs are too busy.")
          break
        end

        # We add the host as many times as AppServers it can run.
        (max_new_total > max_new_free ? max_new_free : max_new_total).downto(1) {
          available_hosts << host
        }

        # Since we already found the stats for this node, no need to look
        # further.
        break
      }
    }
    Djinn.log_debug("Hosts available to scale #{app_name}: #{available_hosts}.")

    # If we're this far, no room is available for AppServers, so try to
    # add a new node instead.
    if available_hosts.empty?
      Djinn.log_info("No AppServer available to scale #{app_name}")
      ZKInterface.request_scale_up_for_app(app_name, my_node.private_ip)
      return false
    end

    # Since we may have 'clumps' of the same host (say a very big
    # appengine machine) we shuffle the list of candidate here.
    available_hosts.shuffle!

    # We prefer candidate that are not already running the application, so
    # ensure redundancy for the application.
    delta_appservers.downto(1) {
      appserver_to_use = nil
      available_hosts.each { |host|
        unless current_hosts.include?(host)
          Djinn.log_debug("Prioritizing #{host} to run #{app_name} " +
              "since it has no running AppServers for it.")
          appserver_to_use = host
          current_hosts << host
          break
        end
      }

      # If we haven't decided on a host yet, we pick one at random, then
      # we remove it from the list to ensure we don't go over the
      # requirements.
      appserver_to_use = available_hosts.sample if appserver_to_use.nil?
      available_hosts.delete_at(available_hosts.index(appserver_to_use))

      Djinn.log_info("Adding a new AppServer on #{appserver_to_use} for #{app_name}.")
      @app_info_map[app_name]['appengine'] << "#{appserver_to_use}:-1"

      # If we ran our of available hosts, we'll have to wait for the
      # next cycle to add more AppServers.
      break if available_hosts.empty?
    }
    @last_decision[app_name] = Time.now.to_i
    return true
  end


  # Try to remove an AppServer for the specified application, ensuring
  # that a minimum number of AppServers is always kept.
  #
  # Args:
  #   app_name: A String containing the application ID.
  #   delta_appservers: The desired number of AppServers to remove.
  # Returns:
  #   A boolean indicating if an AppServer was removed.
  def try_to_scale_down(app_name, _delta_appservers)
    # See how many AppServers are running on each machine. We cannot scale
    # if we already are at the requested minimum.
    min = @app_info_map[app_name]['min_appengines']
    min = Integer(@options['appengine']) if min.nil?
    if @app_info_map[app_name]['appengine'].length <= min
      Djinn.log_debug("We are already at the minimum number of AppServers for " +
        "#{app_name}: requesting to remove node.")

      # If we're this far, nobody can scale down, so try to remove a node instead.
      ZKInterface.request_scale_down_for_app(app_name, my_node.private_ip)
      return false
    end

    # We pick a randon appengine that run the application.  Smarter
    # algorithms could be implemented, but without clear directives (ie
    # decide on cpu, or memory, or number of CPU available, or avg load
    # etc...) any static strategy is flawed, so we go for simplicity.
    scapegoat = @app_info_map[app_name]['appengine'].sample()
    appserver_to_use, port = scapegoat.split(":")
    Djinn.log_info("Removing an AppServer from #{appserver_to_use} for #{app_name}")

    @app_info_map[app_name]['appengine'].delete("#{appserver_to_use}:#{port}")
    @last_decision[app_name] = Time.now.to_i
    return true
  end

  # This function unpacks an application tarball if needed. A removal of
  # the old application code can be forced with a parameter.
  #
  # Args:
  #   app       : the application name to setup
  #   remove_old: boolean to force a re-setup of the app from the tarball
  def setup_app_dir(app, remove_old=false)
    app_dir = "#{HelperFunctions.get_app_path(app)}/app"
    app_path = "#{PERSISTENT_MOUNT_POINT}/apps/#{app}.tar.gz"
    error_msg = ""

    if remove_old
      Djinn.log_info("Removing old application version for app: #{app}.")
      if my_node.is_shadow?
        # Force the shadow node to refresh the application directory.
        FileUtils.rm_rf(app_dir)
      else
        FileUtils.rm_rf(app_path)
        not_hosting_app(app, app_path, @@secret)
      end
    end

    # Let's make sure we have a copy of the tarball of the application. If
    # not, we will get the latest version from another node.
    FileUtils.rm_rf(app_dir) unless File.exists?(app_path)

    unless File.directory?(app_dir)
      Djinn.log_info("App untar directory created from scratch.")
      FileUtils.mkdir_p(app_dir)

      # Let's make sure we have a copy of the application locally.
      if copy_app_to_local(app)
        # Let's make sure their app has an app.yaml or appengine-web.xml in it,
        # since the following code assumes it is present. If it is not there
        # (which can happen if the scp fails on a large app), throw up a dummy
        # app.
        unless HelperFunctions.app_has_config_file?(app_path)
          error_msg = "ERROR: No app.yaml or appengine-web.xml for app: #{app}."
        else
          # Application is good: let's set it up.
          begin
            HelperFunctions.setup_app(app)
            done_uploading(app, app_path, @@secret)
          rescue AppScaleException => exception
            error_msg = "ERROR: couldn't setup source for #{app} " +
              "(#{exception.message})."
          end
        end
      else
        # If we couldn't get a copy of the application, place a dummy error
        # application to inform the user we had issues.
        error_msg = "ERROR: Failed to copy app: #{app}."
      end
    end

    unless error_msg.empty?
      # Something went wrong: place the error applcation instead.
      place_error_app(app, error_msg, get_app_language(app))
    end
  end


  # Starts a new AppServer for the given application.
  #
  # Args:
  #   app: A String naming the application that an additional instance will
  #     be added for.
  #   nginx_port: A String or Fixnum that names the port that should be used to
  #     serve HTTP traffic for this app.
  #   https_port: A String or Fixnum that names the port that should be used to
  #     serve HTTPS traffic for this app.
  #   app_language: A String naming the language of the application.
  # Returns:
  #   A Boolean to indicate if the AppServer was successfully started.
  def add_appserver_process(app, nginx_port, https_port, app_language)
    Djinn.log_info("Received request to add an AppServer for #{app}.")

    # Make sure we have the application setup properly.
    APPS_LOCK.synchronize {
      setup_app_dir(app)
    }

    # Wait for the head node to be setup for this app.
    port_file = "#{APPSCALE_CONFIG_DIR}/port-#{app}.txt"
    HelperFunctions.write_file(port_file, "#{nginx_port}")
    Djinn.log_info("Using NGINX port #{nginx_port} for #{app}.")

    appengine_port = find_lowest_free_port(STARTING_APPENGINE_PORT)
    if appengine_port < 0
      Djinn.log_error("Failed to get port for application #{app} on " +
        "#{@my_private_ip}")
      return false
    end
    Djinn.log_info("Starting #{app_language} app #{app} on " +
      "#{@my_private_ip}:#{appengine_port}")

    xmpp_ip = @options['login']

    app_manager = AppManagerClient.new(my_node.private_ip)
    begin
      max_app_mem = @app_info_map[app]['max_memory']
      max_app_mem = Integer(@options['max_memory']) if max_app_mem.nil?
      pid = app_manager.start_app(app, appengine_port,
        get_load_balancer.public_ip, app_language, xmpp_ip,
        HelperFunctions.get_app_env_vars(app), max_app_mem,
        get_shadow.private_ip)
    rescue FailedNodeException, AppScaleException, ArgumentError => error
      Djinn.log_warn("#{error.class} encountered while starting #{app} "\
        "with AppManager: #{error.message}")
      pid = -1
    end
    if pid < 0
      # Something may have gone wrong: inform the user and move on.
      Djinn.log_warn("Something went wrong starting AppServer for" +
        " #{app}: check logs and running processes as duplicate" +
        " ports may have been allocated.")
    end
    Djinn.log_info("Done adding AppServer for #{app}.")
    return true
  end


  # Terminates a specific AppServer (determined by the listening port)
  # that hosts the specified App Engine app.
  #
  # Args:
  #   app_id: A String naming the application that a process will be removed
  #     from.
  #   port: A Fixnum that names the port of the AppServer to remove.
  #   secret: A String that is used to authenticate the caller.
  # Returns:
  #   A Boolean indicating the success of the operation.
  def remove_appserver_process(app_id, port)
    @state = "Stopping an AppServer to free unused resources"
    Djinn.log_debug("Deleting AppServer instance to free up unused resources")

    uac = UserAppClient.new(my_node.private_ip, @@secret)
    app_manager = AppManagerClient.new(my_node.private_ip)

    begin
      app_is_enabled = uac.is_app_enabled?(app_id)
    rescue FailedNodeException
      Djinn.log_warn("Failed to talk to the UserAppServer about " +
        "application #{app_id}")
      return false
    end
    Djinn.log_debug("is app #{app_id} enabled? #{app_is_enabled}")
    if app_is_enabled == "false"
      return false
    end

    begin
      result = app_manager.stop_app_instance(app_id, port)
    rescue FailedNodeException
      Djinn.log_error("Unable to talk to the UserAppServer " +
        "stop instance on port #{port} for application #{app_id}.")
      result = false
    end
    unless result
      Djinn.log_error("Unable to stop instance on port #{port} " +
        "application #{app_id}")
    end

    return true
  end


  # Tells the AppDashboard how many requests were served for the named
  # application at the given time, so that it can display this info to users
  # graphically.
  #
  # Args:
  #   app_id: A String that indicates which application id we are storing
  #     request info for.
  #   timestamp: An Integer that indicates the epoch time when we measured the
  #     request rate for the given application.
  #   request_rate: An Integer that indicates how many requests were served for
  #     the given application in the last second since we queried it.
  # Returns:
  #   true if the request info was successfully sent, and false otherwise.
  def send_request_info_to_dashboard(app_id, timestamp, request_rate)
    Djinn.log_debug("Sending a log with request rate #{app_id}, timestamp " +
      "#{timestamp}, request rate #{request_rate}")
    encoded_request_info = JSON.dump({
      'timestamp' => timestamp,
      'request_rate' => request_rate
    })

    begin
      url = URI.parse("https://#{get_shadow.private_ip}:" +
        "#{AppDashboard::LISTEN_SSL_PORT}/apps/json/#{app_id}")
      http = Net::HTTP.new(url.host, url.port)
      http.use_ssl = true
      http.verify_mode = OpenSSL::SSL::VERIFY_NONE
      response = http.post(url.path, encoded_request_info,
        {'Content-Type'=>'application/json'})
      return true
    rescue OpenSSL::SSL::SSLError, NotImplementedError, Errno::EPIPE,
      Errno::ECONNRESET => e
      backtrace = e.backtrace.join("\n")
      Djinn.log_warn("Error sending logs: #{e.message}\n#{backtrace}")
      retry
    rescue
      # Don't crash the AppController because we weren't able to send over
      # the request info - just inform the caller that we couldn't send it.
      Djinn.log_info("Couldn't send request info for app #{app_id} to #{url}")
      return false
    end
  end


  # It checks if we need to add or remove App Engine nodes to this deployment.
  #
  # Returns:
  #   An Integer with the number of nodes changed (positive we added
  #     nodes, negative we removed them, 0 if we didn't do anything).
  def scale_appservers_across_nodes()
    # Only the shadow makes scaling decisions.
    return unless my_node.is_shadow?

    Djinn.log_debug("Seeing if we need to spawn new AppServer nodes")

    nodes_needed = []
    all_scaling_requests = {}
    @apps_loaded.each { |appid|
      begin
        scaling_requests = ZKInterface.get_scaling_requests_for_app(appid)
        all_scaling_requests[appid] = scaling_requests
        ZKInterface.clear_scaling_requests_for_app(appid)
      rescue FailedZooKeeperOperationException => e
        Djinn.log_warn("(scale_appservers_across_nodes) issues talking " +
          "to zookeeper with #{e.message}.")
        next
      end
      scale_up_requests = scaling_requests.select { |item| item == "scale_up" }
      num_of_scale_up_requests = scale_up_requests.length

      if num_of_scale_up_requests > 0
        Djinn.log_debug("#{appid} requires more AppServers: adding a node.")
        nodes_needed << ["appengine"]
      end
    }

    if nodes_needed.empty?
      Djinn.log_debug("Not adding any new AppServers at this time. Checking " +
        "to see if we need to scale down.")
      return examine_scale_down_requests(all_scaling_requests)
    end

    if Time.now.to_i - @last_scaling_time < (SCALEUP_THRESHOLD *
            SCALE_TIME_MULTIPLIER * DUTY_CYCLE)
      Djinn.log_info("Not scaling up right now, as we recently scaled " +
        "up or down.")
      return 0
    end

    Djinn.log_info("Need to spawn #{nodes_needed.length} new AppServers.")
    added_nodes = start_new_roles_on_nodes(nodes_needed,
      @options['instance_type'], @@secret)

    if added_nodes != "OK"
      Djinn.log_error("Was not able to add #{nodes_needed.length} new nodes" +
        " because: #{added_nodes}")
      return 0
    end

    @last_scaling_time = Time.now.to_i
    Djinn.log_info("Added the following nodes: #{nodes_needed}.")
    return nodes_needed.length
  end


  # Searches through the requests to scale up and down each application in this
  # AppScale deployment, and determines if machines need to be terminated due
  # to excess capacity.
  #
  # Args:
  #   all_scaling_votes: A Hash that maps each appid (a String) to the votes
  #     received to scale the app up or down (an Array of Strings).
  # Returns:
  #   An Integer that indicates how many nodes were added to this AppScale
  #   deployment. A negative number indicates that that many nodes were
  #   removed from this AppScale deployment.
  def examine_scale_down_requests(all_scaling_votes)
    # First, only scale down in cloud environments.
    unless is_cloud?
      Djinn.log_debug("Not scaling down VMs, because we aren't in a cloud.")
      return 0
    end

    if @nodes.length <= Integer(@options['min_images']) or @nodes.length <= 1
      Djinn.log_debug("Not scaling down VMs right now, as we are at the " +
        "minimum number of nodes the user wants to use.")
      return 0
    end

    # Second, only consider scaling down if nobody wants to scale up.
    @apps_loaded.each { |appid|
      scale_ups = all_scaling_votes[appid].select { |vote| vote == "scale_up" }
      if scale_ups.length > 0
        Djinn.log_debug("Not scaling down VMs, because app #{appid} wants to scale" +
          " up.")
        return 0
      end
    }

    # Third, only consider scaling down if we get two votes to scale down on
    # the same app, just like we do for scaling up.
    scale_down_threshold_reached = false
    @apps_loaded.each { |appid|
      scale_downs = all_scaling_votes[appid].select { |vote| vote == "scale_down" }
      if scale_downs.length > 0
        Djinn.log_info("Got a vote to scale down app #{appid}, so " +
          "considering removing VMs.")
        scale_down_threshold_reached = true
      end
    }

    unless scale_down_threshold_reached
      Djinn.log_debug("Not scaling down VMs right now, as not enough nodes have " +
        "requested it.")
      return 0
    end

    # Also, don't scale down if we just scaled up or down.
    if Time.now.to_i - @last_scaling_time < (SCALEDOWN_THRESHOLD *
            SCALE_TIME_MULTIPLIER * DUTY_CYCLE)
      Djinn.log_info("Not scaling down VMs right now, as we recently scaled " +
        "up or down.")
      return 0
    end

    # Finally, find a node to remove and remove it.
    node_to_remove = nil
    @nodes.each { |node|
      if node.jobs == ["appengine"]
        Djinn.log_info("Removing node #{node}")
        node_to_remove = node
        break
      end
    }

    if node_to_remove.nil?
      Djinn.log_warn("Tried to scale down but couldn't find a node to remove.")
      return 0
    end

    remove_node_from_local_and_zookeeper(node_to_remove.private_ip)

    to_remove = {}
    @app_info_map.each { |app_id, info|
      next if info['appengine'].nil?

      info['appengine'].each { |location|
        host, port = location.split(":")
        if host == node_to_remove.private_ip
          to_remove[app] = [] if to_remove[app].nil?
          to_remove[app] << location
        end
      }
    }
    to_remove.each { |app, locations|
        locations.each { |location|
          @app_info_map[app]['appengine'].delete(location)
        }
    }

    imc = InfrastructureManagerClient.new(@@secret)
    begin
      imc.terminate_instances(@options, node_to_remove.instance_id)
    rescue FailedNodeException
      Djinn.log_warn("Failed to call terminate_instances")
    end

    @last_scaling_time = Time.now.to_i
    return -1
  end


  def stop_appengine()
    Djinn.log_info("Shutting down AppEngine")

    erase_app_instance_info()
    Nginx.reload()

    APPS_LOCK.synchronize {
      @app_names = []
      @apps_loaded = []
    }
  end

  # Returns true on success, false otherwise
  def copy_app_to_local(appname)
    app_path = "#{PERSISTENT_MOUNT_POINT}/apps/#{appname}.tar.gz"

    if File.exists?(app_path)
      Djinn.log_debug("I already have a copy of app #{appname} - won't grab it remotely")
      return true
    else
      Djinn.log_debug("I don't have a copy of app #{appname} - will grab it remotely")
    end

    nodes_with_app = []
    RETRIES.downto(0) { |attempt|
      nodes_with_app = ZKInterface.get_app_hosters(appname, @options['keyname'])
      if nodes_with_app.empty?
        Djinn.log_info("#{attempt} attempt: waiting for a node to " +
          "have a copy of app #{appname}")
        Kernel.sleep(SMALL_WAIT)
        next
      end

      # Try few times on each node known to retrieve this application. Make
      # sure we pick a random order to not overload the same host.
      nodes_with_app.shuffle.each { |node|
        ssh_key = node.ssh_key
        ip = node.private_ip
        Djinn.log_debug("Trying #{ip}:#{app_path} for the application.")
        RETRIES.downto(0) {
          begin
            HelperFunctions.scp_file(app_path, app_path, ip, ssh_key, true)
            if File.exists?(app_path)
              if HelperFunctions.check_tarball(app_path)
                Djinn.log_info("Got a copy of #{appname} from #{ip}.")
                return true
              end
            end
          rescue AppScaleSCPException
            Djinn.log_debug("Got scp issues getting a copy of #{app_path} from #{ip}.")
          end
          # Removing possibly corrupted, or partially downloaded tarball.
          FileUtils.rm_rf(app_path)
          Kernel.sleep(SMALL_WAIT)
        }
        Djinn.log_warn("Unable to get the application from #{ip}:#{app_path}: scp failed.")
      }
    }

    Djinn.log_error("Unable to get the application from any node.")
    return false
  end

  # This function creates the xmpp account for 'app', as app@login_ip.
  def start_xmpp_for_app(app, port, app_language)
    watch_name = "xmpp-#{app}"

    # If we have it already running, nothing to do
    if MonitInterface.is_running?(watch_name)
      Djinn.log_debug("xmpp already running for application #{app}")
      return
    end

    # We don't need to check for FailedNodeException here since we catch
    # it at a higher level.
    login_ip = @options['login']
    uac = UserAppClient.new(my_node.private_ip, @@secret)
    xmpp_user = "#{app}@#{login_ip}"
    xmpp_pass = HelperFunctions.encrypt_password(xmpp_user, @@secret)
    result = uac.commit_new_user(xmpp_user, xmpp_pass, "app")
    Djinn.log_debug("User creation returned: #{result}")
    if result.include?('Error: user already exists')
      # We need to update the password of the channel XMPP account for
      # authorization.
      result = uac.change_password(xmpp_user, xmpp_pass)
      Djinn.log_debug("Change password returned: #{result}")
    end

    Djinn.log_debug("Created user [#{xmpp_user}] with password [#{@@secret}] and hashed password [#{xmpp_pass}]")

    if Ejabberd.does_app_need_receive?(app, app_language)
      start_cmd = "#{PYTHON27} #{APPSCALE_HOME}/XMPPReceiver/xmpp_receiver.py #{app} #{login_ip} #{@@secret}"
      stop_cmd = "#{PYTHON27} #{APPSCALE_HOME}/scripts/stop_service.py " +
        "xmpp_receiver.py #{app}"
      MonitInterface.start(watch_name, start_cmd, stop_cmd, [9999], nil,
                           start_cmd, nil, nil, nil)
      Djinn.log_debug("App #{app} does need xmpp receive functionality")
    else
      Djinn.log_debug("App #{app} does not need xmpp receive functionality")
    end
  end

  # Stop the xmpp receiver for an application.
  #
  # Args:
  #   app: The application ID whose XMPPReceiver we should shut down.
  def stop_xmpp_for_app(app)
    Djinn.log_info("Shutting down xmpp receiver for app: #{app}")
    MonitInterface.stop("xmpp-#{app}")
    Djinn.log_info("Done shutting down xmpp receiver for app: #{app}")
  end

  def start_open()
    return
  end

  def stop_open()
    return
  end

  # Gathers App Controller and System Manager stats for this node.
  #
  # Args:
  #   secret: The secret of this deployment.
  # Returns:
  #   A hash in string format containing system and platform stats for this
  #     node.
  def get_all_stats(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    # Get stats from SystemManager.
    imc = InfrastructureManagerClient.new(secret)
    system_stats = imc.get_system_stats()
    Djinn.log_debug("System stats: #{system_stats}")

    # Combine all useful stats and return.
    all_stats = system_stats
    all_stats["apps"] = {}
    if my_node.is_shadow?
      APPS_LOCK.synchronize {
        @apps_loaded.each { |app_name|
          if @app_info_map[app_name].nil? or @app_info_map[app_name]['appengine'].nil?
            Djinn.log_debug("#{app_name} not setup yet: skipping getting stats.")
            next
          end

          # Get HAProxy requests.
          Djinn.log_debug("Getting HAProxy stats for app: #{app_name}")
          total_reqs, reqs_enqueued, collection_time = HAProxy.get_haproxy_stats(app_name)
          # Create the apps hash with useful information containing HAProxy stats.
          begin
            appservers = 0
            pending = 0
            if collection_time == :no_backend
              total_reqs = 0
              reqs_enqueued = 0
            else

              @app_info_map[app_name]['appengine'].each { |location|
                host, port = location.split(":")
                if Integer(port) > 0
                  appservers += 1
                else
                  pending += 1
                end
              }
            end
            all_stats["apps"][app_name] = {
              "language" => @app_info_map[app_name]["language"].tr('^A-Za-z', ''),
              "appservers" => appservers,
              "pending_appservers" => pending,
              "http" => @app_info_map[app_name]["nginx"],
              "https" => @app_info_map[app_name]["nginx_https"],
              "total_reqs" => total_reqs,
              "reqs_enqueued" => reqs_enqueued
            }
          rescue => exception
            backtrace = exception.backtrace.join("\n")
            message = "Unforseen exception: #{exception} \nBacktrace: #{backtrace}"
            Djinn.log_warn("Unable to get application stats: #{message}")
          end
        }
      }
    end

    all_stats["public_ip"] = my_node.public_ip
    all_stats["private_ip"] = my_node.private_ip
    all_stats["roles"] = my_node.jobs or ["none"]
    Djinn.log_debug("All stats: #{all_stats}")

    return JSON.dump(all_stats)
  end


  # Gets an application cron info.
  #
  # Args:
  #   app_name: The application ID.
  #   secret: The secret of this deployment.
  # Returns:
  #   An application cron info
  def get_application_cron_info(app_name, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    content = CronHelper.get_application_cron_info(app_name)
    return JSON.dump(content)
  end
end
