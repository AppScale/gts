#!/usr/bin/ruby -w


# First-party Ruby libraries
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

  # AppScale install directory  
  APPSCALE_HOME = ENV["APPSCALE_HOME"]

  # The port that the RabbitMQ server runs on, by default.
  SERVER_PORT = 5672 
 
  # The port where the TaskQueue server runs on, by default. 
  TASKQUEUE_SERVER_PORT = 64839

  # The port where the Flower server runs on, by default.
  FLOWER_SERVER_PORT = 5555

  # The python executable path.
  PYTHON_EXEC = "python"

  # The path to the file that the shared secret should be written to.
  COOKIE_FILE = "/var/lib/rabbitmq/.erlang.cookie"
  
  # We need some additional logic for the start command hence using 
  # a script.
  RABBITMQ_START_SCRIPT = File.dirname(__FILE__) + "/../" + \
                          "/scripts/start_rabbitmq.sh"

  # The location of the taskqueue server script. This service controls 
  # and creates celery workers, and receives taskqueue protocol buffers
  # from AppServers.
  TASKQUEUE_SERVER_SCRIPT  = File.dirname(__FILE__) + "/../../AppTaskQueue" + \
                          "taskqueue_server.py"

  # The longest we'll wait for RabbitMQ to come up in seconds.
  MAX_WAIT_FOR_RABBITMQ = 30

  # How many times to retry starting rabbitmq on a slave.
  RABBIT_START_RETRY = 1000

  # Stop command for taskqueue server.
  TASKQUEUE_STOP_CMD = "/bin/kill -9 `ps aux | grep taskqueue_server.py | awk {'print $2'}`"

  # Starts a service that we refer to as a "taskqueue_master", a RabbitMQ
  # service that other nodes can rely on to be running the taskqueue server.
  def self.start_master()
    Djinn.log_info("Starting TaskQueue Master")
    self.write_cookie()
    self.erase_local_files()
    Djinn.log_run("bash #{RABBITMQ_START_SCRIPT} #{HelperFunctions.get_secret()}")

    start_taskqueue_server()
    HelperFunctions.sleep_until_port_is_open("localhost", TASKQUEUE_SERVER_PORT)
  end


  # Starts a service that we refer to as a "rabbitmq slave". Since all nodes in
  # RabbitMQ are equal, this name isn't exactly fair, so what this role means
  # here is "start a RabbitMQ server and connect it to the server on the machine
  # playing the 'rabbitmq_master' role." We also start taskqueue servers on 
  # all taskqueue nodes.
  def self.start_slave(master_ip)
    Djinn.log_info("Starting TaskQueue Slave")
    self.write_cookie()
    self.erase_local_files()
    
    # Wait for RabbitMQ on master node to come up
    Djinn.log_debug("Waiting for RabbitMQ on master node to come up")
    HelperFunctions.sleep_until_port_is_open(master_ip, SERVER_PORT)

    # start the server, reset it to join the head node
    hostname = `hostname`.chomp()
    start_cmds = ["rabbitmqctl start_app",
                  "rabbitmqctl stop_app",
                  "rabbitmqctl reset",
                  "rabbitmq-server -detached -setcookie #{HelperFunctions.get_secret()}",
                  "rabbitmqctl cluster rabbit@#{hostname}",
                  "rabbitmqctl start_app"]
    full_cmd = "#{start_cmds.join('; ')}"

    tries_left = RABBIT_START_RETRY
    while 1
      Djinn.log_run("#{full_cmd}")
      Djinn.log_debug("Waiting for RabbitMQ on local node to come up")
      begin
        Timeout::timeout(MAX_WAIT_FOR_RABBITMQ) do
          HelperFunctions.sleep_until_port_is_open("localhost", SERVER_PORT)
          Djinn.log_debug("Done starting rabbitmq_slave on this node")

          Djinn.log_debug("Starting TaskQueue server on slave node")
          start_taskqueue_server()
          Djinn.log_debug("Waiting for TaskQueue server on slave node to come up")
          HelperFunctions.sleep_until_port_is_open("localhost", 
                                                   TASKQUEUE_SERVER_PORT)
          Djinn.log_debug("Done waiting for TaskQueue server")
          return
        end
      rescue Timeout::Error
        tries_left -= 1
        Djinn.log_warn("Waited for RabbitMQ to start, but timed out. " +
          "Retries left #{tries_left}.")
        self.erase_local_files()
      end
      if tries_left == 0
        Djinn.log_fatal("CRITICAL ERROR: RabbitMQ slave failed to come up")
        abort
      end
    end
  end

  # Starts the AppScale TaskQueue server.
  def self.start_taskqueue_server()
    Djinn.log_debug("Starting taskqueue_server on this node")
    script ="#{APPSCALE_HOME}/AppTaskQueue/taskqueue_server.py"
    start_cmd = "#{PYTHON_EXEC} #{script}"
    stop_cmd = TASKQUEUE_STOP_CMD
    env_vars = {}
    MonitInterface.start(:taskqueue, start_cmd, stop_cmd, TASKQUEUE_SERVER_PORT, env_vars)
    Djinn.log_debug("Done starting taskqueue_server on this node")
  end

  # Stops the RabbitMQ, celery workers, and taskqueue server on this node.
  def self.stop()
    Djinn.log_debug("Shutting down celery workers")
    stop_cmd = "python -c \"import celery; celery = celery.Celery(); celery.control.broadcast('shutdown')\""
    Djinn.log_run(stop_cmd)
    Djinn.log_debug("Shutting down RabbitMQ")
    Djinn.log_run("rabbitmqctl stop")
    self.stop_taskqueue_server()
  end

  # Stops the AppScale TaskQueue server.
  def self.stop_taskqueue_server()
    Djinn.log_debug("Stopping taskqueue_server on this node")
    Djinn.log_run(TASKQUEUE_STOP_CMD)
    MonitInterface.stop(:taskqueue)
    Djinn.log_debug("Done stopping taskqueue_server on this node")
  end

  # Erlang processes use a secret value as a password to authenticate between
  # one another. Since this is pretty much the same thing we do in AppScale
  # with our secret key, use the same key here.
  # TODO(cgb): Consider using a different key, so that if one key is compromised
  # it doesn't compromise the other.
  def self.write_cookie()
    HelperFunctions.write_file(COOKIE_FILE, HelperFunctions.get_secret())
  end


  # Erases all the files that RabbitMQ normally writes to, which can be useful
  # to ensure that we start up RabbitMQ without left-over state from previous
  # runs.
  def self.erase_local_files()
    Djinn.log_run("rm -rf /var/log/rabbitmq/*")
    Djinn.log_run("rm -rf /var/lib/rabbitmq/mnesia/*")
    Djinn.log_run("rm -rf /etc/appscale/celery/")
  end


  # Starts the Flower Server on this machine, which provides a web UI to celery
  # and RabbitMQ. A link to Flower is given in the AppDashboard, for users to
  # monitor their Task Queue tasks.
  def self.start_flower()
    start_cmd = "/usr/local/bin/flower"
    stop_cmd = "/bin/ps ax | /bin/grep flower | /bin/grep -v grep | /usr/bin/awk '{print $1}' | xargs kill -9"
    MonitInterface.start(:flower, start_cmd, stop_cmd, FLOWER_SERVER_PORT)
  end


  # Stops the Flower Server on this machine.
  def self.stop_flower()
    MonitInterface.stop(:flower)
  end


end
