#!/usr/bin/ruby -w

# First-party Ruby libraries.
require 'timeout'

# Imports for AppController libraries
$:.unshift File.join(File.dirname(__FILE__))
require 'node_info'
require 'helperfunctions'
require 'service_helper'

# To implement support for the Google App Engine Search, we use
# the open source SOLR. This module provides
# methods that automatically configure and deploy SOLR.
module Search
  # AppScale install directory.
  APPSCALE_HOME = ENV["APPSCALE_HOME"] || File.join('/', 'root', 'appscale')

  # The port that SOLR server runs on, by default.
  SOLR_SERVER_PORT = 8983

  # The port where the TaskQueue server runs on, by default.
  SEARCH_SERVER_PORT = 53423

  # The python executable path.
  PYTHON_EXEC = 'python'.freeze

  # Search location file.
  SEARCH_LOCATION_FILE = '/etc/appscale/search_ip'.freeze

  # Service name for use with helper
  SERVICE_NAME_SEARCH = 'appscale-search'.freeze

  # Service name for use with helper
  SERVICE_NAME_SOLR = 'appscale-solr'.freeze

  # The location of SOLR source code.
  SOLR_CODE_DIR = File.join(APPSCALE_HOME, 'SearchService', 'solr', 'solr')

  # SOLR persistent state location.
  SOLR_STATE_DIR = '/opt/appscale/solr/data'.freeze

  # Starts a service that we refer to as a "search_master".
  #
  # Args:
  #   clear_data: A boolean that indicates whether or not SOLR state should
  #     be erased before starting SOLR.
  def self.start_master(clear_data, verbose)
    Djinn.log_info('Starting Search Master.')

    if clear_data
      erase_local_files
    else
      Djinn.log_debug('Resuming from previous SOLR state if it exists.')
    end

    # First, start up SOLR.
    start_solr
    # Start up the search server which handles API calls from applications.
    start_search_server(verbose)
  end

  # Starts up SOLR.
  def self.start_solr
    Djinn.log_debug('Starting SOLR.')
    ServiceHelper.start(SERVICE_NAME_SOLR)
    HelperFunctions.sleep_until_port_is_open("localhost", SOLR_SERVER_PORT)
    Djinn.log_debug('Done starting SOLR.')
  end

  # Starts the AppScale search server.
  def self.start_search_server(verbose)
    service_env = {}
    service_env[:APPSCALE_OPTION_VERBOSE] = '--verbose' if verbose
    ServiceHelper.write_environment(SERVICE_NAME_SEARCH, service_env)
    Djinn.log_debug('Starting search server on this node.')
    ServiceHelper.start(SERVICE_NAME_SEARCH)
    HelperFunctions.sleep_until_port_is_open('localhost', SEARCH_SERVER_PORT)
    Djinn.log_debug('Done starting search_server on this node.')
  end

  # Stops the SOLR process on this node.
  def self.stop_solr
    Djinn.log_debug('Stopping SOLR on this node.')
    ServiceHelper.stop(SERVICE_NAME_SOLR)
    Djinn.log_debug('Done stopping SOLR.')
  end

  # Stops SOLR and the search server on this node.
  def self.stop
    stop_search_server
    stop_solr
  end

  # Stops the AppScale search server.
  def self.stop_search_server
    Djinn.log_debug('Stopping search_server on this node.')
    ServiceHelper.stop(SERVICE_NAME_SEARCH)
    Djinn.log_debug('Done stopping search_server on this node.')
  end

  # Erases all the files that SOLR normally writes to, which can be useful
  # to ensure that we start up SOLR without left-over state from previous
  # runs.
  def self.erase_local_files
    Djinn.log_debug('Erasing SOLR state.')
    Djinn.log_run('rm -rf /opt/appscale/solr/schemaless-appscale/')
    Djinn.log_run("rm -rf #{SOLR_STATE_DIR}")
    Djinn.log_debug('Done removing SOLR state.')
  end
end


module Search2
  # The port that we should run haproxy on, to distribute requests to
  # various search servers running on search ndoes.
  PROXY_PORT = 9999

  # The name that haproxy should use as the identifier for Search server
  # when we write its configuration files.
  NAME = 'appscale-search_server'.freeze

  # If we fail to get the number of processors we set default number of
  # search servers to this value.
  DEFAULT_NUM_SERVERS = 1

  # Search server processes to CPU core multiplier.
  MULTIPLIER = 0.75
end
