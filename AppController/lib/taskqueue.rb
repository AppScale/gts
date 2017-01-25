#!/usr/bin/ruby -w


# First-party Ruby libraries
require 'resolv'
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

  # The default name of the service.
  NAME = "TaskQueue"

  # AppScale install directory.
  APPSCALE_HOME = ENV["APPSCALE_HOME"]

  # The port that the RabbitMQ server runs on, by default.
  SERVER_PORT = 5672

  # The port where the TaskQueue server runs on, by default.
  TASKQUEUE_SERVER_INTERNAL_PORT = 17446

  # HAProxy port for TaskQueue REST API endpoints.
  HAPROXY_PORT = 8061

  # Default REST API public port.
  TASKQUEUE_SERVER_SSL_PORT = 8199

  # The port where the Flower server runs on, by default.
  FLOWER_SERVER_PORT = 5555

  # The path to the file that the shared secret should be written to.
  COOKIE_FILE = "/var/lib/rabbitmq/.erlang.cookie"

  # The RabbitMQ server.
  RABBIT_SERVER = "/usr/sbin/rabbitmq-server"

  # Command line tool for RabbitMQ.
  RABBIT_CTL = "/usr/sbin/rabbitmqctl"

  # The location of the taskqueue server script. This service controls
  # and creates celery workers, and receives taskqueue protocol buffers
  # from AppServers.
  TASKQUEUE_SERVER_SCRIPT = `which appscale-taskqueue`.chomp

  # The longest we'll wait for RabbitMQ to come up in seconds.
  MAX_WAIT_FOR_RABBITMQ = 30

  # How many times to retry starting rabbitmq on a slave.
  RABBIT_START_RETRY = 10

  # Small wait time to wait for RabbitMQ to settle.
  RABBIT_WAIT = 3

  # Location where celery workers back up state to.
  CELERY_STATE_DIR = "/opt/appscale/celery"

  # Optional features that can be installed for the taskqueue package.
  OPTIONAL_FEATURES = ['celery_gui']

  # Starts the rabbitmq server.
  def self.start_rabbitmq()
    Djinn.log_run("mkdir -p #{CELERY_STATE_DIR}")
    start_cmd = "#{RABBIT_SERVER} -detached"
    stop_cmd = "#{RABBIT_CTL} stop"
    match_cmd = "sname rabbit"
    MonitInterface.start(:rabbitmq, start_cmd, stop_cmd, [9999], nil,
                         match_cmd, nil, nil, nil)
  end

  # Starts a service that we refer to as a "taskqueue_master", a RabbitMQ
  # service that other nodes can rely on to be running the taskqueue server.
  #
  # Args:
  #   clear_data: A boolean that indicates whether or not RabbitMQ state should
  #     be erased before starting RabbitMQ.
  def self.start_master(clear_data, verbose)
    Djinn.log_info("Starting TaskQueue Master")
    self.write_cookie()

    if clear_data
      Djinn.log_debug("Erasing RabbitMQ state")
      self.erase_local_files()
    else
      Djinn.log_debug("Not erasing RabbitMQ state")
    end

    # First, start up RabbitMQ.
    start_rabbitmq

    # Next, start up the TaskQueue Server.
    start_taskqueue_server(verbose)
    HelperFunctions.sleep_until_port_is_open("localhost",
                                             TASKQUEUE_SERVER_INTERNAL_PORT)
  end


  # Interacts with RabbitMQ, instructing to join the master's cluster, in
  # different ways.
  #
  # Args
  #   type: One of ':join', ':update', ':reset_join', to indicate how to
  #     join the cluster.
  #   master_tq_host: The hostname of the master TaskQueue node.
  # Returns
  #   A Boolean indicating if all was good, of some failure happened.
  def self.join_cluster(type, master_tq_host)
    Djinn.log_info("Trying to #{type} #{master_tq_host} rabbitmq cluster.")
    begin
      Timeout.timeout(MAX_WAIT_FOR_RABBITMQ) do
        Djinn.log_run("#{RABBIT_CTL} stop_app")
        case type
        when :join
          Djinn.log_run("#{RABBIT_CTL} join_cluster rabbit@#{master_tq_host}")
        when :update
          Djinn.log_run("#{RABBIT_CTL} update_cluster_nodes rabbit@#{master_tq_host}")
        else
          Djinn.log_run("#{RABBIT_CTL} force_reset")
          Djinn.log_run("#{RABBIT_CTL} join_cluster rabbit@#{master_tq_host}")
        end
        Djinn.log_run("#{RABBIT_CTL} start_app")
      end
    rescue Timeout::Error
      Djinn.log_warn("Timed out trying to #{type} rabbitmq cluster.")
      return false
    end
    return true
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
    Djinn.log_info("Starting TaskQueue Slave")
    self.write_cookie()

    if clear_data
      Djinn.log_debug("Erasing RabbitMQ state")
      self.erase_local_files()
    else
      Djinn.log_debug("Not erasing RabbitMQ state")
    end

    # Wait for RabbitMQ on master node to come up.
    Djinn.log_run("mkdir -p #{CELERY_STATE_DIR}")
    Djinn.log_debug("Waiting for RabbitMQ on master node to come up")
    HelperFunctions.sleep_until_port_is_open(master_ip, SERVER_PORT)

    # Then start RabbitMQ.
    start_rabbitmq

    # We need the hostname of the master node. We go through few options:
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

    # We now try to join the master's RabbitMQ cluster. We try in a few
    # ways: the first one is the simple join, that should work in ideal
    # condition. The update_cluster_nodes may be needed if the node was
    # part of the cluster, and it simply needs to rejoin now. The third
    # one force a reset and a join: this should take care of partitions.
    tries_left = RABBIT_START_RETRY
    loop {
      break if check_taskqueue_server(master_tq_host)

      if join_cluster(:join, master_tq_host)
        break if check_taskqueue_server(master_tq_host)
      end
      if join_cluster(:update, master_tq_host)
        break if check_taskqueue_server(master_tq_host)
      end
      if join_cluster(:reset_join, master_tq_host)
        break if check_taskqueue_server(master_tq_host)
      end

      # If we couldn't join the master's cluster, let's back-off a bit and
      # retry for a little while.
      tries_left -= 1
      if tries_left > 0
        Djinn.log_warn("Retrying to join #{master_tq_host} rabbitmq cluster.")
        Kernel.sleep(RABBIT_WAIT)
      else
        Djinn.log_fatal("CRITICAL ERROR: rabbitmq coulnd't join the cluster.")
        abort
      end
    }

    Djinn.log_debug("Starting TaskQueue server on slave node")
    start_taskqueue_server(verbose)
    Djinn.log_debug("Waiting for TaskQueue server on slave node to come up")
    HelperFunctions.sleep_until_port_is_open("localhost",
                                             TASKQUEUE_SERVER_INTERNAL_PORT)
    Djinn.log_debug("Done waiting for TaskQueue server")
    return
  end

  # TaskQueue slaves sometimes has trouble to join the master, in
  # particular if nodes goes up/down or there are a lot of TaskQueue
  # nodes.
  #
  # Args
  #   master_tq: A String with the hostname of the taskqueue master node.
  # Returns
  #   A Boolean indicating if RabbitMQ is part of the master cluster.
  def self.check_taskqueue_server(master_tq)
    return system("#{RABBIT_CTL} cluster_status | sed -n '/{running_nodes,/,/{partitions,/p' | grep rabbit@#{master_tq} > /dev/null")
  end


  # Starts the AppScale TaskQueue server.
  def self.start_taskqueue_server(verbose)
    Djinn.log_debug("Starting taskqueue_server on this node")
    start_cmd = "/usr/bin/python2 #{TASKQUEUE_SERVER_SCRIPT}"
    start_cmd << ' --verbose' if verbose
    stop_cmd = "/usr/bin/python2 #{APPSCALE_HOME}/scripts/stop_service.py " +
          "#{TASKQUEUE_SERVER_SCRIPT} /usr/bin/python2"
    env_vars = {:PATH => '$PATH:/usr/local/bin'}
    MonitInterface.start(:taskqueue, start_cmd, stop_cmd,
                         [TASKQUEUE_SERVER_INTERNAL_PORT], env_vars, start_cmd,
                         nil, nil, nil)
    Djinn.log_debug("Done starting taskqueue_server on this node")
  end

  # Stops the RabbitMQ, celery workers, and taskqueue server on this node.
  def self.stop()
    Djinn.log_debug("Shutting down celery workers")
    stop_cmd = "/usr/bin/python2 -c \"import celery; celery = celery.Celery(); celery.control.broadcast('shutdown')\""
    Djinn.log_run(stop_cmd)
    Djinn.log_debug("Shutting down RabbitMQ")
    MonitInterface.stop(:rabbitmq)
    self.stop_taskqueue_server()
  end

  # Stops the AppScale TaskQueue server.
  def self.stop_taskqueue_server()
    Djinn.log_debug("Stopping taskqueue_server on this node")
    MonitInterface.stop(:taskqueue)
    Djinn.log_debug("Done stopping taskqueue_server on this node")
  end

  # Erlang processes use a secret value as a password to authenticate between
  # one another. Since this is pretty much the same thing we do in AppScale
  # with our secret key, use the same key here but hashed as to not reveal the
  # actual key.
  def self.write_cookie()
    HelperFunctions.write_file(COOKIE_FILE, HelperFunctions.get_taskqueue_secret())
  end


  # Erases all the files that RabbitMQ normally writes to, which can be useful
  # to ensure that we start up RabbitMQ without left-over state from previous
  # runs.
  def self.erase_local_files()
    Djinn.log_run("rm -rf /var/log/rabbitmq/*")
    Djinn.log_run("rm -rf /var/lib/rabbitmq/mnesia/*")
    Djinn.log_run("rm -rf /etc/appscale/celery/")
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
    stop_cmd = "/usr/bin/python2 #{APPSCALE_HOME}/scripts/stop_service.py " +
          "flower #{flower_password}"
    MonitInterface.start(:flower, start_cmd, stop_cmd, [FLOWER_SERVER_PORT],
                         nil, start_cmd, nil, nil, nil)
  end


  # Stops the Flower Server on this machine.
  def self.stop_flower()
    MonitInterface.stop(:flower)
  end
end
