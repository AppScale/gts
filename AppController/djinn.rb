#!/usr/bin/ruby -w

# Imports within Ruby's standard libraries
require 'digest'
require 'logger'
require 'monitor'
require 'net/http'
require 'net/https'
require 'open3'
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
$:.unshift File.join(File.dirname(__FILE__), 'lib')
require 'app_controller_client'
require 'blobstore'
require 'cron_helper'
require 'custom_exceptions'
require 'datastore_server'
require 'ejabberd'
require 'error_app'
require 'groomer_service'
require 'haproxy'
require 'helperfunctions'
require 'hermes_client'
require 'infrastructure_manager_client'
require 'monit_interface'
require 'nginx'
require 'search'
require 'taskqueue'
require 'terminate'
require 'user_app_client'
require 'zkinterface'
require 'zookeeper_helper'

# This ensure that exceptions in a thread are not ignored.
Thread.abort_on_exception=true

# By default don't trace remote commands execution.
NO_OUTPUT = false

# This lock makes it so that global variables related to apps are not updated
# concurrently, preventing race conditions.
APPS_LOCK = Monitor.new

# This lock is to ensure that only one thread is trying to start/stop
# applications.
AMS_LOCK = Mutex.new

# Prevents nodetool from being invoked concurrently.
NODETOOL_LOCK = Mutex.new

# This lock is to ensure that only one thread is trying to start/stop
# new nodes (it takes a long time to spawn a new VM).
SCALE_LOCK = Mutex.new

# The name of the user to be used with reserved applications.
APPSCALE_USER = 'appscale-user@local.appscale'.freeze

# The string that should be returned to the caller if they call a publicly
# exposed SOAP method but provide an incorrect secret.
BAD_SECRET_MSG = 'false: bad secret'.freeze

# The String that should be returned to callers if they attempt to add or remove
# AppServers from an HAProxy config file at a node where HAProxy is not running.
NO_HAPROXY_PRESENT = 'false: haproxy not running'.freeze

# The String that should be returned to callers if they attempt to add
# AppServers for an app that does not yet have nginx and haproxy set up.
NOT_READY = 'false: not ready yet'.freeze

# A response that indicates that the caller made an invalid request.
INVALID_REQUEST = 'false: invalid request'.freeze

# The maximum number of seconds that we should wait when deploying Google App
# Engine applications via the AppController.
APP_UPLOAD_TIMEOUT = 180

# TODO get rid of json version of zookeeper locations file
# The location on the local file system where we store information about
# where ZooKeeper servers are located, used to backup and restore
# AppController information.
ZK_LOCATIONS_JSON_FILE = '/etc/appscale/zookeeper_locations.json'.freeze

# The location on the local file system where we store information about
# where ZooKeeper servers are located.
ZK_LOCATIONS_FILE = '/etc/appscale/zookeeper_locations'.freeze

# The location of the logrotate scripts.
LOGROTATE_DIR = '/etc/logrotate.d'.freeze

# The /etc/hosts file.
ETC_HOSTS = '/etc/hosts'.freeze

# The name of the generic appscale centralized app logrotate script.
APPSCALE_APP_LOGROTATE = 'appscale-app-logrotate.conf'.freeze

# The location of the appscale-upload-app script from appscale-tools.
UPLOAD_APP_SCRIPT = `which appscale-upload-app`.chomp

# The location of the build cache.
APPSCALE_CACHE_DIR = '/var/cache/appscale'.freeze

# The domain that hosts packages for the build.
PACKAGE_MIRROR_DOMAIN = 's3.amazonaws.com'.freeze

# The location on the package mirror where the packages are stored.
PACKAGE_MIRROR_PATH = '/appscale-build'.freeze

# The highest load of the deployment we handle before trying to scale up.
MAX_LOAD_THRESHOLD = 0.9

# The desired load of the deployment to achieve after scaling up or down.
DESIRED_LOAD = 0.8

# The lowest load of the deployment to tolerate before trying to scale down.
MIN_LOAD_THRESHOLD = 0.7

# The exit code that indicates the data layout version is unexpected.
INVALID_VERSION_EXIT_CODE = 64

# Djinn (interchangeably known as 'the AppController') automatically
# configures and deploys all services for a single node. It relies on other
# Djinns or the AppScale Tools to tell it what services (roles) it should
# be hosting, and exposes these methods via a SOAP interface (as is provided
# in DjinnServer).
class Djinn
  # An Array of NodeInfo objects, each of which containing information about
  # a node in the currently running AppScale deployment.
  attr_accessor :nodes

  # A Hash containing all the parameters needed to configure any service
  # on any node. At a minimum, this is all the information from the AppScale
  # Tools, including information about database parameters and the roles
  # for all nodes.
  attr_accessor :options

  # An Array of Strings, each of which corresponding to the name of an App
  # Engine app that has been loaded on this node.
  attr_accessor :versions_loaded

  # A boolean that is used to let remote callers know when this AppController
  # is done initializing itself, but not necessarily done starting or
  # stopping roles.
  attr_accessor :done_initializing

  # A boolean that is used to let remote callers know when this AppController
  # is done starting all the services it is responsible for.
  attr_accessor :done_loading

  # The human-readable state that this AppController is in.
  attr_accessor :state

  # An Integer that indexes into @nodes, to return information about this node.
  attr_accessor :my_index

  # An Array that lists the CPU, disk, and memory usage of each machine in this
  # AppScale deployment. Used as a cache so that it does not need to be
  # generated in response to AppDashboard requests.
  # This Array can be fetched in JSON format by get_cluster_stats_json
  # server's method. Its structure is following
  # [
  #  {
  #    # System stats provided by infrustucture manager
  #    "cpu" => {
  #      "count" => 2,
  #      "idle" => 81.3,
  #      "system" => 13.2,
  #      "user" => 5.5
  #    },
  #    "partitions_dict" => [
  #      # For each partition
  #      {
  #        "/" => {
  #          "total" => 30965743616,
  #          "free" => 15482871808,
  #          "used" => 15482871808
  #        }
  #      },
  #      ...
  #    ],
  #    "memory => {
  #      "total" => 12365412865,
  #      "available" => 6472179712,
  #      "used" => 8186245120
  #    },
  #    "swap" => {
  #      "total" => 2097147904,
  #      "free" => 1210527744,
  #      "used" => 886620160
  #    },
  #    "services" => {
  #      # For each Process monitored by monit
  #      "cassandra" => "Running",
  #      ...
  #    },
  #    "loadavg" => {
  #      "last_1min" => 1.35,
  #      "last_5min" => 0.67,
  #      "last_15min" => 0.89,
  #    },
  #    # Node information provided by AppController itself
  #    "apps" => {
  #      # This hash is empty for non-shadow nodes
  #      "my_app" => {
  #        "language" => "python",
  #        "appservers" => 4,
  #        "pending_appservers" => 2,
  #        "http" => 8080,
  #        "https" => 4380,
  #        "reqs_enqueued" => 15,
  #        "total_reqs" => 6513
  #      },
  #      ...
  #    },
  #    "cloud" => False,
  #    "state" => "Done starting up AppScale, now in heartbeat mode",
  #    "db_location" => "192.168.33.10",
  #    "is_initialized" => True,
  #    "is_loaded" => True,
  #    "public_ip" => "192.168.33.10",
  #    "private_ip" => "10.10.105.18",
  #    "roles" => ["shadow", "zookeeper", "datastore", "taskqueue"],
  #  },
  #  ...
  # ]
  attr_accessor :cluster_stats

  # A Hash that contains information about each Google App Engine application
  # running in this deployment. It includes information about the nginx and
  # haproxy ports the app uses, as well as the language the app is written
  # in.
  attr_accessor :app_info_map

  # A lock that should be used whenever we modify internal state that can be
  # modified by more than one thread at a time.
  attr_accessor :state_change_lock

  # A Hash that maps the names of Google App Engine apps running in this
  # AppScale deployment to the total number of requests that haproxy has
  # processed.
  attr_accessor :total_req_seen

  # A Hash that maps the names of Google App Engine apps running in this
  # AppScale deployment to the current number of requests that haproxy has
  # queued.
  attr_accessor :current_req_rate

  # A Hash that maps the names of Google App Engine apps running in this
  # AppScale deployment to the last time we sampled the total number of
  # requests that haproxy has processed. When combined with
  # total_req_seen, we can infer the average number of requests per second
  # that come in for each App Engine application.
  attr_accessor :last_sampling_time

  # A Time that corresponds to the last time this machine added or removed
  # nodes in this AppScale deployment. Adding or removing nodes can happen
  # in response to autoscaling requests, or (eventually) to recover from
  # faults.
  attr_accessor :last_scaling_time

  # A Hash that maps reservation IDs generated when uploading App Engine
  # apps via the AppDashboard to the status of the uploaded app (e.g.,
  # started uploading, failed because of a bad app.yaml).
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
  APPSCALE_CONFIG_DIR = '/etc/appscale'.freeze

  # The tools uses this location to find deployments info. TODO: to remove
  # this dependency.
  APPSCALE_TOOLS_CONFIG_DIR = '/root/.appscale'.freeze

  # The location on the local filesystem where the AppController writes
  # the location of all the nodes which are taskqueue nodes.
  TASKQUEUE_FILE = "#{APPSCALE_CONFIG_DIR}/taskqueue_nodes".freeze

  APPSCALE_HOME = ENV['APPSCALE_HOME']

  # The location on the local filesystem where we save data that should be
  # persisted across AppScale deployments. Currently this is Cassandra data,
  # ZooKeeper data, and Google App Engine apps that users upload.
  PERSISTENT_MOUNT_POINT = '/opt/appscale'.freeze

  # The location where we can find the Python 2.7 executable, included because
  # it is not the default version of Python installed on AppScale VMs.
  PYTHON27 = '/usr/bin/python2'.freeze

  # The message that we display to the user if they call a SOAP-accessible
  # function with a malformed input (e.g., of the wrong class or format).
  BAD_INPUT_MSG = JSON.dump({ 'success' => false, 'message' => 'bad input' })

  # The message that we display to the user if they want to scale up services
  # in an Xen/KVM deployment but don't have enough open nodes to do so.
  NOT_ENOUGH_OPEN_NODES = JSON.dump({ 'success' => false,
    'message' => 'not enough open nodes' })

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

  # How often we should attempt to scale up. It's measured as a multiplier
  # of DUTY_CYCLE.
  SCALEUP_THRESHOLD = 5

  # How often we should attempt to decrease the number of AppServers on a
  # given node. It's measured as a multiplier of DUTY_CYCLE.
  SCALEDOWN_THRESHOLD = 15

  # When scaling down instances we need to use a much longer time in order
  # to reap the benefit of an already running instance.  This is a
  # multiplication factor we use with the above threshold.
  SCALE_TIME_MULTIPLIER = 6

  # This is the generic retries to do.
  RETRIES = 5

  # We won't allow any AppServer to have 1 minute average load
  # (normalized on the number of CPUs) to be bigger than this constant.
  MAX_LOAD_AVG = 2.0

  # We need to leave some extra RAM available for the system to operate
  # safely.
  SAFE_MEM = 50

  # Conversion divisor to MB for RAM statistics given in Bytes.
  MEGABYTE_DIVISOR = 1024 * 1024

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
  RESERVED_APPS = [AppDashboard::APP_NAME].freeze

  # A Fixnum that indicates what the first port is that can be used for hosting
  # Google App Engine apps.
  STARTING_APPSERVER_PORT = 20_000

  # A String that is returned to callers of get_app_upload_status that provide
  # an invalid reservation ID.
  ID_NOT_FOUND = 'Reservation ID not found.'.freeze

  # This String is used to inform the tools that the AppController is not
  # quite ready to receive requests.
  NOT_UP_YET = 'not-up-yet'.freeze

  # A String that is returned to callers of set_property that provide an invalid
  # instance variable name to set.
  KEY_NOT_FOUND = 'Invalid property name, or property value.'.freeze

  # A String indicating when we are looking for a Zookeeper connection to
  # become available.
  NO_ZOOKEEPER_CONNECTION = 'No Zookeeper available: in isolated mode'.freeze

  # Where to put logs.
  LOG_FILE = '/var/log/appscale/controller-17443.log'.freeze

  # Default memory to allocate to each AppServer.
  DEFAULT_MEMORY = 400

  # The default service for a project.
  DEFAULT_SERVICE = 'default'.freeze

  # The default version for a service.
  DEFAULT_VERSION = 'v1'.freeze

  # The character used to separate portions of a complete version string.
  # (e.g. guestbook_default_v1)
  VERSION_PATH_SEPARATOR = '_'.freeze

  # The port that the AdminServer listens on.
  ADMIN_SERVER_PORT = 17442

  # List of parameters allowed in the set_parameter (and in AppScalefile
  # at this time). If a default value is specified, it will be used if the
  # parameter is unspecified. The last value (a boolean) indicates if the
  # parameter's value is of a sensitive nature and shouldn't be printed in
  # the logs.
  PARAMETER_CLASS = 0
  PARAMETER_DEFAULT = 1
  PARAMETER_SHOW = 2
  PARAMETERS_AND_CLASS = {
    'aws_subnet_id' => [String, nil, true],
    'aws_vpc_id' => [String, nil, true],
    'azure_subscription_id' => [String, nil, false],
    'azure_app_id' => [String, nil, false],
    'azure_app_secret_key' => [String, nil, false],
    'azure_tenant_id' => [String, nil, false],
    'azure_resource_group' => [String, nil, false],
    'azure_storage_account' => [String, nil, false],
    'azure_group_tag' => [String, nil, false],
    'autoscale' => [TrueClass, 'True', true],
    'client_secrets' => [String, nil, false],
    'controller_logs_to_dashboard' => [TrueClass, 'False', false],
    'default_max_appserver_memory' => [Fixnum, "#{DEFAULT_MEMORY}", true],
    'default_min_appservers' => [Fixnum, '2', true],
    'default_max_appservers' => [Fixnum, '999999', true],
    'disks' => [String, nil, true],
    'ec2_access_key' => [String, nil, false],
    'ec2_secret_key' => [String, nil, false],
    'ec2_url' => [String, nil, false],
    'EC2_ACCESS_KEY' => [String, nil, false],
    'EC2_SECRET_KEY' => [String, nil, false],
    'EC2_URL' => [String, nil, false],
    'flower_password' => [String, nil, false],
    'group' => [String, nil, true],
    'keyname' => [String, nil, false],
    'infrastructure' => [String, nil, true],
    'instance_type' => [String, nil, true],
    'lb_connect_timeout' => [Fixnum, '120000', true],
    'login' => [String, nil, true],
    'machine' => [String, nil, true],
    'max_machines' => [Fixnum, '0', true],
    'min_machines' => [Fixnum, '1', true],
    'region' => [String, nil, true],
    'replication' => [Fixnum, '1', true],
    'project' => [String, nil, false],
    'table' => [String, 'cassandra', false],
    'use_spot_instances' => [TrueClass, nil, false],
    'user_commands' => [String, nil, true],
    'verbose' => [TrueClass, 'False', true],
    'write_nodes_stats_log' => [TrueClass, 'False', true],
    'nodes_stats_log_interval' => [Fixnum, '15', true],
    'write_processes_stats_log' => [TrueClass, 'False', true],
    'processes_stats_log_interval' => [Fixnum, '65', true],
    'write_proxies_stats_log' => [TrueClass, 'False', true],
    'proxies_stats_log_interval' => [Fixnum, '35', true],
    'write_detailed_processes_stats_log' => [TrueClass, 'False', true],
    'write_detailed_proxies_stats_log' => [TrueClass, 'False', true],
    'zone' => [String, nil, true]
  }.freeze

  # Template used for rsyslog configuration files.
  RSYSLOG_TEMPLATE_LOCATION = "#{APPSCALE_HOME}/common/appscale/common/" \
                              "templates/rsyslog-app.conf"

  # Instance variables that we need to restore from the head node.
  DEPLOYMENT_STATE = [
    "@app_info_map",
    "@versions_loaded",
    "@nodes",
    "@options",
    "@last_decision"
  ].freeze

  # The amount of memory in MB for each instance class.
  INSTANCE_CLASSES = {
    F1: 128,
    F2: 256,
    F4: 512,
    F4_1G: 1024,
    B1: 128,
    B2: 256,
    B4: 512,
    B4_1G: 1024,
    B8: 1024,
  }.freeze

  # Creates a new Djinn, which holds all the information needed to configure
  # and deploy all the services on this node.
  def initialize
    # The password, or secret phrase, that is required for callers to access
    # methods exposed via SOAP.
    @@secret = HelperFunctions.get_secret

    @@log = Logger.new(STDOUT)
    @@log.level = Logger::INFO

    @my_index = nil
    @my_public_ip = nil
    @my_private_ip = nil
    @done_initializing = false
    @done_terminating = false
    @waiting_messages = []
    @waiting_messages.extend(MonitorMixin)
    @message_ready = @waiting_messages.new_cond
    @done_loading = false
    @state = 'AppController just started'
    @cluster_stats = []
    @state_change_lock = Monitor.new

    @initialized_versions = {}
    @total_req_seen = {}
    @current_req_rate = {}
    @average_req_rate = {}
    @curr_sessions_list = []
    @last_sampling_time = {}
    @last_scaling_time = Time.now.to_i
    @app_upload_reservations = {}

    # This variable is used to keep track of the list of zookeeper servers
    # we have in this deployment.
    @zookeeper_data = []

    # This variable is used to keep track of the location files we write
    # when layout changes.
    @locations_content = ''

    # This variable keeps track of the state we read/write to zookeeper,
    # to avoid actions if nothing changed.
    @appcontroller_state = ''

    # The following variables are restored from the headnode ie they are
    # part of the common state of the running deployment.
    @app_info_map = {}
    @versions_loaded = []
    @nodes = []
    @options = {}
    @last_decision = {}

    # Make sure monit is started.
    MonitInterface.start_monit
  end

  # A SOAP-exposed method that callers can use to determine if this node
  # has received information from another node and is starting up.
  def is_done_initializing(secret)
    return @done_initializing if valid_secret?(secret)
    BAD_SECRET_MSG
  end

  # A SOAP-exposed method that callers can use to get information about what
  # roles each node in the AppScale deployment are running.
  def get_role_info(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    all_nodes = []
    @state_change_lock.synchronize {
      @nodes.each { |node| all_nodes << node.to_hash }
    }
    JSON.dump(all_nodes)
  end

  # A SOAP-exposed method that callers can use to get information about what
  # versions are running on this machine, as well as what ports they are bound
  # to, and what ports run nginx and haproxy in front of them.
  #
  # Args:
  #   secret: A String that authenticates callers.
  # Returns:
  #   BAD_SECRET_MSG if the caller could not be authenticated. If the caller
  #   can be authenticated, a JSON-dumped Hash containing information about
  #   versions on this machine is returned.
  def get_app_info_map(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    JSON.dump(@app_info_map)
  end

  # A SOAP-exposed method that callers can use to tell this AppController that
  # a version hosted in this cloud needs to have its nginx reverse proxy
  # serving HTTP and HTTPS traffic on different ports.
  #
  # Args:
  #   version_key: A String that names the version that should be relocated.
  #   http_port: A String or Fixnum that names the port that should be used to
  #     serve HTTP traffic for this app.
  #   https_port: A String or Fixnum that names the port that should be used to
  #     serve HTTPS traffic for this app.
  #   secret: A String that authenticates callers.
  # Returns:
  #   "OK" if the relocation occurred successfully, and a String containing the
  #   reason why the relocation failed in all other cases.
  def relocate_version(version_key, http_port, https_port, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    Djinn.log_debug("Received relocate_version for #{version_key} for " \
                    "http port #{http_port} and https port #{https_port}.")

    unless my_node.is_shadow?
      # We need to send the call to the shadow.
      Djinn.log_debug("Sending relocate_version for #{version_key} " \
        "to #{get_shadow}.")
      acc = AppControllerClient.new(get_shadow.private_ip, @@secret)
      begin
        return acc.relocate_version(version_key, http_port, https_port)
      rescue FailedNodeException => e
        Djinn.log_warn("Failed to forward relocate_version " \
          "call to #{get_shadow} (#{e.to_s}).")
        return NOT_READY
      end
    end

    project_id, service_id, version_id = version_key.split(
      VERSION_PATH_SEPARATOR)

    # Forward relocate as a patch request to the AdminServer.
    version = {:appscaleExtensions => {:httpPort => http_port.to_i,
                                       :httpsPort => https_port.to_i}}
    endpoint = ['v1', 'apps', project_id, 'services', service_id,
                'versions', version_id].join('/')
    fields_updated = %w(appscaleExtensions.httpPort
                        appscaleExtensions.httpsPort)
    uri = URI("http://#{my_node.private_ip}:#{ADMIN_SERVER_PORT}/#{endpoint}")
    uri.query = URI.encode_www_form({:updateMask => fields_updated.join(',')})
    headers = {'Content-Type' => 'application/json',
               'AppScale-Secret' => @@secret}
    request = Net::HTTP::Patch.new([uri.path, uri.query].join('?'), headers)
    request.body = JSON.dump(version)
    response = Net::HTTP.start(uri.hostname, uri.port) do |http|
      http.request(request)
    end
    return "false: #{response.body}" if response.code != '200'

    begin
      CronHelper.update_cron(@options['login'], project_id)
    rescue VersionNotFound => error
      return "false: #{error.message}"
    end

    'OK'
  end

  # This method validates that the layout received is correct (both
  # syntactically and logically).
  #
  # Args:
  #   layout: this is a JSON structure containing the nodes
  #     informations (IPs, roles, instance ID etc...). These are the nodes
  #     specified in the AppScalefile at startup time.
  #   keyname: the key of this deployment, needed to initialize
  #     NodeInfo.
  #
  # Returns:
  #   A NodeInfo array suitale to be used in @nodes.
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
      msg = 'Error: got exception parsing JSON structure layout.'
      Djinn.log_error(msg)
      raise AppScaleException.new(msg)
    end
    if locations.class != Array
      msg = 'Error: layout is not an Array.'
      Djinn.log_error(msg)
      raise AppScaleException.new(msg)
    end
    all_roles = []
    locations.each { |node|
      if node.class != Hash
        msg = 'Error: node structure is not a Hash.'
        Djinn.log_error(msg)
        raise AppScaleException.new(msg)
      end
      if !node['public_ip'] || !node['private_ip'] || !node['roles'] ||
        !node['instance_id']
        msg = "Error: node layout is missing information #{node}."
        Djinn.log_error(msg)
        raise AppScaleException.new(msg)
      elsif node['public_ip'].empty? || node['private_ip'].empty? ||
         node['roles'].empty? || node['instance_id'].empty?
        msg = "Error: node layout is missing information #{node}."
        Djinn.log_error(msg)
        raise AppScaleException.new(msg)
      end
      if node['roles'].class == String
        all_roles << node['roles']
      elsif node['roles'].class == Array
        all_roles += node['roles']
      else
        msg = "Error: node roles is not String or Array for #{node}."
        Djinn.log_error(msg)
        raise AppScaleException.new(msg)
      end
    }

    # Now we can check if we have the needed roles to start the
    # deployment.
    all_roles.uniq!
    ['compute', 'shadow', 'load_balancer', 'zookeeper', 'memcache',
     'db_master', 'taskqueue_master'].each { |role|
      unless all_roles.include?(role)
        msg = "Error: layout is missing role #{role}."
        Djinn.log_error(msg)
        raise AppScaleException.new(msg)
      end
    }

    # Transform the hash into NodeInfo and return it.
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
      key = name.gsub(NOT_EMAIL_REGEX, '')

      # Let's check if the property is a known one.
      unless PARAMETERS_AND_CLASS.has_key?(key)
        begin
          Djinn.log_warn("Removing unknown parameter '" + key.to_s + "'.")
        rescue
          Djinn.log_warn("Removing unknown parameter.")
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
          newval = val.gsub(NOT_FQDN_OR_PLUS_REGEX, '')
        else
          newval = val.gsub(NOT_FQDN_REGEX, '')
        end
      end

      newoptions[key] = newval
      newval = "*****" unless PARAMETERS_AND_CLASS[key][2]
      Djinn.log_debug("Accepted option #{key}:#{newval}.")
    }

    return newoptions
  end

  def enforce_options
    # Set the proper log level.
    new_level = Logger::INFO
    new_level = Logger::DEBUG if @options['verbose'].downcase == "true"
    @state_change_lock.synchronize {
      @@log.level = new_level if @@log.level != new_level
    }

    # The master node can now enforce some sanity checks on the options.
    if my_node.is_shadow? and is_cloud?
      @state_change_lock.synchronize {
        # Max and min needs to be at least the number of started nodes, it
        # needs to be positive. Max needs to be no smaller than min.
        if Integer(@options['max_machines']) < @nodes.length
          msg = 'max_machines is less than the number of nodes!'
          Djinn.log_warn(msg)
          raise AppScaleException.new(msg)
        end
        if Integer(@options['min_machines']) > @nodes.length
          msg = 'min_machines is bigger than the number of nodes!'
          Djinn.log_warn(msg)
          raise AppScaleException.new(msg)
        end
        if Integer(@options['max_machines']) < Integer(@options['min_machines'])
          msg = 'min_machines is bigger than max_machines!'
          Djinn.log_warn(msg)
          raise AppScaleException.new(msg)
        end

        # Ensure we have the correct EC2 credentials available.
        ENV['EC2_URL'] = @options['ec2_url']
        if @options['ec2_access_key'].nil?
          @options['ec2_access_key'] = @options['EC2_ACCESS_KEY']
          @options['ec2_secret_key'] = @options['EC2_SECRET_KEY']
          @options['ec2_url'] = @options['EC2_URL']
        end
      }
    end
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
    if opts.nil? || opts.empty? || opts.class != Hash
      msg = "Error: options is empty or not a Hash."
      Djinn.log_error(msg)
      return msg
    end
    checked_opts = check_options(opts)

    # Let's validate we have the needed options defined.
    ['keyname', 'login', 'table'].each { |key|
      unless checked_opts[key]
        msg = "Error: cannot find #{key} in options!"
        Djinn.log_error(msg)
        return msg
      end
    }

    # Now let's make sure the parameters that needs to have values are
    # indeed defines, otherwise set the defaults.
    PARAMETERS_AND_CLASS.each { |key, _|
      # The parameter 'key' is defined, no need to do anything.
      next if checked_opts[key]

      if PARAMETERS_AND_CLASS[key][1]
         # The parameter has a default, and it's not defined. Adding
         # default value.
         checked_opts[key] = PARAMETERS_AND_CLASS[key][1]
      end
    }

    # We need to make sure we have a good layout and this node is listed
    # in the started nodes.
    @state_change_lock.synchronize {
      @nodes = check_layout(layout, checked_opts['keyname'])
      find_me_in_locations
      return "Error: Couldn't find me in the node map" if @my_index.nil?

      # Now we can unlock the main thread and let it proceed with the
      # initialization.
      @options = checked_opts
    }
    Djinn.log_info("Successfully received nodes layout (#{@nodes}) and deployment options (#{@options}).")

    'OK'
  end

  # Upload a Google App Engine application into this AppScale deployment.
  #
  # Args:
  #   archived_file: A String, with the path to the compressed file containing
  #     the app.
  #   file_suffix: A String indicating what suffix the file should have.
  #   secret: A String with the shared key for authentication.
  # Returns:
  #   A JSON-dumped Hash with fields indicating if the upload process began
  #   successfully, and a reservation ID that can be used with
  #   get_app_upload_status to see if the app has successfully uploaded or not.
  def upload_app(archived_file, file_suffix, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    unless my_node.is_shadow?
      Djinn.log_debug("Sending upload_app call to shadow.")
      acc = AppControllerClient.new(get_shadow.private_ip, @@secret)
      begin
        remote_file = [archived_file, file_suffix].join('.')
        HelperFunctions.scp_file(archived_file, remote_file,
                                 get_shadow.private_ip, get_shadow.ssh_key)
        return acc.upload_app(remote_file, file_suffix)
      rescue FailedNodeException => e
        Djinn.log_warn("Failed to forward upload_app call to shadow " \
                       "(#{get_shadow}): #{e.to_s}.")
        return NOT_READY
      end
    end

    reservation_id = HelperFunctions.get_random_alphanumeric
    @app_upload_reservations[reservation_id] = {'status' => 'starting'}

    Djinn.log_debug("Received a request to upload app at #{archived_file}" \
      ", with suffix #{file_suffix}")

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
      command = "#{UPLOAD_APP_SCRIPT} --file '#{archived_file}' " \
        "--keyname #{keyname} 2>&1"
      output = Djinn.log_run(command)
      if output.include?("Your app can be reached at the following URL")
        result = "true"
      else
        result = output.dump
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
    return NOT_READY if @nodes.empty?

    unless my_node.is_shadow?
      Djinn.log_debug("Sending get_upload_status call to shadow.")
      acc = AppControllerClient.new(get_shadow.private_ip, @@secret)
      begin
        return acc.get_app_upload_status(reservation_id)
      rescue FailedNodeException => e
        Djinn.log_warn("Failed to forward get_app_upload_status call " \
                       "to #{get_shadow}: #{e.to_s}.")
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
  def get_cluster_stats_json(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    unless my_node.is_shadow?
      Djinn.log_debug("Sending get_cluster_stats_json call to shadow.")
      acc = AppControllerClient.new(get_shadow.private_ip, @@secret)
      begin
        return acc.get_cluster_stats_json
      rescue FailedNodeException => e
        Djinn.log_warn("Failed to forward get_cluster_stats_json call " \
                       "to #{get_shadow}: #{e.to_s}.")
        return NOT_READY
      end
    end

    @state_change_lock.synchronize { return JSON.dump(@cluster_stats) }
  end

  # Updates our locally cached information about the CPU, memory, and disk
  # usage of each machine in this AppScale deployment.
  def update_node_info_cache
    threads = []
    new_stats = []
    ips = []

    @state_change_lock.synchronize {
      @nodes.each { |node| ips << node.private_ip }
    }
    ips.each { |ip|
      threads << Thread.new {
        Thread.current[:new_stat] = nil
        begin
          if ip == my_node.private_ip
            ret = get_node_stats_json(@@secret)
          else
            acc = AppControllerClient.new(ip, @@secret)
            ret = acc.get_node_stats_json
          end
          Thread.current[:new_stat] = JSON.load(ret)
        rescue JSON::ParserError
            Djinn.log_warn("Failed to parse stats JSON from #{ip}: #{ret}")
        rescue FailedNodeException => e
          Djinn.log_warn("Failed to get stats from #{ip}: #{e.to_s}.")
        end
      }
    }

    threads.each { |t|
      t.join
      new_stats << t[:new_stat] unless t[:new_stat].nil?
    }

    @state_change_lock.synchronize { @cluster_stats = new_stats }
    Djinn.log_debug("Updated cluster stats.")
  end

  # Gets the database information of the AppScale deployment.
  #
  # Args:
  #   secret: A string with the shared key for authentication.
  # Returns:
  #   A JSON string with the database information.
  def get_database_information(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    tree = { :table => @options['table'], :replication => @options['replication'],
      :keyname => @options['keyname'] }
    return JSON.dump(tree)
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
    return NOT_READY if @nodes.empty?

    Thread.new {
      run_groomer_command = `which appscale-groomer`.chomp
      if my_node.is_db_master?
        Djinn.log_run(run_groomer_command)
      else
        db_master = get_db_master
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
    return NOT_READY if @nodes.empty?

    unless my_node.is_shadow?
      # We need to send the call to the shadow.
      Djinn.log_debug("Sending get_property for #{property_regex} to #{get_shadow}.")
      acc = AppControllerClient.new(get_shadow.private_ip, @@secret)
      begin
        return acc.get_property(property_regex)
      rescue FailedNodeException => e
        Djinn.log_warn("Failed to forward get_property call to " \
                       "#{get_shadow}: #{e.to_s}.")
        return NOT_READY
      end
    end

    Djinn.log_debug("Received request to get properties matching #{property_regex}.")
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

    Djinn.log_debug("Caller asked for instance variables matching regex " \
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
    return NOT_READY if @nodes.empty?

    if property_name.class != String or property_value.class != String
      Djinn.log_warn("set_property: received non String parameters.")
      return KEY_NOT_FOUND
    end

    unless my_node.is_shadow?
      # We need to send the call to the shadow.
      Djinn.log_debug("Sending set_property for #{property_name} to #{get_shadow}.")
      acc = AppControllerClient.new(get_shadow.private_ip, @@secret)
      begin
        return acc.set_property(property_name, property_value)
      rescue FailedNodeException => e
        Djinn.log_warn("Failed to forward set_property call to " \
                       "#{get_shadow}: #{e.to_s}.")
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
      if key == 'keyname'
        Djinn.log_warn('Changing keyname can break your deployment!')
      elsif key == 'default_max_appserver_memory'
        Djinn.log_warn('default_max_appserver_memory will be enforced on new AppServers only.')
        ZKInterface.set_runtime_params({:default_max_appserver_memory => Integer(val)})
      elsif key == 'min_machines'
        unless is_cloud?
          Djinn.log_warn('min_machines is not used in non-cloud infrastructures.')
        end
        if Integer(val) < Integer(@options['min_machines'])
          Djinn.log_warn('Invalid input: cannot lower min_machines!')
          return 'min_machines cannot be less than the nodes defined in ips_layout'
        end
      elsif key == 'max_machines'
        unless is_cloud?
          Djinn.log_warn('max_machines is not used in non-cloud infrastructures.')
        end
        if Integer(val) < Integer(@options['min_machines'])
          Djinn.log_warn('Invalid input: max_machines is smaller than min_machines!')
          return 'max_machines is smaller than min_machines.'
        end
      elsif key == 'default_min_appservers'
        if Integer(val) < 0 || Integer(val) > Integer(@options['default_max_appservers'])
          Djinn.log_warn('Invalid input: default_min_appservers needs to be ' \
                         'non-negative and smaller or equal to default_max_appservers.')
          return 'invalid input for default_min_appservers'
        end
      elsif key == 'default_max_appservers'
        if Integer(val) <= 0 || Integer(val) < Integer(@options['default_min_appservers'])
          Djinn.log_warn('Invalid input: default_max_appservers needs to be ' \
                         'positive and bigger or equal to default_min_appservers.')
          return 'invalid input for default_max_appservers'
        end
      elsif key == 'flower_password'
        TaskQueue.stop_flower
        TaskQueue.start_flower(@options['flower_password'])
      elsif key == 'replication'
        Djinn.log_warn('replication cannot be changed at runtime.')
        next
      elsif key == 'lb_connect_timeout'
        unless Integer(val) > 0
          Djinn.log_warn('Cannot set a negative timeout.')
          next
        end
      end

      @options[key] = val

      if key == 'login'
        Djinn.log_debug('[set_property] Regenerating cron for applications ' \
          'since login changed')
        versions_loaded_now = []
        APPS_LOCK.synchronize { versions_loaded_now = @versions_loaded.clone }
        Djinn.log_info("[set_property] Regenerating cron for #{versions_loaded_now}")
        versions_loaded_now.each { |version_key|
          project_id = version_key.split(VERSION_PATH_SEPARATOR).first
          update_cron(project_id, @@secret)
        }
      end

      if key.include? 'stats_log'
        if key.include? 'nodes'
          ZKInterface.update_hermes_nodes_profiling_conf(
            @options['write_nodes_stats_log'].downcase == 'true',
            @options['nodes_stats_log_interval'].to_i
          )
        elsif key.include? 'processes'
          ZKInterface.update_hermes_processes_profiling_conf(
            @options['write_processes_stats_log'].downcase == 'true',
            @options['processes_stats_log_interval'].to_i,
            @options['write_detailed_processes_stats_log'].downcase == 'true'
          )
        elsif key.include? 'proxies'
          ZKInterface.update_hermes_proxies_profiling_conf(
            @options['write_proxies_stats_log'].downcase == 'true',
            @options['proxies_stats_log_interval'].to_i,
            @options['write_detailed_proxies_stats_log'].downcase == 'true'
          )
        end
      end
      Djinn.log_info("Successfully set #{key} to #{val}.")
    }
    # Act upon changes.
    enforce_options unless old_options == @options

    return 'OK'
  end

  # Updates a project's cron jobs.
  def update_cron(project_id, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    unless my_node.is_shadow?
      Djinn.log_debug(
        "Sending update_cron call for #{project_id} to shadow.")
      acc = AppControllerClient.new(get_shadow.private_ip, @@secret)
      begin
        return acc.update_cron(project_id)
      rescue FailedNodeException => e
        Djinn.log_warn("Failed to forward update_cron call to shadow " \
                       "(#{get_shadow}): #{e.to_s}.")
        return NOT_READY
      end
    end

    begin
      CronHelper.update_cron(@options['login'], project_id)
    rescue VersionNotFound => error
      return "false: #{error.message}"
    end

    return 'OK'
  end

  # Checks ZooKeeper to see if the deployment ID exists.
  # Returns:
  #   A boolean indicating whether the deployment ID has been set or not.
  def deployment_id_exists(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    return ZKInterface.exists?(DEPLOYMENT_ID_PATH)
  end

  # Retrieves the deployment ID from ZooKeeper.
  # Returns:
  #   A string that contains the deployment ID.
  def get_deployment_id(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    begin
      return ZKInterface.get(DEPLOYMENT_ID_PATH)
    rescue FailedZooKeeperOperationException => e
      Djinn.log_warn("(get_deployment_id) failed talking to zookeeper " \
        "with #{e.message}.")
      return
    end
  end

  # Sets deployment ID in ZooKeeper.
  # Args:
  #   id: A string that contains the deployment ID.
  def set_deployment_id(secret, id)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    begin
      ZKInterface.set(DEPLOYMENT_ID_PATH, id, false)
    rescue FailedZooKeeperOperationException => e
      Djinn.log_warn("(set_deployment_id) failed talking to zookeeper " \
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
    return NOT_READY if @nodes.empty?
    return INVALID_REQUEST unless %w(true false).include?(read_only)

    if read_only == 'true'
      GroomerService.stop
    else
      GroomerService.start
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
    return NOT_READY if @nodes.empty?

    ZKInterface.get_datastore_servers.each { |machine_ip, port|
      http = Net::HTTP.new(machine_ip, port)
      request = Net::HTTP::Post.new('/read-only')
      request.body = { 'readOnly' => read_only == 'true' }.to_json
      http.request(request)
    }

    ips = []
    @state_change_lock.synchronize {
      @nodes.each { | node |
        ips << node.private_ip if node.is_db_master? || node.is_db_slave?
      }
    }
    ips.each { |ip|
      acc = AppControllerClient.new(ip, @@secret)
      begin
        response = acc.set_node_read_only(read_only)
      rescue FailedNodeException => e
        Djinn.log_warn("Failed to set read_only on #{ip}: #{e.to_s}.")
        return INVALID_REQUEST
      end
      unless response == 'OK'
        Djinn.log_warn("set_read_only: #{ip} responded with #{response}.")
        return response
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
    return NOT_READY if @nodes.empty?

    primary_ip = get_db_master.private_ip
    unless my_node.is_db_master?
      Djinn.log_debug("Asking #{primary_ip} if database is ready.")
      acc = AppControllerClient.new(get_db_master.private_ip, @@secret)
      begin
        return acc.primary_db_is_up
      rescue FailedNodeException => e
        Djinn.log_warn("Unable to ask #{primary_ip} if database is ready: #{e.to_s}.")
        return NOT_READY
      end
    end

    lock_obtained = NODETOOL_LOCK.try_lock
    begin
      return NOT_READY unless lock_obtained
      ready = nodes_ready.include?(primary_ip)
      return "#{ready}"
    ensure
      NODETOOL_LOCK.unlock if lock_obtained
    end
  end

  # Resets a user's password.
  #
  # Args:
  #   username: The email address for the user whose password will be changed.
  #   password: The SHA1-hashed password that will be set as the user's password.
  def reset_password(username, password, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    begin
      uac = UserAppClient.new(my_node.private_ip, @@secret)
      return uac.change_password(username, password)
    rescue FailedNodeException
      Djinn.log_warn("Failed to talk to the UserAppServer while resetting " \
        "the user's password.")
    end
  end

  # Queries the UserAppServer to see if the given user exists.
  #
  # Args:
  #   username: The email address registered as username for the user's application.
  def does_user_exist(username, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    begin
      uac = UserAppClient.new(my_node.private_ip, @@secret)
      return uac.does_user_exist?(username)
    rescue FailedNodeException
      Djinn.log_warn("Failed to talk to the UserAppServer to check if the " \
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
    return NOT_READY if @nodes.empty?

    begin
      uac = UserAppClient.new(my_node.private_ip, @@secret)
      return uac.commit_new_user(username, password, account_type)
    rescue FailedNodeException
      Djinn.log_warn("Failed to talk to the UserAppServer while committing " \
        "the user #{username}.")
    end
  end

  # Grants the given user the ability to perform any administrative action.
  #
  # Args:
  #   username: The e-mail address that should be given administrative authorizations.
  def set_admin_role(username, is_cloud_admin, capabilities, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    begin
      uac = UserAppClient.new(my_node.private_ip, @@secret)
      return uac.set_admin_role(username, is_cloud_admin, capabilities)
    rescue FailedNodeException
      Djinn.log_warn("Failed to talk to the UserAppServer while setting admin role " \
        "for the user #{username}.")
    end
  end

  def get_all_public_ips(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    public_ips = []
    @state_change_lock.synchronize {
      @nodes.each { |node| public_ips << node.public_ip }
    }
    JSON.dump(public_ips)
  end

  def get_all_private_ips(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    private_ips = []
    @state_change_lock.synchronize {
      @nodes.each { |node| private_ips << node.private_ip }
    }
    JSON.dump(private_ips)
  end

  def check_api_services
    # LoadBalancers needs to setup the routing
    # for the datastore and search2 (if applicable) before proceeding.
    while my_node.is_load_balancer? && !update_db_haproxy
      Djinn.log_info('Waiting for Datastore assignements ...')
      sleep(SMALL_WAIT)
    end

    has_search2 = !get_search2.empty?
    if has_search2
      while my_node.is_load_balancer? && !update_search2_haproxy
        Djinn.log_info('Waiting for Search2 assignements ...')
        sleep (SMALL_WAIT)
      end
    end

    # Wait till the Datastore is functional.
    loop do
      break if HelperFunctions.is_port_open?(get_load_balancer.private_ip,
                                             DatastoreServer::PROXY_PORT)
      Djinn.log_debug('Waiting for Datastore to be active...')
      sleep(SMALL_WAIT)
    end
    Djinn.log_info('Datastore service is active.')

    if has_search2
      # Wait till the Search2 is functional.
      loop do
        break if HelperFunctions.is_port_open?(get_load_balancer.private_ip,
                                               Search2::PROXY_PORT)
        Djinn.log_debug('Waiting for Search2 to be active...')
        sleep(SMALL_WAIT)
      end
      Djinn.log_info('Search2 service is active.')
    end

    # At this point all nodes are fully functional, so the Shadow will do
    # another assignments of the datastore and search2 processes
    # to ensure we got the accurate CPU count.
    assign_datastore_processes if my_node.is_shadow?
    assign_search2_processes if my_node.is_shadow? and has_search2
  end

  def job_start(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)

    Djinn.log_info("==== Starting AppController (pid: #{Process.pid}) ====")

    # On some platform (notably AWS) Ubuntu may be started without an
    # entry in /etc/hosts for the hostname, which would cause issues if
    # the DNS is not performant. We check and set it here to prevent
    # failure to start the system.
    update_etc_hosts

    # We reload our old IPs (if we find them) so we can check later if
    # they changed and act accordingly.
    begin
      @my_private_ip = HelperFunctions.read_file("#{APPSCALE_CONFIG_DIR}/my_private_ip")
      @my_public_ip = HelperFunctions.read_file("#{APPSCALE_CONFIG_DIR}/my_public_ip")
    rescue Errno::ENOENT
      Djinn.log_info("Couldn't find my old my_public_ip or my_private_ip.")
      @my_private_ip = nil
      @my_public_ip = nil
    end

    # If deprecated ZK_LOCATIONS_JSON_FILE is used,
    # convert it to regular ZK_LOCATIONS_FILE
    if not File.exists?(ZK_LOCATIONS_FILE) and File.exists?(ZK_LOCATIONS_JSON_FILE)
      # Read deprecated json file with zookeeper nodes.
      zookeeper_data = HelperFunctions.read_json_file(ZK_LOCATIONS_JSON_FILE)
      HelperFunctions.write_file(ZK_LOCATIONS_FILE, zookeeper_data['locations'].join("\n"))
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
      zookeeper_data = []
      File.foreach(ZK_LOCATIONS_FILE) { |line|
        zookeeper_data << line.strip() unless line.strip().empty?
      }
      @zookeeper_data = zookeeper_data
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
    unless restore_appcontroller_state
      wait_for_data
      erase_old_data
    end
    parse_options

    # Enforce actions from possibly changed options (like logs or
    # credentials).
    enforce_options

    # Load datastore helper.
    # TODO: this should be the class or module.
    table = @options['table']
    # require db_file
    begin
      require "#{table}_helper"
    rescue => e
      backtrace = e.backtrace.join("\n")
      HelperFunctions.log_and_crash("Unable to find #{table} helper." \
        " Please verify datastore type: #{e}\n#{backtrace}")
    end

    # If we have uncommitted changes, we rebuild/reinstall the
    # corresponding packages to ensure we are using the latest code.
    build_uncommitted_changes

    # From here on we have the basic local state that allows to operate.
    # In particular we know our roles, and the deployment layout. Let's
    # start attaching any permanent disk we may have associated with us.
    start_infrastructure_manager
    mount_persistent_storage

    write_database_info
    update_firewall

    # Let's account for the autoscaled nodes differently since we don't
    # have to wait for them (they could have been downscaled).
    skip_nodes = get_autoscaled_nodes
    nodes_to_wait = []
    @state_change_lock.synchronize { nodes_to_wait = @nodes - skip_nodes }

    # If we are the headnode, we may need to start/setup all other nodes.
    # Better do it early on, since it may take some time for the other
    # nodes to start up.
    if my_node.is_shadow?
      configure_ejabberd_cert
      Djinn.log_info("Preparing other nodes for this deployment.")
      initialize_nodes_in_parallel(nodes_to_wait, skip_nodes)
    end

    # Initialize the current server and starts all the API and essential
    # services. The functions are idempotent ie won't restart already
    # running services and can be ran multiple time with no side effect.
    initialize_server
    start_stop_api_services

    # Now that we are done loading, we can set the monit job to check the
    # AppController. At this point we are resilient to failure (ie the AC
    # will restart if needed).
    set_appcontroller_monit
    @done_loading = true

    pick_zookeeper(@zookeeper_data)
    write_our_node_info

    # We wait only for non autoscaled nodes.
    wait_for_nodes_to_finish_loading(nodes_to_wait)

    # Check that services are up before proceeding into the duty cycle.
    check_api_services

    # Make sure we have the first state saved in zookeeper.
    backup_appcontroller_state if my_node.is_shadow?

    # This variable is used to keep track of the last time we printed some
    # statistics to the log.
    last_print = Time.now.to_i

    # We use a thread to check the status of the cluster to ensure we
    # don't block waiting for the status.
    if my_node.is_shadow?
      update_stats_thread = Thread.new { update_node_info_cache }
    end

    loop do
      # Mark the beginning of the duty cycle.
      start_work_time = Time.now.to_i

      # We want to ensure monit stays up all the time, since we rely on
      # it for services and AppServers.
      unless MonitInterface.start_monit
        Djinn.log_warn('Monit was not running: restarted it.')
      end

      write_database_info
      update_port_files
      update_firewall
      write_zookeeper_locations

      # This call will block if we cannot reach a zookeeper node, but will
      # be very fast if we have an available connection. The function sets
      # the state in case we are looking for a zookeeper server.
      pick_zookeeper(@zookeeper_data)

      # We save the current @options and roles to check if
      # restore_appcontroller_state modifies them.
      old_options = @options.clone
      old_roles = my_node.roles
      my_versions_loaded = []
      APPS_LOCK.synchronize {
        my_versions_loaded = @versions_loaded.clone if my_node.is_load_balancer?
      }

      # The appcontroller state is a misnomer, since it contains the state
      # of the deployment that each node needs to reload. For example it
      # contains the current listing of AppServers and Nodes.
      unless restore_appcontroller_state
        # Master is responsible to populate the state for the other nodes
        # consumption, and since we know we could talk to zookeeper,
        # master needs to go ahead and write the state.
        unless my_node.is_shadow?
          @state = "Couldn't reach the deployment state: now in isolated mode"
          Djinn.log_warn("Cannot talk to zookeeper: in isolated mode.")
          next
        end
      end

      # We act here if options or roles for this node changed.
      check_role_change(old_options, old_roles)

      # The master node needs first to update the stats of the nodes, and
      # backup the deployment state for all other nodes to read.
      if my_node.is_shadow?
        write_tools_config
        if update_stats_thread.alive?
          Djinn.log_debug('Update thread still running: skipping updates.')
        else
          update_stats_thread = Thread.new { update_node_info_cache }
        end
        backup_appcontroller_state
      end

      # Load balancers (and shadow) needs to setup new applications.
      if my_node.is_load_balancer? || my_node.is_shadow?
        versions_loaded_now = []
        APPS_LOCK.synchronize { versions_loaded_now = @versions_loaded.clone }

        # Starts apps that are not running yet but they should.
        versions_to_load = versions_loaded_now - my_versions_loaded
        if my_node.is_shadow?
          begin
            versions_to_load = ZKInterface.get_versions - versions_loaded_now
          rescue FailedZooKeeperOperationException
            versions_to_load = []
          end
        end
        versions_to_load.each { |version_key|
          APPS_LOCK.synchronize {
            setup_app_dir(version_key, true)
            setup_appengine_version(version_key)
          }
        }

        # In addition only shadow kick off the autoscaler and manages
        # running instances.
        if my_node.is_shadow?
          missing_nodes = 0
          @state_change_lock.synchronize {
            missing_nodes = Integer(@options['min_machines']) - @nodes.length
          }
          APPS_LOCK.synchronize {
            scale_deployment
            scale_up_instances(missing_nodes) if missing_nodes > 0
          }
        end

        # Nodes need to clean up after removed applications.
        APPS_LOCK.synchronize { check_stopped_apps }
      end
      if my_node.is_load_balancer?
        # Load balancers need to regenerate nginx/haproxy configuration if needed.
        update_db_haproxy
        update_search2_haproxy unless get_search2.empty?
        APPS_LOCK.synchronize { regenerate_routing_config }
      end
      @state = "Done starting up AppScale, now in heartbeat mode"

      # Print stats in the log recurrently; works as a heartbeat mechanism.
      if last_print < (Time.now.to_i - 60 * PRINT_STATS_MINUTES)
        if my_node.is_shadow? && @options['autoscale'].downcase != "true"
          Djinn.log_info("--- This deployment has autoscale disabled.")
        end
        stats = nil
        ret = get_node_stats_json(secret)
        if ret == BAD_SECRET_MSG
          Djinn.log_warn("Bad secret while getting local stats!")
        elsif ret == INVALID_REQUEST
          Djinn.log_warn("Failed to retrieve local stats!")
        else
          begin
            stats = JSON.parse(ret)
          rescue JSON::ParserError
            Djinn.log_warn("Failed to parse local stats JSON.")
          end
        end
        unless stats.nil?
          Djinn.log_info("--- Node at #{stats['public_ip']} has " \
            "#{stats['memory']['available']/MEGABYTE_DIVISOR}MB memory available " \
            "and knows about these apps #{stats['apps']}.")
          Djinn.log_debug("--- Node stats: #{JSON.pretty_generate(stats)}")
        end
        last_print = Time.now.to_i
      end

      # Let's make sure we don't drift the duty cycle too much.
      duty_cycle_duration = Time.now.to_i - start_work_time
      if duty_cycle_duration < DUTY_CYCLE
        Kernel.sleep(DUTY_CYCLE - duty_cycle_duration)
      end
    end
  end

  def is_appscale_terminated(secret)
    begin
      return JSON.dump({'status'=>BAD_SECRET_MSG}) unless valid_secret?(secret)
    rescue Errno::ENOENT
      # On appscale down, terminate may delete our secret key before we
      # can check it here.
      Djinn.log_debug("is_appscale_terminated: didn't find secret file. Continuing.")
    end
    return @done_terminating
  end

  def run_terminate(clean, secret)
    begin
      return JSON.dump({'status'=>BAD_SECRET_MSG}) unless valid_secret?(secret)
    rescue Errno::ENOENT
      # On appscale down, terminate may delete our secret key before we
      # can check it here.
      Djinn.log_debug("is_appscale_terminated: didn't find secret file. Continuing.")
    end
    return NOT_READY if @nodes.empty?

    if my_node.is_shadow?
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
    @state_change_lock.synchronize {
      @nodes.each { |node|
        if node.private_ip != my_node.private_ip
          threads << Thread.new {
            Thread.current[:output] = terminate_appscale(node, clean)
          }
        end
      }
    }

    threads.each do |t|
      t.join
      yield t[:output]
    end

    'OK'
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
  def start_infrastructure_manager
    script = `which appscale-infrastructure`.chomp
    service_port = 17444
    start_cmd = "#{script} -p #{service_port}"
    start_cmd << ' --autoscaler' if my_node.is_shadow?
    start_cmd << ' --verbose' if @options['verbose'].downcase == 'true'

    MonitInterface.start(:iaas_manager, start_cmd)
    Djinn.log_info("Started InfrastructureManager successfully!")
  end

  def stop_infrastructure_manager
    Djinn.log_info("Stopping InfrastructureManager")
    MonitInterface.stop(:iaas_manager)
  end

  def get_online_users_list(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

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

  # This function removes this node from the list of possible sources for
  # a revision's source archive.
  #
  # Args:
  #   revision_key: The revision key.
  #   location: Full path for the tarball of the application.
  #   secret: The deployment current secret.
  # Returns:
  #   A Boolean indicating the success of the operation.
  def stop_hosting_revision(revision_key, location, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    Djinn.log_warn("#{location} still exists") unless File.exists?(location)

    begin
      ZKInterface.remove_revision_entry(revision_key, my_node.private_ip)
      return true
    rescue FailedZooKeeperOperationException => except
      # We just warn here and don't retry, since the shadow may have
      # already cleaned up the hosters.
      Djinn.log_warn("stop_hosting_revision: got exception talking to " \
        "zookeeper: #{except.message}.")
    end

    return false
  end

  # Finds an 'open' node and assigns the specified roles.
  #
  # Args:
  #   roles: An Array with the list of roles to assume.
  #
  # Returns:
  #   A Boolean indicating if an open node was found and the roles
  #   assigned.
  def assign_roles_to_open_node(roles)
    @state_change_lock.synchronize {
      @nodes.each { |node|
        if node.is_open?
          Djinn.log_debug("New roles #{roles} will be assumed by open node #{node}.")
          node.roles = roles
          return true
        end
      }
    }
    return false
  end

  # This SOAP-exposed method dynamically scales up a currently running
  # AppScale deployment. For virtualized clusters, this assumes the
  # user has given us a list of IP addresses where AppScale has been
  # installed to, and for cloud deployments, we assume that the user
  # wants to use the same credentials as for their current deployment.
  #
  # Args:
  #   ips_hash: A Hash that maps roles (e.g., compute, database) to the
  #     IP address (in virtualized deployments) or unique identifier (in
  #     cloud deployments) that should run that role.
  #   secret: A String password that is used to authenticate the request
  #     to add nodes to the deployment.
  # Returns:
  #   BAD_SECRET_MSG: If the secret given does not match the secret for
  #     this AppScale deployment.
  #   BAD_INPUT_MSG: If ips_hash was not a Hash.
  #   OK: otherwise.
  def start_roles_on_nodes(ips_hash, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    begin
      ips_hash = JSON.load(ips_hash)
    rescue JSON::ParserError
      Djinn.log_warn("ips_hash must be valid JSON")
      return BAD_INPUT_MSG
    end

    if ips_hash.class != Hash
      Djinn.log_warn("Was expecting ips_hash to be a Hash, not " \
        "a #{ips_hash.class}.")
      return BAD_INPUT_MSG
    end
    Djinn.log_debug("Received a request to start additional roles on " \
      "these machines: #{ips_hash}.")

    # ips_hash maps roles to IPs, but the internal format here maps
    # IPs to roles, so convert to the right format
    new_nodes_roles = {}
    node_roles = []
    ips_hash.each { |role, ip_or_ips|
      if ip_or_ips.class == String
        ips = [ip_or_ips]  # just one IP
      elsif ip_or_ips.class == Array
        ips = ip_or_ips  # a list of IPs
      else
        Djinn.log_warn("Was expecting an IP or list of IPs, got" \
          " a #{ip_or_ips.class}.")
        return BAD_INPUT_MSG
      end

      ips.each { |ip_or_node|
        begin
          # Convert (or check) if we have an IP address or we have a node
          # we need to start, then we add this role to the node.
          ip = HelperFunctions.convert_fqdn_to_ip(ip_or_node)
        rescue AppScaleException
          # We assume here that we need to create the VM (that is the user
          # specified node-#).
          new_nodes_roles[ip_or_node] = [] unless new_nodes_roles[ip_or_node]
          new_nodes_roles[ip_or_node] << role
          next
        end

        # Save the roles we want for this specific IP.
        found = false
        node_roles.each { |node|
          if node['private_ip'] == ip
            node.roles << role
            found = true
            break
          end
        }
        unless found
          node_roles << {
            "public_ip" => ip,
            "private_ip" => ip,
            "roles" => role,
            "disk" => nil
          }
        end
      }
    }
    Djinn.log_debug("Need to assign the following roles: #{new_nodes_roles}.")

    # Use the existing 'open' nodes first and delete them from the list of
    # roles still to fulfill.
    open_nodes = 0
    new_nodes_roles.each { |_, roles|
      open_nodes += 1 if assign_roles_to_open_node(roles)
    }
    open_nodes.downto(1) { new_nodes_roles.shift }

    # We spawn new nodes if we need to (and can do so) here.
    new_nodes_info = []
    if new_nodes_roles.length > 0
      unless is_cloud?
        Djinn.log_warn("Still need #{new_nodes_roles.length} more " \
          "nodes, but we aren't in a cloud environment, so we can't " \
          "aquire more nodes - failing the caller's request.")
        return NOT_ENOUGH_OPEN_NODES
      end

      # Ensure we have the default type to use for the autoscaled nodes.
      if @options['instance_type'].nil?
        Djinn.log_warn('instance_type is undefined, hence no ' \
                       'spawning of instance is possible.')
        return NOT_ENOUGH_OPEN_NODES
      end

      Djinn.log_info("Need to spawn #{new_nodes_roles.length} VMs.")

      # We create here the needed nodes, with open role and no disk.
      disks = Array.new(new_nodes_roles.length, nil)
      imc = InfrastructureManagerClient.new(@@secret, my_node.private_ip)
      begin
        new_nodes_info = imc.run_instances(new_nodes_roles.length, @options,
           new_nodes_roles.values, disks)
      rescue FailedNodeException, AppScaleException => exception
        Djinn.log_error("Couldn't spawn #{new_nodes_roles.length} VMs " \
          "because: #{exception.message}")
        return exception.message
      end
    end
    Djinn.log_debug("We used #{open_nodes} open nodes.")
    Djinn.log_debug("We spawned VMs for these roles #{new_nodes_info}.")
    Djinn.log_debug("We used the following existing nodes #{node_roles}.")

    # If we have an already running node with the same IP, we change its
    # roles list.
    new_nodes_info += node_roles unless node_roles.empty?
    @state_change_lock.synchronize {
      @nodes.each { |node|
        delete_index = nil
        new_nodes_info.each_with_index { |new_node, index|
          if new_node['private_ip'] == node.private_ip
            Djinn.log_info("Node at #{node.private_ip} changed role to #{new_node['roles']}.")
            node.roles = new_node['roles']
            delete_index = index
            break
          end
        }
        new_nodes_info.delete_at(delete_index) if delete_index
      }
    }
    add_nodes(new_nodes_info) unless new_nodes_info.empty?

    'OK'
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

    update_firewall
    initialize_nodes_in_parallel(new_nodes, [])
  end

  # Cleans out temporary files that may have been written by a previous
  # AppScale deployment.
  def erase_old_data
    Djinn.log_run("rm -f ~/.appscale_cookies")

    # Delete (possibly old) mapping of IP <-> HostKey.
    if File.exist?(File.expand_path('~/.ssh/known_hosts'))
      @state_change_lock.synchronize {
        @nodes.each { |node|
          Djinn.log_run("ssh-keygen -R #{node.private_ip}")
          Djinn.log_run("ssh-keygen -R #{node.public_ip}")
        }
      }
    end

    Nginx.clear_sites_enabled()
  end

  def wait_for_nodes_to_finish_loading(nodes)
    Djinn.log_info('Waiting for nodes to finish loading.')

    nodes.each { |node|
      if ZKInterface.is_node_done_loading?(node.private_ip)
        Djinn.log_info("Node at #{node.private_ip} has finished loading.")
        next
      else
        Djinn.log_info("Node at #{node.private_ip} has not yet finished " \
          "loading - will wait for it to finish.")
        Kernel.sleep(SMALL_WAIT)
        redo
      end
    }

    Djinn.log_info('Nodes have finished loading.')
    return
  end

  # This method logs a message that is useful to know when debugging AppScale,
  # but is too extraneous to know when AppScale normally runs.
  #
  # Args:
  #   message: A String containing the message to be logged.
  def self.log_debug(message)
    @@log.debug(message)
  end

  # This method logs a message that is useful to know when AppScale normally
  # runs.
  #
  # Args:
  #   message: A String containing the message to be logged.
  def self.log_info(message)
    @@log.info(message)
  end

  # This method logs a message that is useful to know when the AppController
  # experiences an unexpected event.
  #
  # Args:
  #   message: A String containing the message to be logged.
  def self.log_warn(message)
    @@log.warn(message)
  end

  # This method logs a message that corresponds to an erroneous, but
  # recoverable, event.
  #
  # Args:
  #   message: A String containing the message to be logged.
  def self.log_error(message)
    @@log.error(message)
  end

  # This method logs a message that immediately precedes the death of this
  # AppController.
  #
  # Args:
  #   message: A String containing the message to be logged.
  def self.log_fatal(message)
    @@log.fatal(message)
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

  # Logs and runs the given command, which is assumed to be trusted and thus
  # needs no filtering on our part. Obviously this should not be executed by
  # anything that the user could inject input into. Returns the output of
  # the command that was executed.
  def self.log_run(command)
    Djinn.log_debug("Running #{command}")
    output, err_output, status = Open3.capture3(command)
    if status.exitstatus != 0
      Djinn.log_debug("Command #{command} failed with #{status.exitstatus}" \
          " and output: #{output}")
      Djinn.log_debug("Command #{command} error output: " \
          "#{err_output}") if err_output
    end
    return output
  end

  # This method converts an Array of Strings (where each String contains all the
  # information about a single node) to an Array of NodeInfo objects, which
  # provide convenience methods that make them easier to operate on than just
  # raw String objects.
  def self.convert_location_array_to_class(nodes, keyname)
    array_of_nodes = []
    nodes.each { |node|
      converted = NodeInfo.new(node, keyname)
      array_of_nodes << converted
    }

    return array_of_nodes
  end

  # This method is the opposite of the previous method, and is needed when an
  # AppController wishes to pass node information to other AppControllers via
  # SOAP (as SOAP accepts Arrays and Strings but not NodeInfo objects).
  def self.convert_location_class_to_json(layout)
    if layout.class != Array
      @state = "Locations is not an Array, but a #{layout.class}."
      HelperFunctions.log_and_crash(@state, WAIT_TO_CRASH)
    end

    layout_array = []
    layout.each { |location|
      layout_array << location.to_hash
    }
    JSON.dump(layout_array)
  end

  def get_shadow
    @state_change_lock.synchronize {
      @nodes.each { |node| return node if node.is_shadow?  }
    }

    @state = "No shadow nodes found."
    HelperFunctions.log_and_crash(@state, WAIT_TO_CRASH)
  end

  def get_db_master
    @state_change_lock.synchronize {
      @nodes.each { |node| return node if node.is_db_master?  }
    }

    @state = "No DB master nodes found."
    HelperFunctions.log_and_crash(@state, WAIT_TO_CRASH)
  end

  def get_all_compute_nodes
    ae_nodes = []
    @state_change_lock.synchronize {
      @nodes.each { |node| ae_nodes << node.private_ip if node.is_compute?  }
    }
    return ae_nodes
  end

  # Gets a list of autoscaled nodes by going through the nodes array
  # and splitting the array from index greater than the
  # minimum images specified.
  def get_autoscaled_nodes
    autoscaled_nodes = []
    min_machines = Integer(@options['min_machines'])
    @state_change_lock.synchronize {
      autoscaled_nodes = @nodes.drop(min_machines)
    }
  end

  def get_load_balancer
    @state_change_lock.synchronize {
      @nodes.each { |node|
        return node if node.is_load_balancer?
      }
    }

    @state = "No load balancer nodes found."
    HelperFunctions.log_and_crash(@state, WAIT_TO_CRASH)
  end

  def get_search2
    @state_change_lock.synchronize {
      return @nodes.select { |node| node.is_search2? }
    }
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
    return NOT_READY if @nodes.empty?

    uuid = HelperFunctions.get_random_alphanumeric
    Djinn.log_info("Generated uuid #{uuid} for request to gather logs.")

    Thread.new {
      # Begin by copying logs on all machines to this machine.
      local_log_dir = "#{Dir.tmpdir}/#{uuid}"
      remote_log_dir = "/var/log/appscale"
      FileUtils.mkdir_p(local_log_dir)
      @state_change_lock.synchronize {
        @nodes.each { |node|
          this_nodes_logs = "#{local_log_dir}/#{node.private_ip}"
          FileUtils.mkdir_p(this_nodes_logs)
          Djinn.log_run("scp -r -i #{node.ssh_key} -o StrictHostkeyChecking=no " \
            "2>&1 root@#{node.private_ip}:#{remote_log_dir} #{this_nodes_logs}")
        }
      }

      # Next, tar.gz it up in the dashboard app so that users can download it.
      version_key = [AppDashboard::APP_NAME, DEFAULT_SERVICE,
                     DEFAULT_VERSION].join(VERSION_PATH_SEPARATOR)
      assets_dir = "#{HelperFunctions::VERSION_ASSETS_DIR}/#{version_key}"
      dashboard_log_location = "#{assets_dir}/static/download-logs/#{uuid}.tar.gz"
      Djinn.log_info("Done gathering logs - placing logs at " +
        dashboard_log_location)
      Djinn.log_run("tar -czf #{dashboard_log_location} #{local_log_dir}")
      FileUtils.rm_rf(local_log_dir)
    }

    return uuid
  end

  # Updates the list of blob_server in haproxy.
  def update_blob_servers
    servers = []
    get_all_compute_nodes.each { |ip|
      servers << {'ip' => ip, 'port' => BlobServer::SERVER_PORT}
    }
    HAProxy.create_app_config(servers, my_node.private_ip,
      BlobServer::HAPROXY_PORT, BlobServer::NAME)
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
    return NOT_READY if @nodes.empty?
    return NO_HAPROXY_PRESENT unless my_node.is_load_balancer?

    Djinn.log_debug('Adding BlobServer routing.')
    update_blob_servers
  end

  # Creates an Nginx/HAProxy configuration file for the Users/Apps soap server.
  def configure_uaserver
    all_db_private_ips = []
    @state_change_lock.synchronize {
      @nodes.each { | node |
        if node.is_db_master? or node.is_db_slave?
          all_db_private_ips.push(node.private_ip)
        end
      }
    }
    HAProxy.create_ua_server_config(all_db_private_ips,
      my_node.private_ip, UserAppClient::HAPROXY_SERVER_PORT)
    Nginx.add_service_location(
      'appscale-uaserver', my_node.private_ip,
      UserAppClient::HAPROXY_SERVER_PORT, UserAppClient::SSL_SERVER_PORT)
  end

  def update_db_haproxy
    begin
      servers = ZKInterface.get_datastore_servers.map { |machine_ip, port|
        {'ip' => machine_ip, 'port' => port}
      }
    rescue FailedZooKeeperOperationException
      Djinn.log_warn('Unable to fetch list of datastore servers')
      return false
    end

    HAProxy.create_app_config(servers, '*', DatastoreServer::PROXY_PORT,
                              DatastoreServer::NAME)
    return true
  end

  def update_search2_haproxy
    begin
      servers = ZKInterface.get_search2_servers.map { |machine_ip, port|
        {'ip' => machine_ip, 'port' => port}
      }
    rescue FailedZooKeeperOperationException
      Djinn.log_warn('Unable to fetch list of search2 servers')
      return false
    end

    HAProxy.create_app_config(servers, '*', Search2::PROXY_PORT, Search2::NAME)
    return true
  end

  # Creates HAProxy configuration for TaskQueue.
  def configure_tq_routing
    all_tq_ips = []
    @state_change_lock.synchronize {
      @nodes.each { | node |
        if node.is_taskqueue_master? || node.is_taskqueue_slave?
          all_tq_ips.push(node.private_ip)
        end
      }
    }
    HAProxy.create_tq_server_config(
      all_tq_ips, my_node.private_ip, TaskQueue::HAPROXY_PORT)

    # TaskQueue REST API routing.
    # We don't need Nginx for backend TaskQueue servers, only for REST support.
    rest_prefix = '~ /taskqueue/v1beta2/projects/.*'
    Nginx.add_service_location(
      'appscale-taskqueue', my_node.private_ip, TaskQueue::HAPROXY_PORT,
      TaskQueue::TASKQUEUE_SERVER_SSL_PORT, rest_prefix)
  end

  def remove_tq_endpoints
    HAProxy.remove_tq_endpoints
  end

  # TODO: this is a temporary fix. The dependency on the tools should be
  # removed.
  def write_tools_config
    ["#{@options['keyname']}.secret",
     "locations-#{@options['keyname']}.json"].each { |config|
      # Read the current config file for the deployment
      begin
        current = File.read("#{APPSCALE_CONFIG_DIR}/#{config}")
      rescue Errno::ENOENT
        Djinn.log_warn("Didn't find #{APPSCALE_CONFIG_DIR}/#{config}.")
        next
      end

      # Compare it with what the tools have and override if needed.
      config_file = "#{APPSCALE_TOOLS_CONFIG_DIR}/#{config}"
      begin
        tools_current = File.read(config_file)
      rescue Errno::ENOENT
        tools_current = ''
      end
      if tools_current != current
        FileUtils.mkdir_p(APPSCALE_TOOLS_CONFIG_DIR)
        File.open(config_file, 'w') { |dest_file| dest_file.write(current) }
        Djinn.log_info("Updated tools config #{config_file}.")
      end
    }
  end

  def write_database_info
    table = @options['table']
    replication = @options['replication']
    keyname = @options['keyname']

    tree = { :table => table, :replication => replication, :keyname => keyname }
    db_info_path = "#{APPSCALE_CONFIG_DIR}/database_info.yaml"
    File.open(db_info_path, "w") { |file| YAML.dump(tree, file) }
  end

  def update_port_files
    begin
      configured_versions = ZKInterface.get_versions
    rescue FailedZooKeeperOperationException
      Djinn.log_warn(
        'Failed to get configured versions when updating port files')
      return
    end

    configured_versions.each { |version_key|
      project_id, service_id, version_id = version_key.split(
        VERSION_PATH_SEPARATOR)
      begin
        version_details = ZKInterface.get_version_details(
          project_id, service_id, version_id)
      rescue VersionNotFound
        next
      end

      http_port = version_details['appscaleExtensions']['httpPort']
      port_file = "#{APPSCALE_CONFIG_DIR}/port-#{version_key}.txt"

      begin
        current_port = File.read(port_file).to_i
        update_port = current_port != http_port
      rescue Errno::ENOENT
        update_port = true
      end

      if update_port
        File.open(port_file, 'w') { |file| file.write("#{http_port}") }
      end
    }
  end

  def update_firewall
    Djinn.log_debug("Resetting firewall.")

    # We force the write of locations, to ensure we have an up-to-date
    # list of nodes in the firewall.
    write_locations
    if FIREWALL_IS_ON
      Djinn.log_run("bash #{APPSCALE_HOME}/firewall.conf")
    end
  end

  def backup_appcontroller_state
    local_state = {}
    APPS_LOCK.synchronize {
      local_state = {'@@secret' => @@secret }
      DEPLOYMENT_STATE.each { |var|
        value = nil
        if var == "@nodes"
          @state_change_lock.synchronize {
            value = Djinn.convert_location_class_to_json(@nodes)
          }
        else
          value = instance_variable_get(var)
        end
        local_state[var] = value
      }
    }
    @state_change_lock.synchronize {
      if @appcontroller_state == local_state.to_s
        Djinn.log_debug("backup_appcontroller_state: no changes.")
        return
      end
    }

    begin
      ZKInterface.write_appcontroller_state(local_state)
    rescue FailedZooKeeperOperationException => e
      Djinn.log_warn("Couldn't talk to zookeeper whle backing up " \
        "appcontroller state with #{e.message}.")
    end
    @state_change_lock.synchronize { @appcontroller_state = local_state.to_s }
    Djinn.log_debug("backup_appcontroller_state: updated state.")
  end

  # Takes actions if options or roles changed.
  #
  # Args:
  #   old_options: this is a clone of @options. We will compare it with
  #     the current value.
  #   old_roles: this is a list of roles. It will be compared against the
  #     current list of roles for this node.
  def check_role_change(old_options, old_roles)
    if old_roles != my_node.roles
      Djinn.log_info("Roles for this node are now: #{my_node.roles}.")
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
    json_state = ''

    unless File.exists?(ZK_LOCATIONS_FILE)
      Djinn.log_info("#{ZK_LOCATIONS_FILE} doesn't exist: not restoring data.")
      return false
    end

    loop {
      begin
        json_state = ZKInterface.get_appcontroller_state
      rescue => e
        Djinn.log_debug("Saw exception #{e.message} reading appcontroller state.")
        json_state = ''
        Kernel.sleep(SMALL_WAIT)
      end
      break unless json_state.empty?
      Djinn.log_warn("Unable to get state from zookeeper: trying again.")
      pick_zookeeper(@zookeeper_data)
    }
    if @appcontroller_state == json_state.to_s
      Djinn.log_debug("Reload state: no changes.")
      return true
    end

    Djinn.log_debug("Reload state : #{json_state}.")
    @appcontroller_state = json_state.to_s

    APPS_LOCK.synchronize {
      @@secret = json_state['@@secret']
      keyname = json_state['@options']['keyname']

      # Puts json_state.
      json_state.each { |k, v|
        next if k == "@@secret"
        v = Djinn.convert_location_array_to_class(JSON.load(v), keyname) if k == "@nodes"
        @state_change_lock.synchronize {
          instance_variable_set(k, v) if DEPLOYMENT_STATE.include?(k)
        }
      }

      # Check to see if our IP address has changed. If so, we need to update all
      # of our internal state to use the new public and private IP anywhere the
      # old ones were present.
      unless HelperFunctions.get_all_local_ips.include?(@my_private_ip)
        Djinn.log_info("IP changed old private:#{@my_private_ip} public:#{@my_public_ip}.")
        @state_change_lock.synchronize { update_state_with_new_local_ip }
        Djinn.log_info("IP changed new private:#{@my_private_ip} public:#{@my_public_ip}.")
      end
      Djinn.log_debug("app_info_map after restore is #{@app_info_map}.")
    }

    # Now that we've restored our state, update the pointer that indicates
    # which node in @nodes is ours
    @state_change_lock.synchronize { find_me_in_locations }
    Djinn.log_error("Couldn't find me in @nodes after restore!") if @my_index.nil?

    # Usually we don't expect the master node to see a change in the state
    # (since it is the one which saves it), so we leave a note here.
    if my_node.is_shadow?
      Djinn.log_warn("Detected a change in the master state #{json_state}.")
    end

    return true
  end

  # Method to ensure that we have our hostname defined in /etc/hosts. If
  # the hostname is not yet defined a line will be added
  #
  # 127.0.1.1        <fqdn-hostname> <hostname>
  #
  # to /etc/hosts.
  def update_etc_hosts
    my_hostname = Socket.gethostname
    my_fqdn = ''
    begin
      my_fqdn = Addrinfo.ip(my_hostname).getnameinfo.first
      my_fqdn = '' if my_fqdn =~ /^[[:digit:]]/
      my_fqdn = '' if my_fqdn == my_hostname
    rescue SocketError, Errno
      Djinn.log_warn("Couldn't get the fqdn of my hostname!")
    end

    etc_hosts = File.read(ETC_HOSTS)
    if etc_hosts =~ /#{my_hostname}/
      Djinn.log_info("/etc/hosts already have an entry for this hostname.")
      return
    end

    Djinn.log_info("hostname #{my_hostname} is not in /etc/hosts: adding it.")
    if etc_hosts =~ /127\.0\.1\.1/
      Djinn.log_warn("/etc/hosts already has 127.0.1.1 defined and it's not #{my_hostname}!")
      return
    end
    open(ETC_HOSTS, 'a') { |f|
      f << "\n\n# Local hostname added by AppScale to limit DNS queries."
      f << "\n127.0.1.1       #{my_fqdn} #{my_hostname}\n"
    }
  end

  # Updates all instance variables stored within the AppController with the new
  # public and private IP addreses of this machine.
  #
  # The issue here is that an AppController may back up state when running, but
  # when it is restored, its IP address changes (e.g., when taking AppScale down
  # then starting it up on new machines in a cloud deploy). This method searches
  # through internal AppController state to update any place where the old
  # public and private IP addresses were used, replacing them with the new one.
  def update_state_with_new_local_ip
    # First, find out this machine's private IP address. If multiple eth devices
    # are present, use the same one we used last time.
    all_local_ips = HelperFunctions.get_all_local_ips
    if all_local_ips.length < 1
      Djinn.log_and_crash("Couldn't detect any IP address on this machine!")
    end
    new_private_ip = all_local_ips[0]

    # Next, find out this machine's public IP address. In a cloud deployment, we
    # have to rely on the metadata server, while in a cluster deployment, it's
    # the same as the private IP.
    if ["ec2", "euca", "gce"].include?(@options['infrastructure'])
      new_public_ip = HelperFunctions.get_public_ip_from_metadata_service
    else
      new_public_ip = new_private_ip
    end

    # Finally, replace anywhere that the old public or private IP addresses were
    # used with the new one.
    old_public_ip = @my_public_ip
    old_private_ip = @my_private_ip

    @state_change_lock.synchronize {
      @nodes.each { |node|
        if node.public_ip == old_public_ip
          node.public_ip = new_public_ip
        end

        if node.private_ip == old_private_ip
          node.private_ip = new_private_ip
        end
      }
    }

    @app_info_map.each { |_, app_info|
      next if app_info['appservers'].nil?

      changed = false
      new_app_info = []
      app_info['appservers'].each { |location|
        host, port = location.split(":")
        if host == old_private_ip
          host = new_private_ip
          changed = true
        end
        new_app_info << "#{host}:#{port}"

        app_info['appservers'] = new_app_info if changed
      }
    }

    @cluster_stats = []

    @my_public_ip = new_public_ip
    @my_private_ip = new_private_ip
  end

  # Writes any custom configuration data in /etc/appscale to ZooKeeper.
  def set_custom_config
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

    if @options.key?('default_max_appserver_memory')
      ZKInterface.set_runtime_params(
        {:default_max_appserver_memory => Integer(@options['default_max_appserver_memory'])})
    end
  end

  # Updates the file that says where all the ZooKeeper nodes are
  # located so that this node has the most up-to-date info if it needs to
  # restore the data down the line.
  def write_zookeeper_locations
    zookeeper_data = []

    @state_change_lock.synchronize {
      @nodes.each { |node|
        if node.is_zookeeper?
          unless zookeeper_data.include? node.private_ip
            zookeeper_data << node.private_ip
          end
        end
      }
    }

    # Let's see if it changed since last time we got the list.
    zookeeper_data.sort!
    if zookeeper_data != @zookeeper_data
      # Save the latest list of zookeeper nodes: needed to restart the
      # deployment.
      HelperFunctions.write_file(ZK_LOCATIONS_FILE, zookeeper_data.join("\n"))
      @zookeeper_data = zookeeper_data
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

      ip = zk_list.sample
      Djinn.log_info("Trying to use zookeeper server at #{ip}.")
      ZKInterface.init_to_ip(@my_private_ip, ip.to_s)
    }
    Djinn.log_debug("Found zookeeper server.")
  end

  # Backs up information about what this node is doing (roles, apps it is
  # running) to ZooKeeper, for later recovery or updates by other nodes.
  def write_our_node_info
    # Since more than one AppController could write its data at the same
    # time, get a lock before we write to it.
    begin
      ZKInterface.lock_and_run {
        ZKInterface.write_node_information(my_node, @done_loading)
      }
    rescue => e
      Djinn.log_info("(write_our_node_info) saw exception #{e.message}")
    end

    return
  end

  # Returns information about the AppServer processes hosting App Engine apps on
  # this machine.
  def get_instance_info(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    APPS_LOCK.synchronize {
      instance_info = []
      @app_info_map.each_pair { |version_key, app_info|
        next if app_info['appservers'].nil?
        project_id, service_id, version_id = version_key.split(
          VERSION_PATH_SEPARATOR)
        begin
          version_details = ZKInterface.get_version_details(
            project_id, service_id, version_id)
        rescue VersionNotFound
          next
        end

        app_info['appservers'].each { |location|
          host, port = location.split(":")
          next if Integer(port) < 0
          instance_info << {
            'versionKey' => version_key,
            'host' => host,
            'port' => Integer(port),
            'language' => version_details['runtime']
          }
        }
      }

      return JSON.dump(instance_info)
    }
  end

  # Removes information associated with the given IP address from our local
  # cache (@nodes) as well as the remote node storage mechanism (in
  # ZooKeeper).
  def remove_node_from_local_and_zookeeper(ip)
    # First, remove our local copy
    index_to_remove = nil
    @state_change_lock.synchronize {
      @nodes.each_index { |i|
        next unless @nodes[i].private_ip == ip
        index_to_remove = i
        break
      }
      @nodes.delete_at(index_to_remove) if index_to_remove
    }

    # Then remove the remote copy
    begin
      ZKInterface.remove_node_information(ip)
    rescue FailedZooKeeperOperationException => e
      Djinn.log_warn("(remove_node_from_local_and_zookeeper) issues " \
        "talking to zookeeper with #{e.message}.")
    end
  end

  def wait_for_data
    loop {
      break if got_all_data
      Djinn.log_info('Waiting for data from the load balancer or cmdline tools.')
      Kernel.sleep(SMALL_WAIT)
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

  def got_all_data
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
  def find_me_in_locations
    @my_index = nil
    all_local_ips = HelperFunctions.get_all_local_ips
    if all_local_ips.length > 1
      Djinn.log_warn("This node has multiple private IPs: " \
        "#{all_local_ips.join(', ')}")
    end

    @nodes.each_with_index { |node, index|
      all_local_ips.each { |ip|
        if ip == node.private_ip
          @my_index = index
          @my_public_ip = node.public_ip
          @my_private_ip = node.private_ip
          Djinn.log_info("Local IP recorded and used is #{ip}.")
          return
        end
      }
    }
    Djinn.log_error("Cannot find any of my IP (#{all_local_ips}) in @nodes (#{@nodes}).")

    # We haven't found our ip in the nodes layout: let's try to give
    # better debugging info to the user.
    public_ip = HelperFunctions.get_public_ip_from_metadata_service
    @nodes.each { |node|
      if node.private_ip == public_ip
        HelperFunctions.log_and_crash("Found my public ip (#{public_ip}) " \
          "but not my private ip in @nodes.")
      end
      if node.public_ip == public_ip
        HelperFunctions.log_and_crash("Found my public ip (#{public_ip}) " \
          "in @nodes but my private ip is not matching! @nodes=#{@nodes}.")
      end
    }

    HelperFunctions.log_and_crash("Can't find my node in @nodes: #{@nodes}. " \
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
          @state_change_lock.synchronize {
            configure_zookeeper(@nodes, @my_index)
          }
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
      @state_change_lock.synchronize {
        @nodes.each { |node|
          db_master = node.private_ip if node.roles.include?('db_master')
        }
      }
      setup_db_config_files(db_master, my_node.private_ip)

      threads << Thread.new {
        Djinn.log_info("Starting database services.")
        db_nodes = nil
        @state_change_lock.synchronize {
          db_nodes = @nodes.count{|node| node.is_db_master? or node.is_db_slave?}
        }
        needed_nodes = needed_for_quorum(db_nodes,
                                         Integer(@options['replication']))

        # If this machine is running other services, decrease Cassandra's max
        # heap size.
        heap_reduction = 0
        heap_reduction += 0.25 if my_node.is_compute?
        if my_node.is_taskqueue_master? || my_node.is_taskqueue_slave?
          heap_reduction += 0.15
        end
        heap_reduction += 0.15 if my_node.is_search2?
        heap_reduction = heap_reduction.round(2)

        if my_node.is_db_master?
          start_db_master(false, needed_nodes, db_nodes, heap_reduction)
          prime_database
        else
          start_db_slave(false, needed_nodes, db_nodes, heap_reduction)
        end
      }
    else
      stop_db_master
      stop_db_slave
    end

    # We now wait for the essential services to go up.
    Djinn.log_info('Waiting for DB services ... ')
    threads.each { |t| t.join }

    Djinn.log_info('Ensuring necessary database tables are present')
    sleep(SMALL_WAIT) until system("#{PRIME_SCRIPT} --check > /dev/null 2>&1")

    Djinn.log_info('Ensuring data layout version is correct')
    layout_script = `which appscale-data-layout`.chomp
    retries = 10
    loop {
      output = `#{layout_script} --db-type cassandra 2>&1`
      if $?.exitstatus == 0
        break
      elsif $?.exitstatus == INVALID_VERSION_EXIT_CODE
        HelperFunctions.log_and_crash(
          'Unexpected data layout version. Please run "appscale upgrade".')
      elsif retries.zero?
        HelperFunctions.log_and_crash(
          'Exceeded retries while trying to check data layout.')
      else
        Djinn.log_warn("Error while checking data layout:\n#{output}")
        sleep(SMALL_WAIT)
      end
      retries -= 1
    }

    if my_node.is_db_master? or my_node.is_db_slave?
      @state = "Starting UAServer"
      # Start the UserAppServer and wait till it's ready.
      start_soap_server
      Djinn.log_info("Done starting database services.")
    else
      stop_soap_server
    end

    # All nodes wait for the UserAppServer now. The call here is just to
    # ensure the UserAppServer is talking to the persistent state.
    HelperFunctions.sleep_until_port_is_open(@my_private_ip,
      UserAppClient::SSL_SERVER_PORT, USE_SSL)
    uac = UserAppClient.new(@my_private_ip, @@secret)
    begin
      uac.does_user_exist?("not-there")
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
          verbose = @options['verbose'].downcase == 'true'
          GroomerService.start_transaction_groomer(verbose)
        end
      }
    else
      threads << Thread.new {
        stop_groomer_service
        GroomerService.stop_transaction_groomer
      }
    end

    start_admin_server

    if my_node.is_memcache?
      threads << Thread.new { start_memcache }
    else
      threads << Thread.new { stop_memcache }
    end

    if my_node.is_load_balancer?
      threads << Thread.new {
        start_ejabberd
        configure_tq_routing
      }
    else
      threads << Thread.new {
        remove_tq_endpoints
        stop_ejabberd
      }
    end

    # The headnode needs to ensure we have the appscale user, and it needs
    # to prepare the dashboard to be started.
    if my_node.is_shadow?
      threads << Thread.new {
        create_appscale_user
        prep_app_dashboard
      }
    end

    if my_node.is_compute?
      threads << Thread.new {
        start_app_manager_server
        start_blobstore_server
      }
    else
      threads << Thread.new {
        stop_app_manager_server
        stop_blobstore_server
      }
    end

    if my_node.is_search?
      threads << Thread.new { start_search_role }
    else
      threads << Thread.new { stop_search_role }
    end

    if my_node.is_search2?
      threads << Thread.new { start_search2_role }
    else
      threads << Thread.new { stop_search2_role }
    end

    if my_node.is_taskqueue_master?
      threads << Thread.new { start_taskqueue_master }
    elsif my_node.is_taskqueue_slave?
      threads << Thread.new { start_taskqueue_slave }
    else
      threads << Thread.new { stop_taskqueue }
    end

    # App Engine apps rely on the above services to be started, so
    # join all our threads here
    Djinn.log_info('Waiting for relevant services to finish starting up,')
    threads.each { |t| t.join }
    Djinn.log_info('API services have started on this node.')

    # Start Hermes with integrated stats service
    start_hermes

    # Leader node starts additional services.
    if my_node.is_shadow?
      @state = 'Assigning Datastore and Search2 processes'
      assign_datastore_processes
      assign_search2_processes
      TaskQueue.start_flower(@options['flower_password'])
    else
      TaskQueue.stop_flower
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
  def prime_database
    table = @options['table']
    prime_script = `which appscale-prime-#{table}`.chomp
    replication = Integer(@options['replication'])
    retries = 10
    Djinn.log_info('Ensuring necessary tables have been created')
    loop {
      prime_cmd = "#{prime_script} --replication #{replication} >> " \
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

  def start_blobstore_server
    # Each node uses the active load balancer to access the Datastore.
    BlobServer.start(get_load_balancer.private_ip, DatastoreServer::PROXY_PORT)
    return true
  end

  def start_search_role
    verbose = @options['verbose'].downcase == "true"
    Search.start_master(false, verbose)
  end

  def stop_search_role
    Search.stop
  end

  def start_search2_role
    search_pth = "#{APPSCALE_HOME}/SearchService2"
    Djinn.log_debug('Ensuring Solr is configured and started.')
    is_db = my_node.is_db_master? || my_node.is_db_slave?
    is_tq = my_node.is_taskqueue_master? || my_node.is_taskqueue_slave?
    heap_reduction = 0
    heap_reduction += 0.40 if is_db
    heap_reduction += 0.25 if my_node.is_compute?
    heap_reduction += 0.15 if is_tq
    heap_reduction = heap_reduction.round(2)
    Djinn.log_run("HEAP_REDUCTION=#{heap_reduction} "\
                  "#{search_pth}/solr-management/ensure_solr_running.sh")
    Djinn.log_debug('Done starting Solr on this node.')
  end

  def stop_search2_role
    # Stop Solr
    Djinn.log_debug('Stopping SOLR on this node.')
    Djinn.log_run('systemctl stop solr')
    Djinn.log_run('systemctl disable solr')
    Djinn.log_debug('Done stopping SOLR.')
  end

  def start_taskqueue_master
    verbose = @options['verbose'].downcase == "true"
    TaskQueue.start_master(false, verbose)
    return true
  end

  def stop_taskqueue
    TaskQueue.stop
  end

  def start_taskqueue_slave
    # All slaves connect to the master to start
    master_ip = nil
    @state_change_lock.synchronize {
      @nodes.each { |node|
        master_ip = node.private_ip if node.is_taskqueue_master?
      }
    }

    verbose = @options['verbose'].downcase == "true"
    unless TaskQueue.start_slave(master_ip, false, verbose)
      HelperFunctions.log_and_crash("Cannot start TQ slave!")
    end
    true
  end

  # Starts the application manager which is a SOAP service in charge of
  # starting and stopping applications.
  def start_app_manager_server
    @state = "Starting up AppManager"
    app_manager_script = `which appscale-instance-manager`.chomp
    start_cmd = "#{PYTHON27} #{app_manager_script}"
    MonitInterface.start(:appmanagerserver, start_cmd)
  end

  # Starts the Hermes service on this node.
  def start_hermes
    @state = "Starting Hermes"
    Djinn.log_info("Starting Hermes service.")
    script = `which appscale-hermes`.chomp
    start_cmd = "/usr/bin/python2 #{script}"
    start_cmd << ' --verbose' if @options['verbose'].downcase == 'true'
    MonitInterface.start(:hermes, start_cmd)
    if my_node.is_shadow?
      nginx_port = 17441
      service_port = 4378
      Nginx.add_service_location(
        'appscale-administration', my_node.private_ip,
        service_port, nginx_port, '/stats/cluster/')
    end
    Djinn.log_info("Done starting Hermes service.")
  end

  # Starts the groomer service on this node. The groomer cleans the datastore of deleted
  # items and removes old logs.
  def start_groomer_service
    @state = "Starting Groomer Service"
    Djinn.log_info("Starting groomer service.")
    GroomerService.start
    Djinn.log_info("Done starting groomer service.")
  end

  def start_soap_server
    db_master_ip = nil
    @state_change_lock.synchronize {
      @nodes.each { |node|
        db_master_ip = node.private_ip if node.is_db_master?
      }
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
    MonitInterface.start(:uaserver, start_cmd, nil, env_vars)
  end

  def assign_datastore_processes
    # Shadow is the only node to call this method, and is called upon
    # startup.
    return unless my_node.is_shadow?

    Djinn.log_info("Assigning datastore processes.")
    verbose = @options['verbose'].downcase == 'true'
    db_nodes = []
    @state_change_lock.synchronize {
      @nodes.each { |node|
        db_nodes << node if node.is_db_master? || node.is_db_slave?
      }
    }

    # Assign the proper number of Datastore processes on each database
    # machine.
    db_nodes.each { |node|
      assignments = {}
      assignments['datastore'] = {'verbose' => verbose}
      ZKInterface.set_machine_assignments(node.private_ip, assignments)
      Djinn.log_debug("Node #{node.private_ip} got #{assignments}.")
    }
  end

  def assign_search2_processes
    # Shadow is the only node to call this method,
    # and is called upon startup.
    return unless my_node.is_shadow?

    Djinn.log_info("Assigning search processes.")
    verbose = @options['verbose'].downcase == 'true'

    # Assign the proper number of Search2 processes on each search2 machine.
    get_search2.each { |node|
      assignments = {}
      begin
        cpu_count = HermesClient.get_cpu_count(node.private_ip, @@secret)
        server_count = (cpu_count * Search2::MULTIPLIER).to_i
        server_count = 1 if server_count == 0
      rescue FailedNodeException
        server_count = Search2::DEFAULT_NUM_SERVERS
      end

      assignments['search'] = {'count' => server_count,
                               'verbose' => verbose}
      ZKInterface.set_machine_assignments(node.private_ip, assignments)
      Djinn.log_debug("Node #{node.private_ip} got #{assignments}.")
    }
  end

  # Starts the Log Server service on this machine
  def start_log_server
    log_server_pid = '/var/run/appscale/log_service.pid'
    log_server_file = '/var/log/appscale/log_service.log'
    twistd = `which twistd`.chomp
    env = `which env`.chomp
    bash = `which bash`.chomp

    env_vars = {
      'APPSCALE_HOME' => APPSCALE_HOME,
      'PYTHONPATH' => "#{APPSCALE_HOME}/LogService/"
    }
    start_cmd = [env, env_vars.map{ |k, v| "#{k}=#{v}" }.join(' '),
                 twistd,
                 '--pidfile', log_server_pid,
                 '--logfile', log_server_file,
                 'appscale-logserver'].join(' ')
    stop_cmd = "#{bash} -c 'kill $(cat #{log_server_pid})'"

    MonitInterface.start_daemon(:log_service, start_cmd, stop_cmd,
                                log_server_pid)
    Djinn.log_info("Started Log Server successfully!")
  end

  def stop_log_server
    Djinn.log_info("Stopping Log Server")
    MonitInterface.stop(:log_service)
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
  def stop_groomer_service
    Djinn.log_info("Stopping groomer service.")
    GroomerService.stop
    Djinn.log_info("Done stopping groomer service.")
  end

  def is_cloud?
    return ['ec2', 'euca', 'gce', 'azure'].include?(@options['infrastructure'])
  end

  def update_python_package(target, pip="pip")
    Djinn.log_info("Building uncommitted changes for '#{target}' using #{pip}")
    log_file = '/var/log/appscale/pip_installation.log'
    cmd = "#{pip} install --upgrade --no-deps #{target}"
    system("echo \"$(date '+\%F \%T') Executing '#{cmd}'\" >> #{log_file}")
    unless system("#{cmd}" + " >> #{log_file} 2>&1")
      Djinn.log_error("Unable to update '#{target}' using #{pip} " \
                      "(install failed).")
      return
    end
    cmd = "#{pip} install #{target}"
    system("echo \"$(date '+\%F \%T') Executing '#{cmd}'\" >> #{log_file}")
    unless system("#{cmd}" + " >> #{log_file} 2>&1")
      Djinn.log_error("Unable to update '#{target}' using #{pip} " \
                      "(install dependencies failed).")
      return
    end
    Djinn.log_info("Finished building target '#{target}' using #{pip}.")
  end

  def cache_package(package_file)
    local_archive = "#{APPSCALE_CACHE_DIR}/#{package_file}"
    unless File.file?(local_archive)
      Net::HTTP.start(PACKAGE_MIRROR_DOMAIN) do |http|
        resp = http.get("#{PACKAGE_MIRROR_PATH}/#{package_file}")
        open(local_archive, 'wb') do |file|
          file.write(resp.body)
        end
      end
    end
    return local_archive
  end

  def build_java_appserver
    Djinn.log_info('Building uncommitted Java AppServer changes')

    new_jsp_jar = 'repackaged-appengine-eclipse-jdt-ecj.jar'
    old_jsp_jar = 'repackaged-appengine-jasper-jdt-6.0.29.jar'

    # Ensure packages cached
    local_sdk_path = cache_package('appengine-java-sdk-1.8.4.zip')
    new_jsp_jar_path = cache_package(new_jsp_jar)

    java_server = "#{APPSCALE_HOME}/AppServer_Java"
    jsp_lib_path = "#{java_server}/appengine-java-sdk-1.8.4/lib/tools/jsp"
    unzip = "unzip -o #{local_sdk_path} -d #{java_server} > /dev/null 2>&1"
    update = "rm #{jsp_lib_path}/#{old_jsp_jar}; " \
             "cp #{new_jsp_jar_path} #{jsp_lib_path}/ > /dev/null 2>&1"
    install = "ant -f #{java_server}/build.xml install > /dev/null 2>&1"
    clean = "ant -f #{java_server}/build.xml clean-build > /dev/null 2>&1"
    if system(unzip) && system(update) && system(install) && system(clean)
      Djinn.log_info('Finished building Java AppServer')
    else
      Djinn.log_error('Unable to build Java AppServer')
    end
  end

  def build_api_server
    Djinn.log_info('Compiling APIServer proto files')
    src = File.join(APPSCALE_HOME, 'APIServer')
    proto_dest = File.join(src, 'appscale', 'api_server')
    unless system("protoc --proto_path=#{src} --python_out=#{proto_dest} " \
                  "#{src}/*.proto")
      Djinn.log_error('Unable to compile APIServer proto files')
      return
    end
    update_python_package(src, '/opt/appscale_venvs/api_server/bin/pip')
  end

  def build_taskqueue
    Djinn.log_info('Compiling AppTaskQueue proto files')
    src = File.join(APPSCALE_HOME, 'AppTaskQueue', 'appscale', 'taskqueue',
                    'protocols')
    unless system("./#{src}/compile_protocols.sh")
      Djinn.log_error('Unable to compile AppTaskQueue proto files')
      return
    end
    extras = TaskQueue::OPTIONAL_FEATURES.join(',')
    update_python_package("#{APPSCALE_HOME}/AppTaskQueue[#{extras}]",
                          TaskQueue::TASKQUEUE_PIP)
  end

  def build_search_service2
    Djinn.log_info('Compiling Search2 proto files')
    build_scripts_path = "#{APPSCALE_HOME}/SearchService2/build-scripts"
    unless system("#{build_scripts_path}/compile_protocols.sh")
      Djinn.log_error('Unable to compile Search2 proto files')
      return
    end
    Djinn.log_info('Compiling ANTLR-4 query parser')
    unless system("#{build_scripts_path}/compile_query.sh")
      Djinn.log_error('Unable to compile ANTLR-4 query parser')
      return
    end
    update_python_package("#{APPSCALE_HOME}/SearchService2",
                          '/opt/appscale_venvs/search2/bin/pip')
  end

  # Run a build on modified directories so that changes will take effect.
  def build_uncommitted_changes
    status = `git -C #{APPSCALE_HOME} status`

    # Update Python packages across corresponding virtual environments
    if status.include?('common')
      update_python_package("#{APPSCALE_HOME}/common")
      update_python_package("#{APPSCALE_HOME}/common",
                            '/opt/appscale_venvs/api_server/bin/pip')
      update_python_package("#{APPSCALE_HOME}/common",
                            TaskQueue::TASKQUEUE_PIP)
      update_python_package("#{APPSCALE_HOME}/common",
                            '/opt/appscale_venvs/search2/bin/pip')
    end
    if status.include?('AppControllerClient')
      update_python_package("#{APPSCALE_HOME}/AppControllerClient")
    end
    if status.include?('AdminServer')
      update_python_package("#{APPSCALE_HOME}/AdminServer")
    end
    if status.include?('AppTaskQueue')
      build_taskqueue
    end
    if status.include?('AppDB')
      update_python_package("#{APPSCALE_HOME}/AppDB")
    end
    if status.include?('InfrastructureManager')
      update_python_package("#{APPSCALE_HOME}/InfrastructureManager")
    end
    if status.include?('Hermes')
      update_python_package("#{APPSCALE_HOME}/Hermes")
    end
    if status.include?('APIServer')
      build_api_server
    end
    if status.include?('SearchService2')
      build_search_service2
    end

    # Update Java AppServer
    build_java_appserver if status.include?('AppServer_Java')
  end

  def configure_ejabberd_cert
    # Update APPSCALE_CONFIG_DIR/ejabberd.pem with private key and cert from
    # deployment.
    cert_loc = "#{APPSCALE_CONFIG_DIR}/certs/mycert.pem"
    key_loc = "#{APPSCALE_CONFIG_DIR}/certs/mykey.pem"
    File.open("#{APPSCALE_CONFIG_DIR}/ejabberd.pem", 'w') do |ejabberd_cert|
      File.open("#{cert_loc}", 'r') do |cert|
        ejabberd_cert.write(cert.read)
      end
      File.open("#{key_loc}", 'r') do |key|
        ejabberd_cert.write(key.read)
      end
    end
  end

  def initialize_nodes_in_parallel(must_have, nice_have)
    threads = []
    must_have.each { |slave|
      next if slave.private_ip == my_node.private_ip
      threads << Thread.new {
        initialize_node(slave)
      }
    }

    # If we cannot reconnect with autoscaled nodes, we will have to clean
    # up the state.
    nice_have.each { |slave|
      next if slave.private_ip == my_node.private_ip
      Thread.new {
        Djinn.log_info("Trying to initialize scaled node #{slave}.")
        begin
          Timeout.timeout(SCALEDOWN_THRESHOLD * DUTY_CYCLE * SMALL_WAIT) {
            initialize_node(slave)
          }
        rescue Timeout::Error
          Djinn.log_warn("Couldn't initialize #{slave} in time.")
          APPS_LOCK.synchronize { terminate_node_from_deployment(slave) }
        end
      }
    }

    threads.each { |t| t.join }
    Djinn.log_info("Done initializing must have nodes.")
  end

  def initialize_node(node)
    copy_encryption_keys(node)
    validate_image(node)
    rsync_files(node, @options['keyname'])
    run_user_commands(node, @options['user_commands'])
    start_appcontroller(node)
  end

  def validate_image(node)
    ip = node.private_ip
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

    # Ensure we don't have an old host key for this host.
    if File.exist?(File.expand_path("~/.ssh/known_hosts"))
      Djinn.log_run("ssh-keygen -R #{ip}")
      Djinn.log_run("ssh-keygen -R #{dest_node.public_ip}")
    end

    is_it_cloud = nil
    infrastructure = nil
    @state_change_lock.synchronize {
      is_it_cloud = is_cloud?
      infrastructure = @options['infrastructure']
    }
    if is_it_cloud
      if infrastructure == 'gce'
        # Since GCE v1beta15, SSH keys don't immediately get injected to newly
        # spawned VMs. It takes around 30 seconds, so sleep a bit longer to be
        # sure.
        Djinn.log_debug("Waiting for SSH keys to get injected to #{ip}.")
        Kernel.sleep(60)
      end
      enable_root_login(ip, ssh_key, infrastructure)
    end

    Kernel.sleep(SMALL_WAIT)

    secret_key_loc = "#{APPSCALE_CONFIG_DIR}/secret.key"
    cert_loc = "#{APPSCALE_CONFIG_DIR}/certs/mycert.pem"
    key_loc = "#{APPSCALE_CONFIG_DIR}/certs/mykey.pem"
    ejabberd_cert_loc = "#{APPSCALE_CONFIG_DIR}/ejabberd.pem"

    HelperFunctions.scp_file(secret_key_loc, secret_key_loc, ip, ssh_key)
    HelperFunctions.scp_file(cert_loc, cert_loc, ip, ssh_key)
    HelperFunctions.scp_file(key_loc, key_loc, ip, ssh_key)
    HelperFunctions.scp_file(ejabberd_cert_loc, ejabberd_cert_loc, ip, ssh_key)

    cloud_keys_dir = File.expand_path("#{APPSCALE_CONFIG_DIR}/keys/cloud1")
    make_dir = "mkdir -p #{cloud_keys_dir}"

    HelperFunctions.run_remote_command(ip, make_dir, ssh_key, NO_OUTPUT)
    HelperFunctions.scp_file(ssh_key, "#{APPSCALE_CONFIG_DIR}/ssh.key", ip, ssh_key)

    # Finally, on GCE, we need to copy over the user's credentials, in case
    # nodes need to attach persistent disks.
    return if infrastructure == 'gce'

    client_secrets = "#{APPSCALE_CONFIG_DIR}/client_secrets.json"
    gce_oauth = "#{APPSCALE_CONFIG_DIR}/oauth2.dat"

    if File.exists?(client_secrets)
      HelperFunctions.scp_file(client_secrets, client_secrets, ip, ssh_key)
    end

    if File.exists?(gce_oauth)
      HelperFunctions.scp_file(gce_oauth, gce_oauth, ip, ssh_key)
    end
  end

  # Logs into the named host and alters its ssh configuration to enable the
  # root user to directly log in.
  def enable_root_login(ip, ssh_key, infrastructure)
    options = '-o StrictHostkeyChecking=no -o NumberOfPasswordPrompts=0'

    # Determine which user to login as.
    output = `ssh -i #{ssh_key} #{options} 2>&1 root@#{ip} true`
    match = /Please login as the user "(.+)" rather than the user "root"/.match(output)
    if match.nil?
      if infrastructure == 'azure'
        user_name = 'azureuser'
      else
        user_name = 'ubuntu'
      end
      Djinn.log_warn(
        "Unable to find out what user to login as. Using #{user_name}")
    else
      user_name = match[1]
    end

    backup_keys = 'sudo cp -p /root/.ssh/authorized_keys ' \
        '/root/.ssh/authorized_keys.old'
    Djinn.log_run("ssh -i #{ssh_key} #{options} 2>&1 #{user_name}@#{ip} " \
                      "'#{backup_keys}'")

    merge_keys = 'sudo sed -n ' \
        '"/Please login/d; w/root/.ssh/authorized_keys" ' \
        "~#{user_name}/.ssh/authorized_keys /root/.ssh/authorized_keys.old"
    Djinn.log_run("ssh -i #{ssh_key} #{options} 2>&1 #{user_name}@#{ip} " \
                      "'#{merge_keys}'")
  end

  def rsync_files(dest_node, keyname)
    # Get the keys and address of the destination node.
    ssh_key = dest_node.ssh_key
    ip = dest_node.private_ip
    options = "-e 'ssh -i #{ssh_key}' -a --filter '- *.pyc'"

    to_copy = %w(
      AdminServer
      APIServer
      AppController
      AppControllerClient
      AppDashboard
      AppDB
      AppServer
      AppServer_Java
      AppTaskQueue
      common
      Hermes
      InfrastructureManager
      LogService
      scripts
      SearchService
      SearchService2
      XMPPReceiver
    ).map { |path| File.join(APPSCALE_HOME, path) }
    to_copy.each { |dir|
      if system("rsync #{options} #{dir}/* root@#{ip}:#{dir}") != true
        Djinn.log_warn("Rsync of #{dir} to #{ip} failed!")
      end
    }

    if dest_node.is_compute?
      locations_json = "#{APPSCALE_CONFIG_DIR}/locations-#{keyname}.json"
      loop {
        break if File.exists?(locations_json)
        Djinn.log_warn('Locations JSON file does not exist on head node' \
                       " yet, #{dest_node.private_ip} is waiting ")
        Kernel.sleep(SMALL_WAIT)
      }
      Djinn.log_info("Copying locations.json to #{dest_node.private_ip}")
      HelperFunctions.shell("rsync #{options} #{locations_json} root@#{ip}:#{locations_json}")
    end
  end

  # Writes locations (IP addresses) for the various nodes fulfilling
  # specific roles, in the local filesystems. These files will be updated
  # as the deployment adds or removes nodes.
  def write_locations
    all_ips = []
    load_balancer_ips = []
    login_ip = @options['login']
    master_ips = []
    memcache_ips = []
    search_ips = []
    search2_ips = []
    slave_ips = []
    taskqueue_ips = []
    my_public = my_node.public_ip
    my_private = my_node.private_ip

    # Populate the appropriate list.
    num_of_nodes = 0
    @state_change_lock.synchronize {
      num_of_nodes = @nodes.length.to_s
      @nodes.each { |node|
        all_ips << node.private_ip
        load_balancer_ips << node.private_ip if node.is_load_balancer?
        master_ips << node.private_ip if node.is_db_master?
        memcache_ips << node.private_ip if node.is_memcache?
        search_ips << node.private_ip if node.is_search?
        search2_ips << node.private_ip if node.is_search2?
        slave_ips << node.private_ip if node.is_db_slave?
        taskqueue_ips << node.private_ip if node.is_taskqueue_master? ||
          node.is_taskqueue_slave?
      }
    }
    slave_ips << master_ips[0] if slave_ips.empty?

    # Turn the arrays into string.
    all_ips_content = all_ips.join("\n") + "\n"
    memcache_content = memcache_ips.join("\n") + "\n"
    load_balancer_content = load_balancer_ips.join("\n") + "\n"
    taskqueue_content = taskqueue_ips.join("\n") + "\n"
    login_content = login_ip + "\n"
    master_content = master_ips.join("\n") + "\n"
    search_content = search_ips.join("\n") + "\n"
    search2_content = search2_ips.join("\n") + "\n"
    slaves_content = slave_ips.join("\n") + "\n"

    new_content = all_ips_content + login_content + load_balancer_content +
      master_content + memcache_content + my_public + my_private +
      num_of_nodes + taskqueue_content + search_content + search2_content +
      slaves_content

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

      Djinn.log_info("Deployment public name/IP: #{login_ip}.")
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

      Djinn.log_info("Search2 service locations: #{search2_ips}.")
      unless search2_content.chomp.empty?
        HelperFunctions.write_file('/etc/appscale/search2_ips',
                                   search2_content)
      end
    end
  end

  # Writes new nginx and haproxy configuration files for the App Engine
  # applications hosted in this deployment. Callers should invoke this
  # method whenever there is a change in the number of machines hosting
  # App Engine apps.
  def regenerate_routing_config
    Djinn.log_debug("Regenerating nginx config files for apps.")
    my_private = my_node.private_ip

    @versions_loaded.each { |version_key|
      project_id, service_id, version_id = version_key.split(
        VERSION_PATH_SEPARATOR)
      begin
        version_details = ZKInterface.get_version_details(
          project_id, service_id, version_id)
      rescue VersionNotFound
        next
      end

      http_port = version_details['appscaleExtensions']['httpPort']
      https_port = version_details['appscaleExtensions']['httpsPort']
      proxy_port = version_details['appscaleExtensions']['haproxyPort']
      app_language = version_details['runtime']

      # Check that we have the application information needed to
      # regenerate the routing configuration.
      appservers = []
      unless @app_info_map[version_key].nil? ||
          @app_info_map[version_key]['appservers'].nil?
        Djinn.log_debug(
          "Regenerating nginx config for #{version_key} on http port " \
          "#{http_port}, https port #{https_port}, and haproxy port " \
          "#{proxy_port}.")

        # Let's see if we already have any AppServers running for this
        # application. We count also the ones we need to terminate.
        @app_info_map[version_key]['appservers'].each { |location|
          _, port = location.split(":")
          next if Integer(port) < 0
          appservers << location
        }
      end

      if appservers.empty?
        # If no AppServer is running, we clear the routing and the crons.
        Djinn.log_debug(
          "Removing routing for #{version_key} since no AppServer is running.")
        Nginx.remove_version(version_key)
      else
        begin
          # Make sure we have the latest revision.
          revision_key = [version_key,
            version_details['revision'].to_s].join(VERSION_PATH_SEPARATOR)
          fetch_revision(revision_key)

          # And grab the application static data.
          static_handlers = HelperFunctions.parse_static_data(
            version_key, false)
        rescue => except
          except_trace = except.backtrace.join("\n")
          Djinn.log_debug("regenerate_routing_config: parse_static_data " \
            "exception from #{version_key}: #{except_trace}.")
          # This specific exception may be a JSON parse error.
          error_msg = "ERROR: Unable to parse app.yaml file for " \
                      "#{version_key}. Exception of #{except.class} with " \
                      "message #{except.message}"
          place_error_app(version_key, error_msg)
          static_handlers = []
        end

        Nginx.write_fullproxy_version_config(
          version_key, http_port, https_port, @options['login'], my_private,
          proxy_port, static_handlers, get_load_balancer.private_ip,
          app_language)
      end
    }
    Djinn.log_debug("Done updating nginx config files.")
  end

  def my_node
    @state_change_lock.synchronize { find_me_in_locations } if @my_index.nil?

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
    unless my_node.disk
      Djinn.log_run("mkdir -p #{PERSISTENT_MOUNT_POINT}/apps")
      return
    end

    imc = InfrastructureManagerClient.new(@@secret, my_node.private_ip)
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
        Djinn.log_info("Device #{device_name} does not exist - waiting for " \
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
    mount_output = Djinn.log_run("mount -t ext4 #{device_name} " \
      "#{PERSISTENT_MOUNT_POINT} 2>&1")
    if mount_output.empty?
      Djinn.log_info("Mounted persistent disk #{device_name}, without " \
        "needing to format it.")
    else
      Djinn.log_info("Formatting persistent disk #{device_name}.")
      Djinn.log_run("mkfs.ext4 -F #{device_name}")
      Djinn.log_info("Mounting persistent disk #{device_name}.")
      Djinn.log_run("mount -t ext4 #{device_name} #{PERSISTENT_MOUNT_POINT}" \
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
  def initialize_server
    HAProxy.initialize_config(@options['lb_connect_timeout'])
    Djinn.log_info("HAProxy configured.")

    if not Nginx.is_running?
      Nginx.initialize_config
      Nginx.start
      Djinn.log_info("Nginx configured and started.")
    else
      Djinn.log_info("Nginx already configured and running.")
    end

    # The HAProxy process needs at least one configured service to start. The
    # UAServer is configured first to satisfy this condition.
    configure_uaserver

    # HAProxy must be running so that the UAServer can be accessed.
    HAProxy.services_start

    # Volume is mounted, let's finish the configuration of static files.
    if my_node.is_shadow? and not my_node.is_compute?
      write_app_logrotate
      Djinn.log_info("Copying logrotate script for centralized app logs")
    end

    write_locations
    Djinn.log_run("bash #{APPSCALE_HOME}/firewall.conf") if FIREWALL_IS_ON
    write_zookeeper_locations
  end

  # Sets up logrotate for this node's centralized app logs.
  # This method is called only when the compute role does not run
  # on the head node.
  def write_app_logrotate
    template_dir = File.join(File.dirname(__FILE__),
                             "../common/appscale/common/templates")
    FileUtils.cp("#{template_dir}/#{APPSCALE_APP_LOGROTATE}",
      "#{LOGROTATE_DIR}/appscale-app")
  end

  # Runs any commands provided by the user in their AppScalefile on the given
  # machine.
  #
  # Args:
  # - node: A NodeInfo that represents the machine where the given commands
  #   should be executed.
  def run_user_commands(node, user_commands)
    if user_commands.class == String
      begin
        commands = JSON.load(user_commands)
      rescue JSON::ParserError
        commands = user_commands
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

  def set_appcontroller_monit
    Djinn.log_debug("Configuring AppController monit.")
    service = `which service`.chomp
    start_cmd = "#{service} appscale-controller start"
    pidfile = '/var/run/appscale/controller.pid'
    stop_cmd = "/sbin/start-stop-daemon --stop --pidfile #{pidfile} --retry=TERM/30/KILL/5"

    # Let's make sure we don't have 2 roles monitoring the controller.
    FileUtils.rm_rf("/etc/monit/conf.d/controller-17443.cfg")

    begin
      MonitInterface.start_daemon(:controller, start_cmd, stop_cmd, pidfile)
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

    layout = nil
    options = nil
    @state_change_lock.synchronize {
      layout = Djinn.convert_location_class_to_json(@nodes)
      options = JSON.dump(@options)
    }
    begin
      result = acc.set_parameters(layout, options)
    rescue FailedNodeException => e
      @state = "Couldn't set parameters on node at #{ip} for #{e.message}."
      HelperFunctions.log_and_crash(@state, WAIT_TO_CRASH)
    end
    Djinn.log_info("Parameters set on node at #{ip} returned #{result}.")
  end

  def start_admin_server
    Djinn.log_info('Starting AdminServer')
    script = `which appscale-admin`.chomp
    nginx_port = 17441
    service_port = 17442
    start_cmd = "#{script} serve -p #{service_port}"
    start_cmd << ' --verbose' if @options['verbose'].downcase == 'true'
    MonitInterface.start(:admin_server, start_cmd, nil,
                         {'PATH' => ENV['PATH']})
    if my_node.is_load_balancer?
      Nginx.add_service_location('appscale-administration', my_node.private_ip,
                                 service_port, nginx_port, '/')
    end
  end

  def start_memcache
    @state = "Starting up memcache"
    Djinn.log_info("Starting up memcache")
    port = 11211
    start_cmd = "/usr/bin/memcached -m 64 -p #{port} -u root"
    MonitInterface.start(:memcached, start_cmd)
  end

  def stop_memcache
    MonitInterface.stop(:memcached) if MonitInterface.is_running?(:memcached)
  end

  def start_ejabberd
    @state = "Starting up XMPP server"
    Djinn.log_run("rm -f /var/lib/ejabberd/*")
    Ejabberd.write_config_file(@options['login'], my_node.private_ip)
    Ejabberd.update_ctl_config

    # Monit does not have an entry for ejabberd yet. This allows a restart
    # with the new configuration if it is already running.
    `service ejabberd stop`

    Ejabberd.start
  end

  def stop_ejabberd
    Ejabberd.stop
  end

  # Create the system user used to start and run system's applications.
  def create_appscale_user
    uac = UserAppClient.new(my_node.private_ip, @@secret)
    password = SecureRandom.base64

    begin
      retries ||= 0
      result = uac.commit_new_user(APPSCALE_USER, password, "app")
      Djinn.log_info("Created/confirmed system user: (#{result})")
    rescue UserExists
      Djinn.log_info('System user already exists')
    rescue InternalError, FailedNodeException
      Djinn.log_warn('Failed to create a new user')
      retries += 1
      if retries < RETRIES
        sleep(SMALL_WAIT)
        retry
      else
        raise
      end
    end
  end

  # Deploy the dashboard by making a request to the AdminServer.
  def deploy_dashboard(source_archive)
    # Allow fewer dashboard instances for small deployments.
    min_dashboards = [3, get_all_compute_nodes.length].min

    archive_md5 = Digest::MD5.file(source_archive).hexdigest

    version = {:deployment => {:zip => {:sourceUrl => source_archive}},
               :id => DEFAULT_VERSION,
               :instanceClass => 'F4',
               :runtime => AppDashboard::APP_LANGUAGE,
               :threadsafe => true,
               :automaticScaling => {:minTotalInstances => min_dashboards},
               :appscaleExtensions => {
                 :httpPort => AppDashboard::LISTEN_PORT,
                 :httpsPort => AppDashboard::LISTEN_SSL_PORT,
                 :md5 => archive_md5
               }}
    endpoint = ['v1', 'apps', AppDashboard::APP_NAME,
                'services', DEFAULT_SERVICE, 'versions'].join('/')
    uri = URI("http://#{my_node.private_ip}:#{ADMIN_SERVER_PORT}/#{endpoint}")
    headers = {'Content-Type' => 'application/json',
               'AppScale-Secret' => @@secret,
               'AppScale-User' => APPSCALE_USER}
    request = Net::HTTP::Post.new(uri.path, headers)
    request.body = JSON.dump(version)
    loop do
      begin
        response = Net::HTTP.start(uri.hostname, uri.port) do |http|
          http.request(request)
        end
        if response.code != '200'
          HelperFunctions.log_and_crash(
            "AdminServer was unable to deploy dashboard: #{response.body}")
        end
        break
      rescue Errno::ECONNREFUSED, Errno::ETIMEDOUT, Net::ReadTimeout => error
        Djinn.log_warn(
          "Error when deploying dashboard: #{error.message}. Trying again.")
        sleep(SMALL_WAIT)
      end
    end

    # Update cron jobs for the dashboard.
    endpoint = "api/cron/update?app_id=#{AppDashboard::APP_NAME}"
    uri = URI("http://#{my_node.private_ip}:#{ADMIN_SERVER_PORT}/#{endpoint}")
    cron_yaml = File.read(
      File.join(APPSCALE_HOME, 'AppDashboard', 'cron.yaml'))
    headers = {'AppScale-Secret' => @@secret}
    request = Net::HTTP::Post.new("/#{endpoint}", headers)
    request.body = cron_yaml
    loop do
      begin
        response = Net::HTTP.start(uri.hostname, uri.port) do |http|
          http.request(request)
        end
        break if response.code == '200'
        Djinn.log_warn(
          "Error updating dashboard cron: #{response.body}. Trying again.")
        sleep(SMALL_WAIT)
      rescue Errno::ECONNREFUSED, Errno::ETIMEDOUT, Net::ReadTimeout => error
        Djinn.log_warn(
          "Error updating dashboard cron: #{error.message}. Trying again.")
        sleep(SMALL_WAIT)
      end
    end
  end

  # Start the AppDashboard web service which allows users to login, upload
  # and remove apps, and view the status of the AppScale deployment. Other
  # nodes will need to delete the old source since we regenerate each
  # 'up'.
  def prep_app_dashboard
    @state = "Preparing AppDashboard"
    Djinn.log_info("Preparing AppDashboard")

    my_public = my_node.public_ip
    my_private = my_node.private_ip

    datastore_location = [get_load_balancer.private_ip,
                          DatastoreServer::PROXY_PORT].join(':')
    taskqueue_location = [get_load_balancer.private_ip,
                          TaskQueue::HAPROXY_PORT].join(':')
    source_archive = AppDashboard.prep(
      my_private, PERSISTENT_MOUNT_POINT, datastore_location,
      taskqueue_location)

    self.deploy_dashboard(source_archive)
  end

  # Stop the AppDashboard web service.
  def stop_app_dashboard
    Djinn.log_info("Shutting down AppDashboard")
    AppDashboard.stop
  end

  def start_shadow
    Djinn.log_info("Starting Shadow role")
  end

  def stop_shadow
    Djinn.log_info("Stopping Shadow role")
  end

  #
  # Swaps out a version with one that relays an error message to the developer.
  # It deletes the existing version source and places a templated app that
  # prints out the given error message.
  #
  # Args:
  #   version_key: Name of version to construct an error application for
  #   err_msg: A String message that will be displayed as
  #            the reason why we couldn't start their application.
  def place_error_app(version_key, err_msg)
    Djinn.log_error(
      "Placing error application for #{version_key} because of: #{err_msg}")

    project_id, service_id, version_id = version_key.split(
      VERSION_PATH_SEPARATOR)
    begin
      version_details = ZKInterface.get_version_details(
        project_id, service_id, version_id)
    rescue VersionNotFound
      # If the version does not exist, do not place an error app.
      return
    end
    language = version_details['runtime']
    revision_key = [version_key, version_details['revision'].to_s].join(
      VERSION_PATH_SEPARATOR)

    ea = ErrorApp.new(revision_key, err_msg)
    ea.generate(language)
  end


  # This function ensures that applications we are not aware of (that is
  # they are not accounted for) will be terminated and, potentially old
  # sources, will be removed. Must be called under APPS_LOCK.
  def check_stopped_apps
    Djinn.log_debug("Checking applications that have been stopped.")
    begin
      zookeeper_versions = ZKInterface.get_versions
    rescue FailedZooKeeperOperationException => e
      Djinn.log_warn("Failed to get list of versions in zookeeper. Error: " \
        "#{e}.message")
      return
    end
    Djinn.log_debug("check_stopped_apps: Versions running: #{zookeeper_versions}")
    removed_versions = []

    # Remove old crontab and syslog configuration. Only the master node
    # should do it, but since the role could be assumed by different
    # nodes, we make sure the removal are idempotent and we run it on all
    # nodes running this method.
    CronHelper.list_app_crontabs.each { |app|
      match = app.match(CronHelper::PROJECT_ID_REGEX)
      next if match.nil?

      project_id = match.captures.first
      default_version_key = "#{project_id}_#{DEFAULT_SERVICE}_#{DEFAULT_VERSION}"

      next if zookeeper_versions.include?(default_version_key)

      next if RESERVED_APPS.include?(project_id)

      Djinn.log_info(
        "#{default_version_key} is no longer running: removing crontabs.")
      CronHelper.clear_app_crontab(project_id)
      removed_versions << default_version_key
    }
    Dir.glob("/etc/rsyslog.d/10-*_*_*.conf").each { |app|
      match = app.match(/10-(.*_.*_.*).conf/)
      next if match.nil?

      version_key = match.captures.first
      next if zookeeper_versions.include?(version_key)

      project_id = version_key.split(VERSION_PATH_SEPARATOR).first
      next if RESERVED_APPS.include?(project_id)

      Djinn.log_info(
        "#{version_key} is no longer running: removing log configuration.")
      begin
        FileUtils.rm(get_rsyslog_conf(version_key))
        HelperFunctions.shell("service rsyslog restart")
      rescue Errno::ENOENT, Errno::EACCES
        Djinn.log_debug("Old syslog for #{version_key} wasn't there.")
      end
      removed_versions << version_key
    }

    # Load balancers have to adjust nginx and haproxy to remove the
    # application routings.
    if my_node.is_load_balancer?
      MonitInterface.running_xmpp.each { |xmpp_app|
        match = xmpp_app.match(/xmpp-(.*)/)
        next if match.nil?

        project_id = match.captures.first
        default_version_key = "#{project_id}_#{DEFAULT_SERVICE}_#{DEFAULT_VERSION}"
        next if zookeeper_versions.include?(default_version_key)

        next if RESERVED_APPS.include?(project_id)

        Djinn.log_info(
          "#{default_version_key} is no longer running: stopping xmpp for application.")
        stop_xmpp_for_app(project_id)
        removed_versions << default_version_key
      }
      Nginx.list_sites_enabled.each { |site|
        match = site.match(Nginx::VERSION_KEY_REGEX)
        next if match.nil?

        version_key = match.captures.first
        next if zookeeper_versions.include?(version_key)

        project_id = version_key.split(VERSION_PATH_SEPARATOR).first
        next if RESERVED_APPS.include?(project_id)

        Djinn.log_info(
          "#{version_key} is no longer running: removing Nginx state.")
        Nginx.remove_version(version_key)
        removed_versions << version_key
      }
    end

    # If this node has any information about AppServers for this version,
    # clear that information out.
    if my_node.is_shadow?
      removed_versions.each { |version_key|
        @app_info_map.delete(version_key)
      }
    end

    # Remove versions from versions_loaded.
    @versions_loaded = @versions_loaded - removed_versions
  end

  # Small utility function that returns the full path for the rsyslog
  # configuration for each version.
  #
  # Args:
  #   version_key: A String containing the version key.
  # Returns:
  #   path: A String with the path to the rsyslog configuration file.
  def get_rsyslog_conf(version_key)
    return "/etc/rsyslog.d/10-#{version_key}.conf"
  end

  # Performs all of the preprocessing needed to start a version on this node.
  # This method then starts the actual version by calling the AppManager.
  #
  # Args:
  #   version_key: A String containing the version key for the app to start.
  def setup_appengine_version(version_key)
    @state = "Setting up AppServers for #{version_key}"
    Djinn.log_debug(
      "setup_appengine_version: got a new version #{version_key}.")

    project_id, service_id, version_id = version_key.split(
      VERSION_PATH_SEPARATOR)
    # Let's create an entry for the application if we don't already have it.
    @app_info_map[version_key] = {} if @app_info_map[version_key].nil?

    if @app_info_map[version_key]['appservers'].nil?
      @app_info_map[version_key]['appservers'] = []
    end
    Djinn.log_debug("setup_appengine_version: info for #{version_key}: " \
                    "#{@app_info_map[version_key]}.")

    begin
      version_details = ZKInterface.get_version_details(
        project_id, service_id, version_id)
    rescue VersionNotFound
      Djinn.log_debug(
        "Version #{version_key} not found, exiting setup_appengine_version")
      return
    end

    nginx_port = version_details['appscaleExtensions']['httpPort']
    https_port = version_details['appscaleExtensions']['httpsPort']
    proxy_port = version_details['appscaleExtensions']['haproxyPort']

    port_file = "#{APPSCALE_CONFIG_DIR}/port-#{version_key}.txt"
    HelperFunctions.write_file(port_file, nginx_port.to_s)
    Djinn.log_debug("#{version_key} will be using nginx port #{nginx_port}, " \
                    "https port #{https_port}, and haproxy port #{proxy_port}")

    # Setup rsyslog to store application logs.
    app_log_config_file = get_rsyslog_conf(version_key)
    begin
      existing_app_log_config = HelperFunctions.read_file(app_log_config_file)
    rescue Errno::ENOENT
      existing_app_log_config = ''
    end

    rsyslog_prop = ':syslogtag'
    rsyslog_version = Gem::Version.new(`rsyslogd -v`.split[1].chomp(','))
    rsyslog_prop = ':programname' if rsyslog_version < Gem::Version.new('8.12')
    rsyslog_propval = "app_#{Digest::SHA1.hexdigest(version_key)[0...28]}"

    app_log_template = HelperFunctions.read_file(RSYSLOG_TEMPLATE_LOCATION)
    app_log_config = app_log_template.gsub('{property}', rsyslog_prop)
    app_log_config = app_log_config.gsub('{property_value}', rsyslog_propval)
    app_log_config = app_log_config.gsub('{version}', version_key)
    unless existing_app_log_config == app_log_config
      Djinn.log_info("Installing log configuration for #{version_key}.")
      HelperFunctions.write_file(app_log_config_file, app_log_config)
      HelperFunctions.shell("service rsyslog restart")
    end

    if service_id == DEFAULT_SERVICE && version_id == DEFAULT_VERSION
      begin
        start_xmpp_for_app(project_id)
      rescue FailedNodeException
        Djinn.log_warn("Failed to start xmpp for application #{project_id}")
      end
    end

    unless @versions_loaded.include?(version_key)
      @versions_loaded << version_key
    end
  end

  # Updates @app_info_map with registered instances. This must be called under
  # APPS_LOCK.
  #
  # Args:
  #   version_key: A string specifying the version key to update.
  def update_registered_instances(version_key)
    begin
      zk_instances = ZKInterface.get_children(
        "/appscale/instances_by_version/#{version_key}")
    rescue FailedZooKeeperOperationException
      Djinn.log_warn('Unable to fetch list of registered instances.')
      return
    end

    @app_info_map[version_key] = {} unless @app_info_map.key?(version_key)
    unless @app_info_map[version_key].key?('appservers')
      @app_info_map[version_key]['appservers'] = []
    end
    known_instances = @app_info_map[version_key]['appservers']

    # Replace instance assignments with any new registered instances.
    zk_instances.each { |instance_key|
      next if known_instances.include?(instance_key)

      # Find and remove an entry for this AppServer node and app.
      ip = instance_key.split(':')[0]
      match = known_instances.index("#{ip}:-1")
      if match
        known_instances.delete_at(match)
        known_instances << instance_key
      else
        Djinn.log_warn("Ignoring unassigned instance: #{instance_key}.")
      end
    }

    # Account for instances that have been stopped.
    known_instances.delete_if { |instance_key|
      pending = instance_key.split(':')[-1] == '-1'
      registered = zk_instances.include?(instance_key)
      !pending && !registered
    }
  end


  # Adds or removes AppServers and/or nodes to the deployment, depending
  # on the statistics of the application and the loads of the various
  # services.
  def scale_deployment
    begin
      configured_versions = ZKInterface.get_versions
    rescue FailedZooKeeperOperationException
      Djinn.log_warn(
        'Unable to fetch configured versions when scaling appservers')
      return
    end

    configured_versions.each { |version_key|
      next unless @versions_loaded.include?(version_key)

      update_registered_instances(version_key)
      initialize_scaling_info_for_version(version_key)

      # Get the desired changes in the number of AppServers.
      delta_appservers = get_scaling_info_for_version(version_key)
      if delta_appservers > 0
        # try_to_scale_up returns back the number of instances desired
        # based on the current application requirements (memory and cpu)
        # and the instance_type we have for autoscaling.
        scale_up_instances(try_to_scale_up(version_key, delta_appservers))
      elsif delta_appservers < 0
        try_to_scale_down(version_key, delta_appservers.abs)
        scale_down_instances
      end
    }
  end


  # Adds additional nodes to the deployment, depending on the load of the
  # application and the additional AppServers we need to accomodate.
  #
  # Args:
  #   needed_nodes: The number of additional nodes desired.
  def scale_up_instances(needed_nodes)
    # Here we count the number of machines we need to spawn, and the roles
    # we need.
    vms_to_spawn = 0
    roles_needed = {}
    vm_scaleup_capacity = Integer(@options['max_machines']) - @nodes.length

    Djinn.log_info("Asked to start #{needed_nodes} more VMs.")

    needed_nodes.downto(1) {
      vms_to_spawn += 1
      if vm_scaleup_capacity < vms_to_spawn
        Djinn.log_warn("Only have capacity to start #{vm_scaleup_capacity}" \
          " vms, so spawning only maximum allowable nodes.")
        break
      end
      roles_needed["compute"] = [] unless roles_needed["compute"]
      roles_needed["compute"] << "node-#{vms_to_spawn}"
    }

    # Check if we need to spawn VMs and the InfrastructureManager is
    # available to do so.
    return unless vms_to_spawn > 0

    # Check if we haven't recently scaled.
    if Time.now.to_i - @last_scaling_time < (SCALEUP_THRESHOLD * DUTY_CYCLE)
      Djinn.log_info("Not scaling up right now, as we recently scaled " \
                     "up or down.")
      return
    end

    # Check if there is another thread already working.
    if SCALE_LOCK.locked?
      Djinn.log_debug("Another thread is already working with the InfrastructureManager.")
      return
    end

    Thread.new {
      SCALE_LOCK.synchronize {
        Djinn.log_info("Starting #{vms_to_spawn} more VMs.")

        result = start_roles_on_nodes(JSON.dump(roles_needed), @@secret)
        if result != "OK"
          Djinn.log_error("Was not able to add nodes because: #{result}.")
        else
          @last_scaling_time = Time.now.to_i
          Djinn.log_info("Added the following nodes: #{roles_needed}.")
        end
      }
    }
  end

  # Removes autoscaled nodes from the deployment as long as they are not running
  # any AppServers and the minimum number of user specified machines are still
  # running in the deployment.
  def scale_down_instances
    num_scaled_down = 0
    # If we are already at the minimum number of machines that the user specified,
    # then we do not have the capacity to scale down.
    max_scale_down_capacity = @nodes.length - Integer(@options['min_machines'])
    if max_scale_down_capacity <= 0
      Djinn.log_debug("We are already at the minimum number of user specified machines," \
        "so will not be scaling down")
      return
    end

    # Also, don't scale down if we just scaled up or down.
    if Time.now.to_i - @last_scaling_time < (SCALEDOWN_THRESHOLD *
        SCALE_TIME_MULTIPLIER * DUTY_CYCLE)
      Djinn.log_info("Not scaling down right now, as we recently scaled " \
        "up or down.")
      return
    end

    if SCALE_LOCK.locked?
      Djinn.log_debug("Another thread is already working with the InfrastructureManager.")
      return
    end

    Thread.new {
      SCALE_LOCK.synchronize {
        # Look through an array of autoscaled nodes and check if any of the
        # machines are not running any AppServers and need to be downscaled.
        get_autoscaled_nodes.reverse_each { |node|
          break if num_scaled_down == max_scale_down_capacity

          hosted_apps = []
          @versions_loaded.each { |version_key|
            @app_info_map[version_key]['appservers'].each { |location|
              host, port = location.split(":")
              if host == node.private_ip
                hosted_apps << "#{version_key}:#{port}"
              end
            }
          }

          unless hosted_apps.empty?
            Djinn.log_debug("The node #{node.private_ip} has these AppServers " \
              "running: #{hosted_apps}")
            next
          end

          # Right now, only the autoscaled machines are started with just the
          # compute role, so we check specifically for that during downscaling
          # to make sure we only downscale the new machines added.
          node_to_remove = nil
          if node.roles == ['compute']
            Djinn.log_info("Removing node #{node}")
            node_to_remove = node
          end

          num_terminated = terminate_node_from_deployment(node_to_remove)
          num_scaled_down += num_terminated
        }
      }

      # Make sure we have the proper list of blobservers configured.
      update_blob_servers
    }
  end

  # Removes the specified node from the deployment and terminates
  # the instance from the cloud.
  #
  # Args:
  #   node_to_remove: A node instance, to be terminated and removed
  #     from this deployment.
  def terminate_node_from_deployment(node_to_remove)
    if node_to_remove.nil?
      Djinn.log_warn("Tried to scale down but couldn't find a node to remove.")
      return 0
    end

    # Terminate instance if we are in cloud.
    if is_cloud?
      imc = InfrastructureManagerClient.new(@@secret, my_node.private_ip)
      begin
        imc.terminate_instances(@options, node_to_remove.instance_id)
      rescue FailedNodeException
        Djinn.log_warn("Failed to call terminate_instances")
        return 0
      rescue AppScaleException
        Djinn.log_warn("Failed to terminate #{node_to_remove}. Not removing it.")
        return 0
      end
    end

    # And then clean up the internal state.
    remove_node_from_local_and_zookeeper(node_to_remove.private_ip)
    to_remove = {}
    @app_info_map.each { |version_key, info|
      next if info['appservers'].nil?

      info['appservers'].each { |location|
        host = location.split(":")[0]
        if host == node_to_remove.private_ip
          to_remove[version_key] = [] if to_remove[version_key].nil?
          to_remove[version_key] << location
        end
      }
    }
    to_remove.each { |version_key, locations|
      locations.each { |location|
        @app_info_map[version_key]['appservers'].delete(location)
      }
    }

    @last_scaling_time = Time.now.to_i
    return 1
  end

  # Sets up information about the request rate and number of requests in
  # haproxy's queue for the given version.
  #
  # Args:
  #   version_key: The name of the version to set up scaling info
  #   force: A boolean value that indicates if we should reset the scaling
  #     info even in the presence of existing scaling info.
  def initialize_scaling_info_for_version(version_key, force=false)
    return if @initialized_versions[version_key] and !force

    @current_req_rate[version_key] = 0
    @total_req_seen[version_key] = 0
    @last_sampling_time[version_key] = Time.now.to_i
    @last_decision[version_key] = 0 unless @last_decision.key?(version_key)
    @initialized_versions[version_key] = true
  end

  # Get the effective min/max instances for a version
  #
  # Args:
  #   version_details: The version details from zookeeper
  def get_min_max_from_version_details(version_details)
    manual_scaling = version_details.fetch('manualScaling', {})
    if manual_scaling.fetch('instances', nil)
      if version_details.fetch('servingStatus', 'SERVING') == 'STOPPED'
        min = 0
        max = 0
      else
        min = manual_scaling.fetch('instances')
        max = min
      end
    else
      scaling_params = version_details.fetch('automaticScaling', {})
      if scaling_params.fetch('standardSchedulerSettings', nil)
        min_max_params = scaling_params.fetch('standardSchedulerSettings', {})
        min_param = 'minInstances'
        max_param = 'maxInstances'
      else
        min_max_params = scaling_params
        min_param = 'minTotalInstances'
        max_param = 'maxTotalInstances'
      end
      min = min_max_params.fetch(min_param,
                                 Integer(@options['default_min_appservers']))
      max = min_max_params.fetch(max_param,
                                 Integer(@options['default_max_appservers']))
    end
    return min, max
  end

  # Queries haproxy to see how many requests are queued for a given version
  # and how many requests are served at a given time.
  # Args:
  #   version_key: The name of the version to get info for.
  # Returns:
  #   an Integer: the number of AppServers desired (a positive number
  #     means we want more, a negative that we want to remove some, and 0
  #     for no changes).
  def get_scaling_info_for_version(version_key)
    project_id, service_id, version_id, = version_key.split(
      VERSION_PATH_SEPARATOR)
    begin
      version_details = ZKInterface.get_version_details(
        project_id, service_id, version_id)
    rescue VersionNotFound
      Djinn.log_info("Not scaling app #{version_key} since we aren't " \
                     'hosting it anymore.')
      return 0
    end
    min, max = get_min_max_from_version_details(version_details)

    # Let's make sure we have the minimum number of AppServers running.
    num_appservers = 0
    unless @app_info_map[version_key]['appservers'].nil?
      num_appservers = @app_info_map[version_key]['appservers'].length
    end
    Djinn.log_debug("Evaluating #{version_key} for scaling " \
                    "(#{num_appservers} AppServers allocated).")

    if num_appservers < min
      Djinn.log_info(
        "#{version_key} needs #{min - num_appservers} more AppServers.")
      @last_decision[version_key] = 0
      return min - num_appservers
    end

    # We only run @options['default_min_appservers'] AppServers per application
    # if austoscale is disabled. No need to print anything here since we
    # print log about disabled autoscale at intervals with the stats.
    return 0 if @options['autoscale'].downcase != "true"

    # If there are no instances then there is no load to decide scaling
    # activity, a manual start is required when using manual scaling
    return 0 if num_appservers == 0 and max == 0

    # We need the haproxy stats to decide upon what to do.
    total_requests_seen, total_req_in_queue, current_sessions,
      time_requests_were_seen = get_application_load_stats(version_key)

    if time_requests_were_seen == :no_stats
      Djinn.log_warn("Didn't see any request data - not sure whether to scale up or down.")
      return 0
    end

    update_request_info(version_key, total_requests_seen,
                        time_requests_were_seen, total_req_in_queue)

    # Check if we are already at the maximum allowed.
    if num_appservers > max
      Djinn.log_info("Enforcing maximum number of AppServers (#{max})" \
                     " for #{version_key}.")
      return max - num_appservers
    end

    # We have seen the current_sessions to amply fluctuate from reading to
    # reading, so we smooth it out picking the max we have seen over the
    # last 10 reads.
    @curr_sessions_list.delete_at(0)  if @curr_sessions_list.length >= 10
    @curr_sessions_list << current_sessions
    scale_sessions = @curr_sessions_list.max
    Djinn.log_debug("Using #{scale_sessions} as current_sessions value " \
                    "for scaling #{version_key}.")

    allow_concurrency = version_details.fetch('threadsafe', true)
    current_load = calculate_current_load(num_appservers, scale_sessions,
                                          allow_concurrency)
    if current_load >= MAX_LOAD_THRESHOLD
      if num_appservers == max
        Djinn.log_info("Reached maximum allowed number of AppServers " \
                       "for #{version_key}.")
        return 0
      end
      appservers_to_scale = calculate_appservers_needed(
          num_appservers, scale_sessions, allow_concurrency)

      # Let's make sure we don't get over the user define maximum.
      if num_appservers + appservers_to_scale > max
        appservers_to_scale = max - num_appservers
      end

      Djinn.log_debug("The deployment has reached its maximum load " \
                      "threshold for #{version_key} - Advising that we " \
                      "scale up #{appservers_to_scale} AppServers.")
      return appservers_to_scale

    elsif current_load <= MIN_LOAD_THRESHOLD
      downscale_cooldown = SCALEDOWN_THRESHOLD * DUTY_CYCLE
      if Time.now.to_i - @last_decision[version_key] < downscale_cooldown
        Djinn.log_debug(
          "Not enough time has passed to scale down #{version_key}")
        return 0
      end
      appservers_to_scale = calculate_appservers_needed(
          num_appservers, scale_sessions, allow_concurrency)
      Djinn.log_debug("The deployment is below its minimum load threshold " \
                      "for #{version_key} - Advising that we scale down " \
                      "#{appservers_to_scale.abs} AppServers.")
      return appservers_to_scale
    else
      Djinn.log_debug("The deployment is within the desired range of load " \
                      "for #{version_key} - Advising that there is no need " \
                      "to scale currently.")
      return 0
    end
  end

  # Calculates the current load of the deployment based on the number of
  # running AppServers, its max allowed threaded connections and current
  # handled sessions.
  # Formula: Load = Current Sessions / (No of AppServers * Max conn)
  #
  # Args:
  #   num_appservers: The total number of AppServers running for the app.
  #   curr_sessions: The number of current sessions from HAProxy stats.
  #   allow_concurrency: A boolean indicating that AppServers can handle
  #     concurrent connections.
  # Returns:
  #   A decimal indicating the current load.
  def calculate_current_load(num_appservers, curr_sessions, allow_concurrency)
    max_connections = allow_concurrency ? HAProxy::MAX_APPSERVER_CONN : 1
    max_sessions = num_appservers * max_connections
    return curr_sessions.to_f / max_sessions
  end

  # Calculates the additional number of AppServers needed to be scaled up in
  # order achieve the desired load.
  # Formula: No of AppServers = Current sessions / (Load * Max conn)
  #
  # Args:
  #   num_appservers: The total number of AppServers running for the app.
  #   curr_sessions: The number of current sessions from HAProxy stats.
  #   allow_concurrency: A boolean indicating that AppServers can handle
  #     concurrent connections.
  # Returns:
  #   A number indicating the number of additional AppServers to be scaled up.
  def calculate_appservers_needed(num_appservers, curr_sessions,
                                  allow_concurrency)
    max_conn = allow_concurrency ? HAProxy::MAX_APPSERVER_CONN : 1
    desired_appservers = curr_sessions.to_f / (DESIRED_LOAD * max_conn)
    appservers_to_scale = desired_appservers.ceil - num_appservers
    return appservers_to_scale
  end

  # Updates internal state about the number of requests seen for the given
  # version, as well as how many requests are currently enqueued for it.
  #
  # Args:
  #   version_key: A String that indicates a version key.
  #   total_requests_seen: An Integer that indicates how many requests haproxy
  #     has received for the given application since we reloaded it (which
  #     occurs when we start the app or add/remove AppServers).
  #   time_requests_were_seen: An Integer that represents the epoch time when we
  #     got request info from haproxy.
  #   total_req_in_queue: An Integer that represents the current number of
  #     requests waiting to be served.
  def update_request_info(version_key, total_requests_seen,
                          time_requests_were_seen, total_req_in_queue)
    requests_since_last_sampling = total_requests_seen - @total_req_seen[version_key]
    time_since_last_sampling = time_requests_were_seen - @last_sampling_time[version_key]
    if time_since_last_sampling.zero?
      time_since_last_sampling = 1
    end

    average_request_rate = Float(requests_since_last_sampling) / Float(time_since_last_sampling)
    if average_request_rate < 0
      Djinn.log_info("Saw negative request rate for #{version_key}, so " \
                     "resetting our haproxy stats for this version.")
      initialize_scaling_info_for_version(version_key, true)
      return
    end
    Djinn.log_debug("Stats for #{version_key}: Total requests " \
                    "#{total_requests_seen}, requests in queue " \
                    "#{total_req_in_queue}, average rate " \
                    "#{average_request_rate}, time #{time_requests_were_seen}")
    @average_req_rate[version_key] = average_request_rate
    @current_req_rate[version_key] = total_req_in_queue
    @total_req_seen[version_key] = total_requests_seen
    @last_sampling_time[version_key] = time_requests_were_seen
  end

  # Determines the amount of memory already allocated for instances on each
  # machine.
  #
  # Returns:
  #   A hash mapping locations to memory allocated in MB.
  def get_allocated_memory
    allocated_memory = {}
    @app_info_map.each_pair { |version_key, app_info|
      next if app_info['appservers'].nil?

      project_id, service_id, version_id = version_key.split(
        VERSION_PATH_SEPARATOR)
      max_app_mem = Integer(@options['default_max_appserver_memory'])
      begin
        version_details = ZKInterface.get_version_details(
          project_id, service_id, version_id)
      rescue VersionNotFound
        Djinn.log_warn(
          "#{version_key} not found when considering memory usage")
        version_details = {}
      end

      if version_details.key?('instanceClass')
        instance_class = version_details['instanceClass'].to_sym
        max_app_mem = INSTANCE_CLASSES.fetch(instance_class, max_app_mem)
      end

      app_info['appservers'].each { |location|
        host = location.split(':')[0]
        allocated_memory[host] = 0 unless allocated_memory.key?(host)
        allocated_memory[host] += max_app_mem
      }
    }
    return allocated_memory
  end

  # Retrieves a list of hosts that are running instances for a version.
  #
  # Args:
  #   version_key: A string specifying a version key.
  # Returns:
  #   A set of IP addresses.
  def get_hosts_for_version(version_key)
    current_hosts = Set.new
    if @app_info_map.key?(version_key) &&
        @app_info_map[version_key].key?('appservers')
      @app_info_map[version_key]['appservers'].each { |location|
        host = location.split(":")[0]
        current_hosts << host
      }
    end
    return current_hosts
  end

  # This method computes how many nodes will be needed to satisfy a
  # request to start a num_appservers AppServers each with a certain
  # memory requirement.
  #
  # Args:
  #   num_appservers: An Integer indicationg the desired number of
  #     AppServers.
  #   max_app_mem: An Integer indicating the maximum memory per AppServer.
  # Returns:
  #   An Integer indicating the needed number of nodes.
  def appservers_to_nodes(num_appservers, max_app_mem)
    # TODO: We should check the cores/RAM of @options['instance_type'],
    # then understand how many AppServers of max_app_mem each we can fit.
    return (num_appservers/3.0).ceil
  end

  # Try to add an AppServer for the specified version, ensuring that a
  # minimum number of AppServers is always kept.
  #
  # Args:
  #   version_key: A String containing the version key.
  #   delta_appservers: The desired number of new AppServers.
  # Returns:
  #   An Integer indicating the number of nodes we need to scale to
  #     accomodate the request.
  def try_to_scale_up(version_key, delta_appservers)
    # Select an compute machine if it has enough resources to support
    # another AppServer for this version.
    available_hosts = []

    # Prevent each machine from being assigned too many instances.
    allocated_memory = get_allocated_memory

    # Prioritize machines that aren't serving the version.
    current_hosts = get_hosts_for_version(version_key)

    # Get the memory limit for this application.
    project_id, service_id, version_id = version_key.split(
      VERSION_PATH_SEPARATOR)
    begin
      version_details = ZKInterface.get_version_details(
        project_id, service_id, version_id)
    rescue VersionNotFound
      Djinn.log_info("Not scaling #{version_key} because it no longer exists")
      return 0
    end

    max_app_mem = Integer(@options['default_max_appserver_memory'])
    if version_details.key?('instanceClass')
      instance_class = version_details['instanceClass'].to_sym
      max_app_mem = INSTANCE_CLASSES.fetch(instance_class, max_app_mem)
    end

    # Let's consider the last system load readings we have, to see if the
    # node can run another AppServer.
    @state_change_lock.synchronize {
      get_all_compute_nodes.each { |host|
        @cluster_stats.each { |node|
          next if node['private_ip'] != host
          Djinn.log_debug("Using #{host}'s stats, making sure keys are accessible " \
            "node['memory']['total']: #{node['memory']['total']} " \
            "node['memory']['available']: #{node['memory']['available']}" \
            "node['loadavg']['last_1min']: #{node['loadavg']['last_1min']}" \
            "node['cpu']['count']: #{node['cpu']['count']}"
          )
          # Check how many new AppServers of this app, we can run on this
          # node (as theoretical maximum memory usage goes).  First convert
          # total memory to MB.
          total = Float(node['memory']['total']/MEGABYTE_DIVISOR)
          allocated_memory[host] = 0 if allocated_memory[host].nil?
          max_new_total = Integer(
            (total - allocated_memory[host] - SAFE_MEM) / max_app_mem)
          Djinn.log_debug("Check for total memory usage: #{host} can run " \
                          "#{max_new_total} AppServers for #{version_key}.")
          break if max_new_total <= 0

          # Now we do a similar calculation but for the current amount of
          # available memory on this node. First convert bytes to MB.
          host_available_mem = Float(node['memory']['available']/MEGABYTE_DIVISOR)
          max_new_free = Integer((host_available_mem - SAFE_MEM) / max_app_mem)
          Djinn.log_debug("Check for free memory usage: #{host} can run " \
                          "#{max_new_free} AppServers for #{version_key}.")
          break if max_new_free <= 0

          # The host needs to have normalized average load less than MAX_LOAD_AVG.
          if Float(node['loadavg']['last_1min']) / node['cpu']['count'] > MAX_LOAD_AVG
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
    }
    Djinn.log_debug(
      "Hosts available to scale #{version_key}: #{available_hosts}.")

    # Since we may have 'clumps' of the same host (say a very big
    # compute machine) we shuffle the list of candidates here.
    available_hosts.shuffle!

    # We prefer candidate that are not already running the application, so
    # ensure redundancy for the application.
    delta_appservers.downto(1) { |delta|
      if available_hosts.empty?
        Djinn.log_info("No compute node is available to scale #{version_key}: " \
                       "still need #{delta} AppServers.")
        return appservers_to_nodes(delta, max_app_mem)
      end

      appserver_to_use = nil
      available_hosts.each { |host|
        unless current_hosts.include?(host)
          Djinn.log_debug("Prioritizing #{host} to run #{version_key} " \
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

      Djinn.log_info(
        "Adding a new AppServer on #{appserver_to_use} for #{version_key}.")
      @app_info_map[version_key]['appservers'] << "#{appserver_to_use}:-1"
    }

    # We started all desired AppServers.
    @last_decision[version_key] = Time.now.to_i
    return 0
  end


  # Try to remove an AppServer for the specified version, ensuring
  # that a minimum number of AppServers is always kept. We remove
  # AppServers from the 'latest' compute node.
  #
  # Args:
  #   version_key: A String containing the version key.
  #   delta_appservers: The desired number of AppServers to remove.
  # Returns:
  #   A boolean indicating if an AppServer was removed.
  def try_to_scale_down(version_key, delta_appservers)
    project_id, service_id, version_id = version_key.split(
      VERSION_PATH_SEPARATOR)
    # See how many AppServers are running on each machine. We cannot scale
    # if we already are at the requested minimum.
    begin
      version_details = ZKInterface.get_version_details(
        project_id, service_id, version_id)
      min, max = get_min_max_from_version_details(version_details)
    rescue VersionNotFound
      min = 0
    end

    if @app_info_map[version_key]['appservers'].length <= min
      Djinn.log_debug("We are already at the minimum number of AppServers " \
                      "for #{version_key}.")
      return false
    end

    # Make sure we leave at least the minimum number of AppServers
    # running.
    max_delta = @app_info_map[version_key]['appservers'].length - min
    num_to_remove = [delta_appservers, max_delta].min

    # We first remove AppServers that may not have yet started: this
    # is important to guarantee the minimum number of AppServers will hold
    # even in the event that new AppServers fails to start (assuming there
    # are at least old ones running).
    to_delete = []
    get_all_compute_nodes.reverse_each { |node_ip|
      break if num_to_remove == to_delete.length
      @app_info_map[version_key]['appservers'].each { |location|
        break if num_to_remove == to_delete.length

        host, port = location.split(":")
        to_delete << location if host == node_ip && Integer(port) < 0
      }
    }

    # Let's pick the latest compute node hosting the application and
    # remove the AppServer there, so we can try to reclaim it once it's
    # unloaded.
    get_all_compute_nodes.reverse_each { |node_ip|
      break if num_to_remove == to_delete.length
      @app_info_map[version_key]['appservers'].each { |location|
        break if num_to_remove == to_delete.length

        host, _ = location.split(":")
        to_delete << location if host == node_ip
      }
    }

    # Finally terminates the selected AppServers. Since we can have
    # multiple same locations (for starting AppServers) we delete the last
    # occurence of the object only.
    to_delete.each{ |location|
      i = @app_info_map[version_key]['appservers'].rindex(location)
      if i.nil?
        Djinn.log_warn("Something went wrong removing #{location}.")
        next
      end
      @app_info_map[version_key]['appservers'].delete_at(i)
      @last_decision[version_key] = Time.now.to_i
      Djinn.log_info("Removing an AppServer for #{version_key} #{location}.")
    }

    return !to_delete.empty?
  end

  # This function unpacks an application tarball if needed. A removal of
  # the old application code can be forced with a parameter.
  #
  # Args:
  #   version_key: the version to setup
  #   remove_old: boolean to force a re-setup of the app from the tarball
  def setup_app_dir(version_key, remove_old=false)
    project_id, service_id, version_id = version_key.split(
      VERSION_PATH_SEPARATOR)
    begin
      version_details = ZKInterface.get_version_details(
        project_id, service_id, version_id)
    rescue VersionNotFound
      Djinn.log_debug(
        "Skipping #{version_key} setup because version node does not exist")
      return
    end

    error_msg = ''

    # Make sure we have the application directory (only certain roles
    # needs it).
    unless Dir.exist?(HelperFunctions::APPLICATIONS_DIR)
      Dir.mkdir(HelperFunctions::APPLICATIONS_DIR)
    end

    revision_key = [version_key, version_details['revision'].to_s].join(
      VERSION_PATH_SEPARATOR)
    if remove_old && my_node.is_load_balancer?
      Djinn.log_info("Removing old application revisions for #{version_key}.")
      revision_dirs = []
      Dir.entries(HelperFunctions::APPLICATIONS_DIR).each { |revision_dir|
        next unless File.directory?(revision_dir)
        next unless revision_dir.include?(version_key)
        # Keep revision that is being set up.
        next if revision_dir == revision_key
        revision_dirs << revision_key
      }
      revision_dirs = revision_dirs.sort
      # Keep last revision in case this machine is hosting instances.
      revision_dirs.pop
      revision_dirs.each { |revision_dir|
        FileUtils.rm_rf("#{HelperFunctions::APPLICATIONS_DIR}/#{revision_dir}")
      }

      old_source_archives = []
      Dir.entries("#{PERSISTENT_MOUNT_POINT}/apps").each { |source_archive|
        next unless File.file?(source_archive)
        next unless source_archive.include?(version_key)
        next if source_archive.include?(revision_key)
        old_source_archives << source_archive
      }
      old_source_archives = old_source_archives.sort
      old_source_archives.pop
      old_source_archives.each { |source_archive|
        FileUtils.rm_f("#{PERSISTENT_MOUNT_POINT}/apps/#{source_archive}")
      }
    end

    begin
      fetch_revision(revision_key)
      HelperFunctions.setup_revision(revision_key)
    rescue AppScaleException => exception
      error_msg = "ERROR: couldn't setup source for #{version_key} " \
                  "(#{exception.message})."
    end
    if remove_old && my_node.is_load_balancer?
      begin
        HelperFunctions.parse_static_data(version_key, true)
      rescue => except
        except_trace = except.backtrace.join("\n")
        Djinn.log_debug("setup_app_dir: parse_static_data exception from" \
          " #{version_key}: #{except_trace}.")
        # This specific exception may be a JSON parse error.
        error_msg = "ERROR: Unable to parse app.yaml file for " \
                    "#{version_key}. Exception of #{except.class} with " \
                    "message #{except.message}"
      end
    end
    unless error_msg.empty?
      # Something went wrong: place the error applcation instead.
      place_error_app(version_key, error_msg)
    end
  end

  # Returns request info stored by the AppController in a JSON string
  # containing the average request rate, timestamp, and total requests seen.
  #
  # Args:
  #   version_key: A String that indicates which version we are fetching
  #     request info for.
  #   secret: A String that authenticates callers.
  # Returns:
  #   A JSON string containing the average request rate, timestamp, and total
  # requests seen for the given application.
  def get_request_info(version_key, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    Djinn.log_debug("Sending a log with request rate #{version_key}, " \
                    "timestamp #{@last_sampling_time[version_key]}, request " \
                    "rate #{@average_req_rate[version_key]}")
    encoded_request_info = JSON.dump({
      'timestamp' => @last_sampling_time[version_key],
      'avg_request_rate' => @average_req_rate[version_key],
      'num_of_requests' => @total_req_seen[version_key]
    })
    return encoded_request_info
  end

  # Copies a revision archive from a machine that has it.
  #
  # Args:
  #   revision_key: A string specifying the revision key.
  # Raises:
  #   AppScaleException if unable to fetch source archive.
  def fetch_revision(revision_key)
    app_path = "#{PERSISTENT_MOUNT_POINT}/apps/#{revision_key}.tar.gz"
    return if File.file?(app_path)

    Djinn.log_debug("Fetching #{app_path}")

    RETRIES.downto(0) { ||
      begin
        remote_machine = ZKInterface.get_revision_hosters(
          revision_key, @options['keyname']).sample
      rescue FailedZooKeeperOperationException
        sleep(SMALL_WAIT)
        next
      end

      if remote_machine.nil?
        Djinn.log_info("Waiting for a machine to have a copy of #{app_path}")
        Kernel.sleep(SMALL_WAIT)
        next
      end

      ssh_key = remote_machine.ssh_key
      ip = remote_machine.private_ip
      md5 = ZKInterface.get_revision_md5(revision_key, ip)
      Djinn.log_debug("Trying #{ip}:#{app_path} for the application.")
      RETRIES.downto(0) {
        begin
          HelperFunctions.scp_file(app_path, app_path, ip, ssh_key, true)
          if File.exists?(app_path)
            if HelperFunctions.check_tarball(app_path, md5)
              Djinn.log_info("Got a copy of #{revision_key} from #{ip}.")
              ZKInterface.add_revision_entry(
                revision_key, my_node.private_ip, md5)
              return
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

    Djinn.log_error("Unable to get the application from any node.")
    raise AppScaleException.new("Unable to fetch #{app_path}")
  end

  # This function creates the xmpp account for 'app', as app@login_ip.
  def start_xmpp_for_app(app)
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

    begin
      retries ||= 0
      result = uac.commit_new_user(xmpp_user, xmpp_pass, "app")
    rescue UserExists
      Djinn.log_info("User #{xmpp_user} already exists")
      # We need to update the password of the channel XMPP account for
      # authorization.
      result = uac.change_password(xmpp_user, xmpp_pass)
      Djinn.log_debug("Change password returned: #{result}")
    rescue InternalError
      Djinn.log_warn('Failed to create a new user')
      retries += 1
      if retries < RETRIES
        sleep(SMALL_WAIT)
        retry
      else
        raise
      end
    end

    Djinn.log_debug("Created user [#{xmpp_user}] with password " \
      "[#{@@secret}] and hashed password [#{xmpp_pass}]")

    if Ejabberd.does_app_need_receive?(app)
      start_cmd = "#{PYTHON27} #{APPSCALE_HOME}/XMPPReceiver/" \
        "xmpp_receiver.py #{app} #{login_ip} " \
        "#{get_load_balancer.private_ip} #{@@secret}"
      MonitInterface.start(watch_name, start_cmd)
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
    MonitInterface.stop("xmpp-#{app}") if MonitInterface.is_running?("xmpp-#{app}")
    Djinn.log_info("Done shutting down xmpp receiver for app: #{app}")
  end

  def start_open
  end

  def stop_open
  end

  # Gathers App Controller and System Manager stats for this node.
  #
  # Args:
  #   secret: The secret of this deployment.
  # Returns:
  #   A hash in string format containing system and platform stats for this
  #     node.
  def get_node_stats_json(secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return NOT_READY if @nodes.empty?

    # Get stats from Hermes.
    begin
      system_stats = HermesClient.get_system_stats(my_node.private_ip, @@secret)
    rescue AppScaleException => error
      Djinn.log_warn("Couldn't get system stats from Hermes: #{error.message}")
      return INVALID_REQUEST
    end

    Djinn.log_debug('get_node_stats_json: got system stats.')

    # Combine all useful stats and return.
    node_stats = system_stats
    node_stats['apps'] = {}
    if my_node.is_shadow?
      my_versions_loaded  = []
      APPS_LOCK.synchronize {
        my_versions_loaded = @versions_loaded.clone if my_node.is_load_balancer?
      }
      my_versions_loaded.each { |version_key|
        project_id, service_id, version_id = version_key.split(
          VERSION_PATH_SEPARATOR)

        appservers = 0
        pending = 0
        APPS_LOCK.synchronize {
          if @app_info_map[version_key].nil? ||
              @app_info_map[version_key]['appservers'].nil?
            Djinn.log_debug(
              "#{version_key} not setup yet: skipping getting stats.")
            next
          end
          @app_info_map[version_key]['appservers'].each { |location|
            _host, port = location.split(':')
            if Integer(port) > 0
              appservers += 1
            else
              pending += 1
            end
          }
        }

        begin
          version_details = ZKInterface.get_version_details(
            project_id, service_id, version_id)
        rescue VersionNotFound
          next
        end

        # Get HAProxy requests.
        Djinn.log_debug("Getting HAProxy stats for #{version_key}")
        total_reqs, reqs_enqueued, _,
          collection_time = get_application_load_stats(version_key)
        # Create the apps hash with useful information containing
        # HAProxy stats.
        begin
          if collection_time == :no_backend
            total_reqs = 0
            reqs_enqueued = 0
            appservers = 0
            pending = 0
          end

          node_stats['apps'][version_key] = {
            'language' => version_details['runtime'].tr('^A-Za-z', ''),
            'appservers' => appservers,
            'pending_appservers' => pending,
            'http' => version_details['appscaleExtensions']['httpPort'],
            'https' => version_details['appscaleExtensions']['httpsPort'],
            'total_reqs' => total_reqs,
            'reqs_enqueued' => reqs_enqueued
          }
        rescue => except
          backtrace = except.backtrace.join("\n")
          message = "Unforseen exception: #{except} \nBacktrace: #{backtrace}"
          Djinn.log_warn("Unable to get application stats: #{message}")
        end
      }
    end

    node_stats['cloud'] = my_node.cloud
    node_stats['state'] = @state
    node_stats['db_location'] = NOT_UP_YET
    node_stats['db_location'] = get_db_master.public_ip if @done_initializing
    node_stats['is_initialized'] = @done_initializing
    node_stats['is_loaded'] = @done_loading
    node_stats['public_ip'] = my_node.public_ip
    node_stats['private_ip'] = my_node.private_ip
    node_stats['roles'] = my_node.roles || ['none']

    JSON.dump(node_stats)
  end

  # Gets summarized total_requests, total_req_in_queue and current_sessions
  # for a specific application version accross all LB nodes.
  #
  # Args:
  #   version_key: A string specifying the version key.
  # Returns:
  #   The total requests for the proxy, the requests enqueued and current sessions.
  #
  def get_application_load_stats(version_key)
    total_requests, requests_in_queue, sessions = 0, 0, 0
    pxname = "#{HelperFunctions::GAE_PREFIX}#{version_key}"
    time = :no_stats
    lb_nodes = []
    @state_change_lock.synchronize {
      lb_nodes = @nodes.select { |node| node.is_load_balancer? }
    }
    lb_nodes.each { |node|
      begin
        ip = node.private_ip
        load_stats = HermesClient.get_proxy_load_stats(ip, @@secret, pxname)
        total_requests += load_stats[0]
        requests_in_queue += load_stats[1]
        sessions += load_stats[2]
        time = Time.now.to_i
      rescue AppScaleException => error
        Djinn.log_warn("Couldn't get proxy stats from Hermes: #{error.message}")
      end
    }
    if lb_nodes.length > 1
      # Report total HAProxy stats if there are multiple LB nodes.
      Djinn.log_debug("Summarized HAProxy load stats for #{pxname}: " \
        "req_tot=#{total_requests}, qcur=#{requests_in_queue}, scur=#{sessions}")
    end
    return total_requests, requests_in_queue, sessions, time
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
    return NOT_READY if @nodes.empty?

    content = CronHelper.get_application_cron_info(app_name)
    JSON.dump(content)
  end
end

