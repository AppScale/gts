#!/usr/bin/ruby -w

require 'fileutils'
require 'monitor'

$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'

require 'rubygems'
require 'json'
require 'zookeeper'

# A class of exceptions that we throw whenever we perform a ZooKeeper
# operation that does not return successfully (but does not normally
# throw an exception).
class FailedZooKeeperOperationException < StandardError
end

# Indicates that the requested version node was not found.
class VersionNotFound < StandardError
end

# Indicates that the requested configuration was not found.
class ConfigNotFound < StandardError
end

# The AppController employs the open source software ZooKeeper as a highly
# available naming service, to store and retrieve information about the status
# of applications hosted within AppScale. This class provides methods to
# communicate with ZooKeeper, and automates commonly performed functions by the
# AppController.
class ZKInterface
  # The port that ZooKeeper runs on in AppScale deployments.
  SERVER_PORT = 2181

  EPHEMERAL = true

  NOT_EPHEMERAL = false

  # The location in ZooKeeper where AppControllers can read and write
  # data to.
  APPCONTROLLER_PATH = '/appcontroller'.freeze

  # The location in ZooKeeper where the Shadow node will back up its state to,
  # and where other nodes will recover that state from.
  APPCONTROLLER_STATE_PATH = "#{APPCONTROLLER_PATH}/state".freeze

  # The ZooKeeper node where datastore servers register themselves.
  DATASTORE_REGISTRY_PATH = '/appscale/datastore/servers'

  # The ZooKeeper node where search servers register themselves.
  SEARCH2_REGISTRY_PATH = '/appscale/search/live_nodes'

  # The location in ZooKeeper that AppControllers write information about their
  # node to, so that others can poll to see if they are alive and what roles
  # they've taken on.
  APPCONTROLLER_NODE_PATH = "#{APPCONTROLLER_PATH}/nodes".freeze

  # The location in ZooKeeper that nodes will try to acquire an ephemeral node
  # for, to use as a lock.
  APPCONTROLLER_LOCK_PATH = "#{APPCONTROLLER_PATH}/lock".freeze

  # The location in ZooKeeper that AppControllers write information about
  # which Google App Engine apps require additional (or fewer) AppServers to
  # handle the amount of traffic they are receiving.
  SCALING_DECISION_PATH = "#{APPCONTROLLER_PATH}/scale".freeze

  # The name of the file that nodes use to store the list of Google App Engine
  # instances that the given node runs.
  APP_INSTANCE = 'app_instance'.freeze

  ROOT_APP_PATH = '/apps'.freeze

  # The contents of files in ZooKeeper whose contents we don't care about
  # (e.g., where we care that's an ephemeral file or needed just to provide
  # a hierarchical filesystem-like interface).
  DUMMY_DATA = ''.freeze

  # The amount of time that has to elapse before Zookeeper expires the
  # session (and all ephemeral locks) with our client. Setting this value at
  # or below 10 seconds has historically not been a good idea for us (as
  # sessions repeatedly time out).
  TIMEOUT = 60

  # Initializes a new ZooKeeper connection to the IP address specified.
  # Callers should use this when they know exactly which node hosts ZooKeeper.
  def self.init_to_ip(client_ip, ip)
    Djinn.log_debug("Waiting for #{ip}:#{SERVER_PORT} to open")
    HelperFunctions.sleep_until_port_is_open(ip, SERVER_PORT)

    @@client_ip = client_ip
    @@ip = ip

    @@lock = Monitor.new unless defined?(@@lock)
    @@lock.synchronize {
      if defined?(@@zk)
        Djinn.log_debug('Closing old connection to zookeeper.')
        @@zk.close!
      end
      Djinn.log_debug("Opening connection to zookeeper at #{ip}.")
      @@zk = Zookeeper.new("#{ip}:#{SERVER_PORT}", TIMEOUT)
    }
  end

  # This method check if we are already connected to a zookeeper server.
  #
  # Returns:
  #   A boolean to indicate if we are already connected to a zookeeper
  #   server.
  def self.is_connected?
    ret = false
    ret = @@zk.connected? if defined?(@@zk)
    Djinn.log_debug("Connection status with zookeeper server: #{ret}.")
    ret
  end

  # Creates a new connection to use with ZooKeeper. Useful for scenarios
  # where the ZooKeeper library has terminated our connection but we still
  # need it. Also recreates any ephemeral links that were lost when the
  # connection was disconnected.
  def self.reinitialize
    init_to_ip(@@client_ip, @@ip)
    set_live_node_ephemeral_link(@@client_ip)
  end

  def self.add_revision_entry(revision_key, ip, md5)
    revision_path = "#{ROOT_APP_PATH}/#{revision_key}/#{ip}"
    set(revision_path, md5, NOT_EPHEMERAL)
  end

  def self.remove_revision_entry(revision_key, ip)
    delete("#{ROOT_APP_PATH}/#{revision_key}/#{ip}")
  end

  def self.get_revision_hosters(revision_key, keyname)
    revision_hosters = get_children("#{ROOT_APP_PATH}/#{revision_key}")
    converted = []
    revision_hosters.each { |host|
      converted << NodeInfo.new(get_job_data_for_ip(host), keyname)
    }
    converted
  end

  def self.get_revision_md5(revision_key, ip)
    get("#{ROOT_APP_PATH}/#{revision_key}/#{ip}").chomp
  end

  def self.get_appcontroller_state
    JSON.load(get(APPCONTROLLER_STATE_PATH))
  end

  def self.write_appcontroller_state(state)
    # Create the top-level AC dir, then the actual node that stores
    # our data
    set(APPCONTROLLER_PATH, DUMMY_DATA, NOT_EPHEMERAL)
    set(APPCONTROLLER_STATE_PATH, JSON.dump(state), NOT_EPHEMERAL)
  end

  # Gets a lock that AppControllers can use to have exclusive write access
  # (between other AppControllers) to the ZooKeeper hierarchy located at
  # APPCONTROLLER_PATH. It returns a boolean that indicates whether or not
  # it was able to acquire the lock or not.
  def self.get_appcontroller_lock
    unless exists?(APPCONTROLLER_PATH)
      set(APPCONTROLLER_PATH, DUMMY_DATA, NOT_EPHEMERAL)
    end

    info = run_zookeeper_operation {
      @@zk.create(path: APPCONTROLLER_LOCK_PATH, ephemeral: EPHEMERAL,
                  data: @@client_ip)
    }
    return true if info[:rc].zero?

    Djinn.log_warn("Couldn't get the AppController lock, saw info " \
                   "#{info.inspect}")
    false
  end

  # Releases the lock that AppControllers use to have exclusive write access,
  # which was acquired via self.get_appcontroller_lock().
  def self.release_appcontroller_lock
    delete(APPCONTROLLER_LOCK_PATH)
  end

  # This method provides callers with an easier way to read and write to
  # AppController data in ZooKeeper. This is useful for methods that aren't
  # sure if they already have the ZooKeeper lock or not, but definitely need
  # it and don't want to accidentally cause a deadlock (grabbing the lock when
  # they already have it).
  def self.lock_and_run(&block)
    # Create the ZK lock path if it doesn't exist.
    unless exists?(APPCONTROLLER_PATH)
      set(APPCONTROLLER_PATH, DUMMY_DATA, NOT_EPHEMERAL)
    end

    # Try to get the lock, and if we can't get it, see if we already have
    # it. If we do, move on (but don't release it later since this block
    # didn't grab it), and if we don't have it, try again.
    got_lock = false
    begin
      if get_appcontroller_lock
        got_lock = true
      else # it may be that we already have the lock
        info = run_zookeeper_operation {
          @@zk.get(path: APPCONTROLLER_LOCK_PATH)
        }
        owner = JSON.load(info[:data])
        if @@client_ip == owner
          got_lock = false
        else
          raise "Tried to get the lock, but it's currently owned by #{owner}."
        end
      end
    rescue => e
      sleep_time = 5
      Djinn.log_warn("Saw #{e.inspect}. Retrying in #{sleep_time} seconds.")
      Kernel.sleep(sleep_time)
      retry
    end

    begin
      yield  # invoke the user's block, and catch any uncaught exceptions
    rescue => except
      Djinn.log_error("Ran caller's block but saw an Exception of class " \
        "#{except.class}")
      raise except
    ensure
      release_appcontroller_lock if got_lock
    end
  end

  # Creates files in ZooKeeper that relate to a given AppController's
  # role information, so that other AppControllers can detect if it has
  # failed, and if so, what functionality it was providing at the time.
  def self.write_node_information(node, done_loading)
    # Create the folder for all nodes if it doesn't exist.
    unless exists?(APPCONTROLLER_NODE_PATH)
      run_zookeeper_operation {
        @@zk.create(path: APPCONTROLLER_NODE_PATH,
                    ephemeral: NOT_EPHEMERAL, data: DUMMY_DATA)
      }
    end

    # Create the folder for this node.
    my_ip_path = "#{APPCONTROLLER_NODE_PATH}/#{node.private_ip}"
    run_zookeeper_operation {
      @@zk.create(path: my_ip_path, ephemeral: NOT_EPHEMERAL,
                  data: DUMMY_DATA)
    }

    # Create an ephemeral link associated with this node, which other
    # AppControllers can use to quickly detect dead nodes.
    set_live_node_ephemeral_link(node.private_ip)

    # Since we're reporting on the roles we've started, we are done loading
    # roles right now, so write that information for others to read and act on.
    set_done_loading(node.private_ip, done_loading)

    # Finally, dump the data from this node to ZK, so that other nodes can
    # reconstruct it as needed.
    set_job_data_for_ip(node.private_ip, node.to_hash)
  end

  # Deletes all information for a given node, whose data is stored in ZooKeeper.
  def self.remove_node_information(ip)
    recursive_delete("#{APPCONTROLLER_NODE_PATH}/#{ip}")
  end

  # Checks ZooKeeper to see if the given node has finished loading its roles,
  # which it indicates via a file in a particular path.
  def self.is_node_done_loading?(ip)
    return false unless exists?(APPCONTROLLER_NODE_PATH)

    loading_file = "#{APPCONTROLLER_NODE_PATH}/#{ip}/done_loading"
    return false unless exists?(loading_file)

    begin
      contents = get(loading_file)
      return contents == 'true'
    rescue FailedZooKeeperOperationException
      return false
    end
  end

  # Writes the ephemeral link in ZooKeeper that represents a given node
  # being alive. Callers should only use this method to indicate that their
  # own node is alive, and not do it on behalf of other nodes.
  def self.set_live_node_ephemeral_link(ip)
    run_zookeeper_operation {
      @@zk.create(path: "#{APPCONTROLLER_NODE_PATH}/#{ip}/live",
                  ephemeral: EPHEMERAL, data: DUMMY_DATA)
    }
  end

  # Provides a convenience function that callers can use to indicate that their
  # node is done loading (if they have finished starting/stopping roles), or is
  # not done loading (if they have roles they need to start or stop).
  def self.set_done_loading(ip, val)
    zk_value = val ? 'true' : 'false'
    set("#{APPCONTROLLER_NODE_PATH}/#{ip}/done_loading",
        zk_value, NOT_EPHEMERAL)
  end

  # Checks ZooKeeper to see if the given node is alive, by checking if the
  # ephemeral file it has created is still present.
  def self.is_node_live?(ip)
    exists?("#{APPCONTROLLER_NODE_PATH}/#{ip}/live")
  end

  def self.get_job_data_for_ip(ip)
    JSON.load(get("#{APPCONTROLLER_NODE_PATH}/#{ip}/job_data"))
  end

  def self.set_job_data_for_ip(ip, job_data)
    set("#{APPCONTROLLER_NODE_PATH}/#{ip}/job_data",
        JSON.dump(job_data), NOT_EPHEMERAL)
  end

  def self.get_versions
    active_versions = []
    get_children('/appscale/projects').each { |project_id|
      services_node = "/appscale/projects/#{project_id}/services"
      get_children(services_node).each { |service_id|
        versions_node = "/appscale/projects/#{project_id}/services/" \
          "#{service_id}/versions"
        get_children(versions_node).each { |version_id|
          active_versions << [project_id, service_id,
                              version_id].join(Djinn::VERSION_PATH_SEPARATOR)
        }
      }
    }
    active_versions
  end

  def self.get_version_details(project_id, service_id, version_id)
    version_node = "/appscale/projects/#{project_id}/services/#{service_id}" \
      "/versions/#{version_id}"
    begin
      version_details_json = get(version_node)
    rescue FailedZooKeeperOperationException
      raise VersionNotFound,
            "#{project_id}/#{service_id}/#{version_id} does not exist"
    end
    JSON.load(version_details_json)
  end

  def self.get_cron_config(project_id)
    cron_node = "/appscale/projects/#{project_id}/cron"
    begin
      cron_config_json = self.get(cron_node)
    rescue FailedZooKeeperOperationException
      raise ConfigNotFound, "Cron configuration not found for #{project_id}"
    end
    return JSON.load(cron_config_json)
  end

  def self.get_datastore_servers
    return get_children(DATASTORE_REGISTRY_PATH).map { |server|
      server = server.split(':')
      server[1] = server[1].to_i
      server
    }
  end

  def self.get_search2_servers
    return get_children(SEARCH2_REGISTRY_PATH).map { |server|
      server = server.split(':')
      server[1] = server[1].to_i
      server
    }
  end

  def self.set_machine_assignments(machine_ip, assignments)
    assignments_node = '/appscale/assignments'
    ensure_path(assignments_node)
    machine_node = [assignments_node, machine_ip].join('/')
    begin
      current_assignments = get_detailed(machine_node)
      assignments = JSON.load(current_assignments[:data]).merge assignments
      set(machine_node, JSON.dump(assignments), NOT_EPHEMERAL,
          current_assignments[:version])
    rescue FailedZooKeeperOperationException
      set(machine_node, JSON.dump(assignments), NOT_EPHEMERAL)
    end
  end

  # Defines deployment-wide defaults for runtime parameters.
  def self.set_runtime_params(parameters)
    runtime_params_node = '/appscale/config/runtime_parameters'
    ensure_path('/appscale/config')
    set(runtime_params_node, JSON.dump(parameters), false)
  end

  # Writes new configs for node stats profiling to zookeeper.
  def self.update_hermes_nodes_profiling_conf(is_enabled, interval)
    configs_node = '/appscale/stats/profiling/nodes'
    ensure_path(configs_node)
    configs = {
      'enabled' => is_enabled,
      'interval' => interval
    }
    set(configs_node, JSON.dump(configs), NOT_EPHEMERAL)
  end

  # Writes new configs for processes stats profiling to zookeeper
  def self.update_hermes_processes_profiling_conf(is_enabled, interval, is_detailed)
    configs_node = '/appscale/stats/profiling/processes'
    ensure_path(configs_node)
    configs = {
      'enabled' => is_enabled,
      'interval' => interval,
      'detailed' => is_detailed
    }
    set(configs_node, JSON.dump(configs), NOT_EPHEMERAL)
  end

  # Writes new configs for proxies stats profiling to zookeeper
  def self.update_hermes_proxies_profiling_conf(is_enabled, interval, is_detailed)
    configs_node = '/appscale/stats/profiling/proxies'
    ensure_path(configs_node)
    configs = {
      'enabled' => is_enabled,
      'interval' => interval,
      'detailed' => is_detailed
    }
    set(configs_node, JSON.dump(configs), NOT_EPHEMERAL)
  end

  def self.run_zookeeper_operation(&block)
    begin
      yield
    rescue ZookeeperExceptions::ZookeeperException::ConnectionClosed,
      ZookeeperExceptions::ZookeeperException::NotConnected,
      ZookeeperExceptions::ZookeeperException::SessionExpired

      Djinn.log_warn('Lost our ZooKeeper connection - making a new ' \
        'connection and trying again.')
      reinitialize
      Kernel.sleep(1)
      retry
    rescue => e
      backtrace = e.backtrace.join("\n")
      Djinn.log_warn("Saw a transient ZooKeeper error: #{e}\n#{backtrace}")
      Kernel.sleep(1)
      retry
    end
  end

  def self.exists?(key)
    unless defined?(@@zk)
      raise FailedZooKeeperOperationException.new('ZKinterface has not ' \
        'been initialized yet.')
    end

    self.run_zookeeper_operation {
      @@zk.get(path: key)[:stat].exists
    }
  end

  def self.get_detailed(key)
    unless defined?(@@zk)
      raise FailedZooKeeperOperationException.new('ZKinterface has not ' \
        'been initialized yet.')
    end

    info = run_zookeeper_operation { @@zk.get(path: key) }
    if info[:rc].zero?
      return info
    else
      raise FailedZooKeeperOperationException.new("Failed to get #{key}, " \
        "with info #{info.inspect}")
    end
  end

  def self.get(key)
    get_detailed(key)[:data]
  end

  def self.get_children(key)
    unless defined?(@@zk)
      raise FailedZooKeeperOperationException.new('ZKinterface has not ' \
        'been initialized yet.')
    end

    response = run_zookeeper_operation {
      @@zk.get_children(:path => key)
    }
    if response[:rc] != Zookeeper::Constants::ZOK
      raise FailedZooKeeperOperationException.new(
        "Failed to get children for #{key}, response: #{response.inspect}")
    end

    children = response[:children]
    if children.nil?
      return []
    else
      return children
    end
  end

  # Recursively create a path if it doesn't exist.
  def self.ensure_path(path)
    # Remove preceding slash.
    nodes = path.split('/')[1..-1]
    i = 0
    while i < nodes.length
      node = '/' + nodes[0..i].join('/')
      run_zookeeper_operation {
        @@zk.create(path: node)
      }
      i += 1
    end
  end

  def self.set(key, val, ephemeral, version=nil)
    unless defined?(@@zk)
      raise FailedZooKeeperOperationException.new('ZKinterface has not ' \
        'been initialized yet.')
    end

    retries_left = 5
    begin
      info = {}
      if exists?(key)
        info = run_zookeeper_operation {
          @@zk.set(path: key, data: val, version: version)
        }
      elsif version.nil?
        info = run_zookeeper_operation {
          @@zk.create(path: key, ephemeral: ephemeral, data: val)
        }
      else
        raise FailedZooKeeperOperationException.new('Can not update ' \
        'node #{key} with version #{version} as it was deleted.')
      end

      unless info[:rc].zero?
        raise FailedZooKeeperOperationException.new('Failed to set path ' \
          "#{key} with data #{val}, ephemeral = #{ephemeral}, saw " \
          "info #{info.inspect}")
      end
    rescue FailedZooKeeperOperationException => e
      retries_left -= 1
      Djinn.log_warn('Saw a failure trying to write to ZK, with ' \
        "info [#{e}]")
      if retries_left > 0
        Djinn.log_warn("Retrying write operation, with #{retries_left}" \
          ' retries left')
        Kernel.sleep(5)
        retry
      else
        Djinn.log_error('[ERROR] Failed to write to ZK and no retries ' \
          'left. Skipping on this write for now.')
      end
    end
  end

  def self.recursive_delete(key)
    child_info = get_children(key)
    return if child_info.empty?

    child_info.each { |child|
      recursive_delete("#{key}/#{child}")
    }

    begin
      delete(key)
    rescue FailedZooKeeperOperationException
      Djinn.log_error("Failed to delete key #{key} - continuing onward")
    end
  end

  def self.delete(key)
    unless defined?(@@zk)
      raise FailedZooKeeperOperationException.new('ZKinterface has not ' \
        'been initialized yet.')
    end

    info = run_zookeeper_operation {
      @@zk.delete(path: key)
    }
    unless info[:rc].zero?
      Djinn.log_error("Delete failed - #{info.inspect}")
      raise FailedZooKeeperOperationException.new('Failed to delete ' \
        " path #{key}, saw info #{info.inspect}")
    end
  end
end
