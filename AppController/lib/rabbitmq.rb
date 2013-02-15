#!/usr/bin/ruby -w


# Imports for AppController libraries
$:.unshift File.join(File.dirname(__FILE__))
require 'godinterface'
require 'djinn_job_data'
require 'helperfunctions'


# To implement support for the Google App Engine Task Queue API, we use
# the open source rabbitmq server. This lets users dispatch background
# tasks, whose data are stored as items in rabbitmq. This module provides
# methods that automatically configure and deploy rabbitmq as needed.
module RabbitMQ
  

  # The port that the RabbitMQ server runs on, by default.
  SERVER_PORT = 5672 
  

  # The path to the file that the shared secret should be written to.
  COOKIE_FILE = "/var/lib/rabbitmq/.erlang.cookie"

  
  # We need some additional logic for the start command hence using 
  # a script.
  RABBITMQ_START_SCRIPT = File.dirname(__FILE__) + "/../" + \
                          "/scripts/start_rabbitmq.sh"

  # Starts a service that we refer to as a "rabbitmq_master", a RabbitMQ
  # service that other nodes can rely on to be running RabbitMQ.
  def self.start_master()
    Djinn.log_debug("Starting RabbitMQ Master")
    self.write_cookie()
    self.erase_local_files()
    # Because god cannot keep track of RabbitMQ because of it's changing 
    # PIDs, we put in a guard on the start command to not start it if 
    # its already running.
    start_cmd = "bash #{RABBITMQ_START_SCRIPT} " +\
                "#{HelperFunctions.get_secret()}"
    stop_cmd = "rabbitmqctl stop"
    env_vars = {}
    GodInterface.start(:rabbitmq, start_cmd, stop_cmd, SERVER_PORT, env_vars)
    # start up rabbitmq manually since god can't do it
    Djinn.log_run("#{start_cmd}")
  end


  # Starts a service that we refer to as a "rabbitmq slave". Since all nodes in
  # RabbitMQ are equal, this name isn't exactly fair, so what this role means
  # here is "start a RabbitMQ server and connect it to the server on the machine
  # playing the 'rabbitmq_master' role."
  def self.start_slave(master_ip)
    Djinn.log_debug("Starting RabbitMQ Slave")
    self.write_cookie()
    self.erase_local_files()
    
    # Wait for RabbitMQ on master node to come up
    Djinn.log_debug("Waiting for RabbitMQ on master node to come up")
    HelperFunctions.sleep_until_port_is_open(master_ip, SERVER_PORT)

    # start the server, reset it to join the head node
    # TODO(cgb): This looks like this assumes that the head node is
    # appscale-image0 - true for default deployments but not necessarily
    # so in advanced placement scenarios. Change accordingly.
    start_cmds = ["rabbitmqctl start_app",
                  "rabbitmqctl stop_app",
                  "rabbitmqctl reset",
                  "rabbitmq-server -detached -setcookie #{HelperFunctions.get_secret()}",
                  "rabbitmqctl cluster rabbit@appscale-image0",
                  "rabbitmqctl start_app"]
    full_cmd = "#{start_cmds.join('; ')}"

    Djinn.log_run("#{full_cmd}")
    Djinn.log_debug("Waiting for RabbitMQ on local node to come up")

    begin
      Timeout::timeout(300) do
        HelperFunctions.sleep_until_port_is_open("localhost", SERVER_PORT)
        Djinn.log_debug("Done starting rabbitmq_slave on this node")
      end
    rescue Timeout::Error
      Djinn.log_debug("Waited for RabbitMQ to start, but timed out. " +
        "Proceeding anyways.")
    end
  end


  # Stops the RabbitMQ server on this node.
  # TODO(cgb): It doesn't actually do anything right now - find out what we
  # need to do to stop the server.
  def self.stop()
    Djinn.log_debug("Shutting down RabbitMQ")
    GodInterface.stop(:rabbitmq)
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
  end
    

end
