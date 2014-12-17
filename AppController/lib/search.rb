#!/usr/bin/ruby -w


# First-party Ruby libraries
require 'timeout'


# Imports for AppController libraries
$:.unshift File.join(File.dirname(__FILE__))
require 'djinn_job_data'
require 'helperfunctions'
require 'monit_interface'


# To implement support for the Google App Engine Search, we use
# the open source lucene. This module provides
# methods that automatically configure and deploy SOLR.
module Search

  # AppScale install directory  
  APPSCALE_HOME = ENV["APPSCALE_HOME"]

  # The port that SOLR server runs on, by default.
  SOLR_SERVER_PORT = 8983
 
  # The port where the TaskQueue server runs on, by default. 
  SEARCH_SERVER_PORT = 53423

  # The python executable path.
  PYTHON_EXEC = "python"

  # Stop command for search server.
  SEARCH_STOP_CMD = "/bin/kill -9 `ps aux | grep search_server.py | awk {'print $2'}`"

  # Search location file.
  SEARCH_LOCATION_FILE = "/etc/appscale/search_location"

  # SOLR persistent state location.
  SOLR_STATE_DIR = "/opt/appscale/solr/data"

  # Starts a service that we refer to as a "search_master".
  #
  # Args:
  #   clear_data: A boolean that indicates whether or not SOLR state should
  #     be erased before starting SOLR.
  def self.start_master(clear_data)
    Djinn.log_info("Starting Search Master.")

    if clear_data
      self.erase_local_files()
    else
      Djinn.log_debug("Resuming from previous SOLR state if it exists.")
    end

    # First, start up SOLR.
    start_solr()
    # Start up the search server which handles API calls from applications.
    start_search_server()
  end

  # Start up SOLR.
  def self.start_solr()
    Djinn.log_debug("Starting SOLR.")
    Djinn.log_run("mkdir -p #{SOLR_STATE_DIR}")
    Djinn.log_run("cp -r /root/appscale/SearchService/templates/schemaless-appscale /opt/appscale/solr/")
    start_cmd = "/root/appscale/SearchService/solr/solr/bin/solr start -noprompt -s /opt/appscale/solr/schemaless-appscale/solr/"
    stop_cmd = "/root/appscale/SearchService/solr/solr/bin/solr stop -all"
    match_cmd = "-Dsolr.solr.home=/opt/appscale/solr/schemaless-appscale/solr/"
    MonitInterface.start(:solr, start_cmd, stop_cmd, ports=9999,
      env_vars=nil, remote_ip=nil, remote_key=nil, match_cmd=match_cmd)
    HelperFunctions.sleep_until_port_is_open("localhost", SOLR_SERVER_PORT)
    Djinn.log_debug("Done starting SOLR.")
  end

  # Starts the AppScale search server.
  def self.start_search_server()
    Djinn.log_debug("Starting search server on this node.")
    script = "#{APPSCALE_HOME}/SearchService/search_server.py"
    start_cmd = "#{PYTHON_EXEC} #{script}"
    stop_cmd = SEARCH_STOP_CMD
    env_vars = {}
    MonitInterface.start(:search, start_cmd, stop_cmd, SEARCH_SERVER_PORT,
      env_vars)
    HelperFunctions.sleep_until_port_is_open("localhost", SEARCH_SERVER_PORT)
    Djinn.log_debug("Done starting search_server on this node")
  end

  # Stops the SOLR process on this node.
  def self.stop_solr()
    Djinn.log_debug("Stopping SOLR on this node.")
    MonitInterface.stop(:solr)
    Djinn.log_debug("Done stopping SOLR.")
  end

  # Stops SOLR and the search server on this node.
  def self.stop()
    self.stop_search_server()
    self.stop_solr()
  end


  # Stops the AppScale search server.
  def self.stop_search_server()
    Djinn.log_debug("Stopping search_server on this node.")
    MonitInterface.stop(:search)
    Djinn.log_debug("Done stopping search_server on this node.")
  end


  # Erases all the files that SOLR normally writes to, which can be useful
  # to ensure that we start up SOLR without left-over state from previous
  # runs.
  def self.erase_local_files()
    Djinn.log_debug("Erasing SOLR state")
    Djinn.log_run("rm -rf /opt/appscale/solr/schemaless-appscale/")
    Djinn.log_run("rm -rf #{SOLR_STATE_DIR}")
    Djinn.log_debug("Done removing SOLR state")
  end

end
