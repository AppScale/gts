#!/usr/bin/ruby -w

# First-party Ruby libraries
require 'posixpsutil'
require 'socket'
require 'timeout'

# Imports for AppController libraries
$:.unshift File.join(File.dirname(__FILE__))
require 'node_info'
require 'helperfunctions'
require 'service_helper'

# To implement support for the Google App Engine Task Queue API, we use
# the open source rabbitmq server and celery. This lets users dispatch background
# tasks, whose data are stored as items in rabbitmq. This module provides
# methods that automatically configure and deploy rabbitmq and celery as needed.
module TaskQueue
  # Indicates an error when determining the version of rabbitmq.
  class UnknownVersion < StandardError; end

  # The default name of the service.
  NAME = 'TaskQueue'.freeze

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

  # Name for flower service as per helper.
  SERVICE_NAME_FLOWER = 'appscale-flower'.freeze

  # Name for rabbit mq service as per helper.
  SERVICE_NAME_RABBITMQ = 'appscale-rabbitmq-server.target'.freeze

  # Name for task queue service template as per helper.
  SERVICE_NAME_TASKQUEUE = 'appscale-taskqueue@'.freeze

  # The location of taskqueue venv pip
  TASKQUEUE_PIP = '/opt/appscale_venvs/appscale_taskqueue/bin/pip'.chomp

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

    Ejabberd.ensure_correct_epmd
    ServiceHelper.start(SERVICE_NAME_RABBITMQ)
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

    # Look up the TaskQueue master's hostname (not the fqdn). To resolve
    # it we use Addrinfo.getnameinfo since Resolv will not use /etc/hosts
    # and this could cause issues on private clusters.
    master_tq_host = nil
    begin
      master_tq_host = Addrinfo.ip(master_ip).getnameinfo[0]
      if master_tq_host =~ /^[[:digit:]]/
        Djinn.log_warn("#{master_ip} didn't resolve to a hostname! Expect" \
                       " problems with rabbitmq clustering.")
      else
        master_tq_host = master_tq_host.split('.')[0]
      end
    rescue SocketError
      Djinn.log_error("Cannot resolv #{master_ip}!")
      return false
    end
    Djinn.log_info("Using #{master_tq_host} as master taskqueue hostname.")

    # Now we try to cluster with the master node.
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
          return true
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
    service_env = {}
    service_env[:APPSCALE_OPTION_VERBOSE] = '--verbose' if verbose
    ServiceHelper.write_environment('appscale-taskqueue', service_env)
    Djinn.log_debug('Starting taskqueue servers on this node')
    ports = get_server_ports
    ServiceHelper.start(SERVICE_NAME_TASKQUEUE, ports)
    Djinn.log_debug('Done starting taskqueue servers on this node')
  end

  # Stops the RabbitMQ, celery workers, and taskqueue server on this node.
  def self.stop
    Djinn.log_debug('Shutting down celery workers')
    stop_script = \
      "import celery\n" \
      "celery = celery.Celery()\n" \
      "with celery.control.app.connection_or_acquire(None) as conn:\n" \
      "  conn.ensure_connection(max_retries=2)\n" \
      "  celery.control.broadcast('shutdown', connection=conn)"
    stop_cmd = %Q(/usr/bin/python2 -c "#{stop_script}")
    Djinn.log_run(stop_cmd)
    stop_rabbitmq
    stop_taskqueue_server
  end

  def self.stop_rabbitmq
    Djinn.log_debug('Shutting down RabbitMQ')
    ServiceHelper.stop(SERVICE_NAME_RABBITMQ)
  end

  # Stops the AppScale TaskQueue server.
  def self.stop_taskqueue_server
    Djinn.log_debug('Stopping taskqueue servers on this node')
    ServiceHelper.stop(SERVICE_NAME_TASKQUEUE)
    Djinn.log_debug('Done stopping taskqueue servers on this node')
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

    service_env = {
        APPSCALE_FLOWER_OPTION_AUTH: "--basic_auth=appscale:#{flower_password}"
    }
    ServiceHelper.write_environment(SERVICE_NAME_FLOWER, service_env)
    ServiceHelper.start(SERVICE_NAME_FLOWER)
  end

  # Stops the Flower Server on this machine.
  def self.stop_flower
    ServiceHelper.stop(SERVICE_NAME_FLOWER)
  end

  # Number of servers is based on the number of CPUs.
  def self.number_of_servers
    # If this is NaN then it returns 0
    num_procs = `cat /proc/cpuinfo | grep processor | wc -l`.to_i
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
end
