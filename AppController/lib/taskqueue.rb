#!/usr/bin/ruby -w

# First-party Ruby libraries
require 'posixpsutil'
require 'resolv'
require 'socket'
require 'timeout'

# Imports for AppController libraries
$:.unshift File.join(File.dirname(__FILE__))
require 'djinn_job_data'
require 'helperfunctions'
require 'monit_interface'

# To implement support for the Google App Engine Task Queue API, we use
# the open source rabbitmq server and celery. This lets users dispatch background
# tasks, whose data are stored as items in rabbitmq. This module provides
# methods that automatically configure and deploy rabbitmq and celery as needed.
module TaskQueue
  # Indicates an error when determining the version of rabbitmq.
  class UnknownVersion < StandardError; end

  # The default name of the service.
  NAME = 'TaskQueue'.freeze

  # The default name of the service.
  REST_NAME = 'TaskQueue_REST'.freeze

  # AppScale install directory.
  APPSCALE_HOME = ENV['APPSCALE_HOME']

  # The port that the RabbitMQ server runs on, by default.
  SERVER_PORT = 5672

  # The starting port for TaskQueue server processes.
  STARTING_PORT = 17447

  # HAProxy port for TaskQueue servers.
  HAPROXY_PORT = 17446

  # Default REST API public port.
  TASKQUEUE_SERVER_SSL_PORT = 8199

  # The path to the file that the shared secret should be written to.
  COOKIE_FILE = '/var/lib/rabbitmq/.erlang.cookie'.freeze

  # The location of the taskqueue server script. This service controls
  # and creates celery workers, and receives taskqueue protocol buffers
  # from AppServers.
  TASKQUEUE_SERVER_SCRIPT = `which appscale-taskqueue`.chomp

  # Where to find the rabbitmqctl command.
  RABBITMQCTL = `which rabbitmqctl`.chomp

  # The longest we'll wait for RabbitMQ to come up in seconds.
  MAX_WAIT_FOR_RABBITMQ = 60

  # Location where celery workers back up state to.
  CELERY_STATE_DIR = '/opt/appscale/celery'.freeze

  # Optional features that can be installed for the taskqueue package.
  OPTIONAL_FEATURES = ['celery_gui']

  # TaskQueue server processes per core.
  MULTIPLIER = 2

  # If we fail to get the number of processors we set our default number of
  # taskqueue servers to this value.
  DEFAULT_NUM_SERVERS = 3

  # Starts rabbitmq server.
  def self.start_rabbitmq
    if RABBITMQCTL.empty?
      msg = "Couldn't find rabbitmqctl! Not starting rabbitmq server."
      Djinn.log_error(msg)
      raise AppScaleException.new(msg)
    end

    pidfile = File.join('/', 'var', 'lib', 'rabbitmq', 'mnesia',
                        "rabbit@#{Socket.gethostname}.pid")

    var_run_pidfile = File.join('/', 'var', 'run', 'rabbitmq', 'pid')
    if File.read('/proc/1/cgroup').include?('docker')
      # In docker, the pid file is present at /var/run/rabbitmq/pid
      pidfile = var_run_pidfile
    end

    begin
      installed_version = Gem::Version.new(get_rabbitmq_version)
      new_location_version = Gem::Version.new('3.4')
      if installed_version < new_location_version
        pidfile = var_run_pidfile
      end
    rescue TaskQueue::UnknownVersion => error
      Djinn.log_warn("Error while getting rabbitmq version: #{error.message}")
    end

    Djinn.log_run("mkdir -p #{CELERY_STATE_DIR}")
    service_bin = `which service`.chomp
    start_cmd = "#{service_bin} rabbitmq-server start"
    stop_cmd = "#{service_bin} rabbitmq-server stop"

    Ejabberd.ensure_correct_epmd
    MonitInterface.start_daemon(:rabbitmq, start_cmd, stop_cmd, pidfile,
                                MAX_WAIT_FOR_RABBITMQ)
  end

  # Starts a service that we refer to as a "taskqueue_master", a RabbitMQ
  # service that other nodes can rely on to be running the taskqueue server.
  #
  # Args:
  #   clear_data: A boolean that indicates whether or not RabbitMQ state should
  #     be erased before starting RabbitMQ.
  def self.start_master(clear_data, verbose)
    Djinn.log_info('Starting TaskQueue Master')
    write_cookie

    if clear_data
      Djinn.log_debug('Erasing RabbitMQ state')
      erase_local_files
    else
      Djinn.log_debug('Not erasing RabbitMQ state')
    end

    # First, start up RabbitMQ and make sure the service is up.
    start_rabbitmq
    HelperFunctions.sleep_until_port_is_open('localhost',
                                             SERVER_PORT)

    # The master rabbitmq will set the policy for replication of messages
    # and queues.
    policy = '{"ha-mode":"all", "ha-sync-mode": "automatic"}'
    Djinn.log_run("#{RABBITMQCTL} set_policy ha-all '' '#{policy}'")

    # Next, start up the TaskQueue Server.
    start_taskqueue_server(verbose)
    HelperFunctions.sleep_until_port_is_open('localhost',
                                             STARTING_PORT)
  end

  # Starts a service that we refer to as a "rabbitmq slave". Since all nodes in
  # RabbitMQ are equal, this name isn't exactly fair, so what this role means
  # here is "start a RabbitMQ server and connect it to the server on the machine
  # playing the 'rabbitmq_master' role." We also start taskqueue servers on
  # all taskqueue nodes.
  #
  # Args:
  #   master_ip: A String naming the IP address or FQDN where RabbitMQ is
  #     already running.
  #   clear_data: A boolean that indicates whether or not RabbitMQ state should
  #     be erased before starting up RabbitMQ.
  def self.start_slave(master_ip, clear_data, verbose)
    Djinn.log_info('Starting TaskQueue Slave')
    write_cookie

    if clear_data
      Djinn.log_debug('Erasing RabbitMQ state')
      erase_local_files
    else
      Djinn.log_debug('Not erasing RabbitMQ state')
    end

    # Start the local RabbitMQ server, and then wait for RabbitMQ on the master
    # node to come up. The RabbitMQ server on the taskqueue master may not be
    # able to start without this one if it previously stopped first.
    Djinn.log_run("mkdir -p #{CELERY_STATE_DIR}")
    start_rabbitmq
    Djinn.log_debug('Waiting for RabbitMQ on master node to come up')
    HelperFunctions.sleep_until_port_is_open(master_ip, SERVER_PORT)

    # we now reset it to join the head node. To do this we need the
    # hostname of the master node. We go through few options:
    # - the old one is to look into /etc/hosts for it
    # - another one is to just try to resolve it
    # - finally we give up and use the IP address
    master_tq_host = `cat /etc/hosts | grep #{master_ip} | tr -s \" \" | cut -d \" \" -f2`.chomp
    if master_tq_host.empty?
      begin
        master_tq_host = Resolv.getname(master_ip)
      rescue Resolv::ResolvError
        # We couldn't get the name: let's try to use the IP address.
        master_tq_host = master_ip
      end
    end

    HelperFunctions::RETRIES.downto(0) { |tries_left|
      Djinn.log_debug('Waiting for RabbitMQ on local node to come up')
      begin
        Timeout.timeout(MAX_WAIT_FOR_RABBITMQ) do
          HelperFunctions.sleep_until_port_is_open('localhost', SERVER_PORT)
          Djinn.log_debug('Done starting rabbitmq_slave on this node')

          Djinn.log_run("#{RABBITMQCTL} stop_app")
          Djinn.log_run("#{RABBITMQCTL} join_cluster rabbit@#{master_tq_host}")
          Djinn.log_run("#{RABBITMQCTL} start_app")

          Djinn.log_debug('Starting TaskQueue servers on slave node')
          start_taskqueue_server(verbose)
          Djinn.log_debug('Waiting for TaskQueue servers on slave node to' \
                          ' come up')
          HelperFunctions.sleep_until_port_is_open('localhost', STARTING_PORT)
          Djinn.log_debug('Done waiting for TaskQueue servers')
          return
        end
      rescue Timeout::Error
        tries_left -= 1
        Djinn.log_warn('Waited for RabbitMQ to start, but timed out. ' \
          "Retries left #{tries_left}.")
        Djinn.log_run("ps ax | grep rabbit | grep -v grep | awk '{print $1}' | xargs kill -9")
        erase_local_files if clear_data
      end
      if tries_left.zero?
        Djinn.log_fatal('CRITICAL ERROR: RabbitMQ slave failed to come up')
        abort
      end
    }
  end

  # Starts the AppScale TaskQueue server.
  def self.start_taskqueue_server(verbose)
    Djinn.log_debug('Starting taskqueue servers on this node')
    ports = get_server_ports

    start_cmd = TASKQUEUE_SERVER_SCRIPT
    start_cmd << ' --verbose' if verbose
    env_vars = { PATH: '$PATH:/usr/local/bin' }
    MonitInterface.start(:taskqueue, start_cmd, ports, env_vars)
    Djinn.log_debug('Done starting taskqueue servers on this node')
  end

  # Stops the RabbitMQ, celery workers, and taskqueue server on this node.
  def self.stop
    Djinn.log_debug('Shutting down celery workers')
    stop_cmd = "/usr/bin/python2 -c \"import celery; celery = celery.Celery(); celery.control.broadcast('shutdown')\""
    Djinn.log_run(stop_cmd)
    Djinn.log_debug('Shutting down RabbitMQ')
    MonitInterface.stop(:rabbitmq)
    stop_taskqueue_server
  end

  # Stops the AppScale TaskQueue server.
  def self.stop_taskqueue_server
    Djinn.log_debug('Stopping taskqueue_server on this node')
    MonitInterface.stop(:taskqueue)
    Djinn.log_debug('Done stopping taskqueue_server on this node')
  end

  # Erlang processes use a secret value as a password to authenticate between
  # one another. Since this is pretty much the same thing we do in AppScale
  # with our secret key, use the same key here but hashed as to not reveal the
  # actual key.
  def self.write_cookie
    HelperFunctions.write_file(COOKIE_FILE, HelperFunctions.get_taskqueue_secret)
  end

  # Erases all the files that RabbitMQ normally writes to, which can be useful
  # to ensure that we start up RabbitMQ without left-over state from previous
  # runs.
  def self.erase_local_files
    Djinn.log_run('rm -rf /var/log/rabbitmq/*')
    Djinn.log_run('rm -rf /var/lib/rabbitmq/mnesia/*')
    Djinn.log_run('rm -rf /etc/appscale/celery/')
    Djinn.log_run("rm -rf #{CELERY_STATE_DIR}/*")
  end

  # Starts the Flower Server on this machine, which provides a web UI to celery
  # and RabbitMQ. A link to Flower is given in the AppDashboard, for users to
  # monitor their Task Queue tasks.
  #
  # Args:
  #   flower_password: A String that is used as the password to log into flower.
  def self.start_flower(flower_password)
    if flower_password.nil? || flower_password.empty?
      Djinn.log_info("Flower password is empty: don't start flower.")
      return
    end

    flower_cmd = `which flower`.chomp
    start_cmd = "#{flower_cmd} --basic_auth=appscale:#{flower_password}"
    MonitInterface.start(:flower, start_cmd)
  end

  # Stops the Flower Server on this machine.
  def self.stop_flower
    MonitInterface.stop(:flower)
  end

  # Number of servers is based on the number of CPUs.
  def self.number_of_servers
    # If this is NaN then it returns 0
    num_procs = `grep -c processor /proc/cpuinfo`.to_i
    return DEFAULT_NUM_SERVERS if num_procs.zero?
    (num_procs * MULTIPLIER)
  end

  # Returns a list of ports that should be used to host TaskQueue servers.
  def self.get_server_ports
    num_servers = number_of_servers

    server_ports = []
    num_servers.times { |i|
      server_ports << STARTING_PORT + i
    }
    server_ports
  end

  def self.get_rabbitmq_version
    version_re = /Version: (.*)-/

    begin
      rabbitmq_info = `dpkg -s rabbitmq-server`
    rescue Errno::ENOENT
      raise TaskQueue::UnknownVersion.new('The dpkg command was not found')
    end

    match = version_re.match(rabbitmq_info)
    raise TaskQueue::UnknownVersion.new('Unable to find version') if match.nil?
    match[1]
  end
end
