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
class FailedZooKeeperOperationException < Exception
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
  APPCONTROLLER_PATH = "/appcontroller"


  # The location in ZooKeeper where the Shadow node will back up its state to,
  # and where other nodes will recover that state from.
  APPCONTROLLER_STATE_PATH = "#{APPCONTROLLER_PATH}/state"


  # The location in ZooKeeper that contains a list of the IP addresses that
  # are currently running within AppScale.
  IP_LIST = "#{APPCONTROLLER_PATH}/ips"


  # The location in ZooKeeper that AppControllers write information about their
  # node to, so that others can poll to see if they are alive and what roles
  # they've taken on.
  APPCONTROLLER_NODE_PATH = "#{APPCONTROLLER_PATH}/nodes"


  # The location in ZooKeeper that nodes will try to acquire an ephemeral node
  # for, to use as a lock.
  APPCONTROLLER_LOCK_PATH = "#{APPCONTROLLER_PATH}/lock"


  # The location in ZooKeeper that AppControllers write information about
  # which Google App Engine apps require additional (or fewer) AppServers to
  # handle the amount of traffic they are receiving.
  SCALING_DECISION_PATH = "#{APPCONTROLLER_PATH}/scale"


  # The location in ZooKeeper that the Babel Master and Slaves will read and
  # write data to that should be globally accessible or fault-tolerant.
  BABEL_PATH = "/babel"


  # The location in ZooKeeper that the Babel Master's threads read and write
  # to, to determine the maximum number of machines that should be used to
  # run Babel tasks.
  BABEL_MAX_MACHINES_PATH = "#{BABEL_PATH}/max_slaves_machines"


  # The name of the file that nodes use to store the list of Google App Engine
  # instances that the given node runs.
  APP_INSTANCE = "app_instance"


  ROOT_APP_PATH = "/apps"


  # The contents of files in ZooKeeper whose contents we don't care about
  # (e.g., where we care that's an ephemeral file or needed just to provide
  # a hierarchical filesystem-like interface).
  DUMMY_DATA = ""


  # The amount of time that has to elapse before Zookeeper expires the
  # session (and all ephemeral locks) with our client. Setting this value at
  # or below 10 seconds has historically not been a good idea for us (as
  # sessions repeatedly time out).
  TIMEOUT = 60


  public


  # Initializes a new ZooKeeper connection to the IP address specified.
  # Callers should use this when they know exactly which node hosts ZooKeeper.
  def self.init_to_ip(client_ip, ip)
    Djinn.log_debug("Waiting for #{ip}:#{SERVER_PORT} to open")
    HelperFunctions.sleep_until_port_is_open(ip, SERVER_PORT)

    @@client_ip = client_ip
    @@ip = ip

    if !defined?(@@lock)
      @@lock = Monitor.new
    end

    @@lock.synchronize {
      @@zk = Zookeeper.new("#{ip}:#{SERVER_PORT}", timeout=TIMEOUT)
    }
  end


  # Initializes a new ZooKeeper connection to the "closest" node in the
  # system. "Closeness" is defined as either "this node" (if it runs
  # ZooKeeper), or an arbitrary node that runs ZooKeeper. Callers should use
  # this method when they don't want to determine on their own which
  # ZooKeeper box to connect to.
  def self.init(my_node, all_nodes)
    self.init_to_ip(my_node.private_ip, self.get_zk_location(my_node,
      all_nodes))
  end


  # Creates a new connection to use with ZooKeeper. Useful for scenarios
  # where the ZooKeeper library has terminated our connection but we still
  # need it. Also recreates any ephemeral links that were lost when the
  # connection was disconnected.
  def self.reinitialize()
    self.init_to_ip(@@client_ip, @@ip)
    self.set_live_node_ephemeral_link(@@client_ip)
  end


  def self.add_app_entry(appname, ip, location)
    appname_path = ROOT_APP_PATH + "/#{appname}"
    full_path = appname_path + "/#{ip}"

    # can't just create path in ZK
    # need to do create the nodes at each level

    self.set(ROOT_APP_PATH, DUMMY_DATA, NOT_EPHEMERAL)
    self.set(appname_path, DUMMY_DATA, NOT_EPHEMERAL)
    self.set(full_path, location, EPHEMERAL)
  end


  def self.remove_app_entry(appname, ip)
    appname_path = ROOT_APP_PATH + "/#{appname}/#{ip}"
    self.delete(appname_path)
  end


  def self.get_app_hosters(appname)
    if !defined?(@@zk)
      return []
    end

    appname_path = ROOT_APP_PATH + "/#{appname}"
    app_hosters = self.get_children(appname_path)
    converted = []
    app_hosters.each { |serialized|
      converted << DjinnJobData.deserialize(serialized)
    }
    return converted
  end


  # Erases all of the ZooKeeper entries that correspond to where an app's tar
  # file can be found.
  #
  # Args:
  #   appname: A String corresponding to the appid of the app whose hosting
  #     data we want to erase.
  def self.clear_app_hosters(appname)
    if !defined?(@@zk)
      return
    end

    appname_path = ROOT_APP_PATH + "/#{appname}"
    app_hosters = self.get_children(appname_path)
    app_hosters.each { |host_info|
      self.delete(appname_path + "/#{host_info}")
    }
    return
  end


  def self.get_appcontroller_state()
    return JSON.load(self.get(APPCONTROLLER_STATE_PATH))
  end


  def self.write_appcontroller_state(state)
    # Create the top-level AC dir, then the actual node that stores
    # our data
    self.set(APPCONTROLLER_PATH, DUMMY_DATA, NOT_EPHEMERAL)
    self.set(APPCONTROLLER_STATE_PATH, JSON.dump(state), NOT_EPHEMERAL)
  end


  # Gets a lock that AppControllers can use to have exclusive write access
  # (between other AppControllers) to the ZooKeeper hierarchy located at
  # APPCONTROLLER_PATH. It returns a boolean that indicates whether or not
  # it was able to acquire the lock or not.
  def self.get_appcontroller_lock()
    if !self.exists?(APPCONTROLLER_PATH)
      self.set(APPCONTROLLER_PATH, DUMMY_DATA, NOT_EPHEMERAL)
    end

    info = self.run_zookeeper_operation {
      @@zk.create(:path => APPCONTROLLER_LOCK_PATH, 
        :ephemeral => EPHEMERAL, :data => JSON.dump(@@client_ip))
    }
    if info[:rc].zero? 
      return true
    else # we couldn't get the lock for some reason
      Djinn.log_warn("Couldn't get the AppController lock, saw info " +
        "#{info.inspect}")
      return false
    end
  end


  # Releases the lock that AppControllers use to have exclusive write access,
  # which was acquired via self.get_appcontroller_lock().
  def self.release_appcontroller_lock()
    self.delete(APPCONTROLLER_LOCK_PATH)
  end

  
  # This method provides callers with an easier way to read and write to
  # AppController data in ZooKeeper. This is useful for methods that aren't
  # sure if they already have the ZooKeeper lock or not, but definitely need
  # it and don't want to accidentally cause a deadlock (grabbing the lock when
  # they already have it).
  def self.lock_and_run(&block)
    # Create the ZK lock path if it doesn't exist.
    if !self.exists?(APPCONTROLLER_PATH)
      self.set(APPCONTROLLER_PATH, DUMMY_DATA, NOT_EPHEMERAL)
    end

    # Try to get the lock, and if we can't get it, see if we already have
    # it. If we do, move on (but don't release it later since this block
    # didn't grab it), and if we don't have it, try again.
    got_lock = false
    begin
      if self.get_appcontroller_lock()
        got_lock = true
      else  # it may be that we already have the lock
        info = self.run_zookeeper_operation {
          @@zk.get(:path => APPCONTROLLER_LOCK_PATH)
        }
        owner = JSON.load(info[:data])
        if @@client_ip == owner
          got_lock = false
        else 
          Djinn.log_warn("Tried to get the lock, but it's currently owned " +
            "by #{owner}. Will try again later.")
          raise Exception
        end
      end
    rescue Exception => e
      Djinn.log_warn("Saw an exception of class #{e.class}")
      Kernel.sleep(5)
      retry
    end

    begin
      yield  # invoke the user's block, and catch any uncaught exceptions
    rescue Exception => except
      Djinn.log_error("Ran caller's block but saw an Exception of class " +
        "#{except.class}")
      raise except
    ensure
      if got_lock
        self.release_appcontroller_lock()
      end
    end
  end


  # Returns a Hash containing the list of the IPs that are currently running
  # within AppScale as well as a timestamp corresponding to the time when the
  # latest node updated this information.
  def self.get_ip_info()
    return JSON.load(self.get(IP_LIST))
  end

  
  # Add the given IP to the list of IPs that we store in ZooKeeper. If the IPs
  # file doesn't exist in ZooKeeper, create it and add in the given IP address.
  # We also update the timestamp associated with this list so that others know
  # to update it as needed.
  def self.add_ip_to_ip_list(ip)
    new_timestamp = 0.0

    if self.exists?(IP_LIST)
      # See if our IP is in the list of IPs that are up, and if not,
      # append it to the list and update the timestamp so that everyone
      # else will update their local copies.
      data = JSON.load(self.get(IP_LIST))
      if !data['ips'].include?(ip)
        Djinn.log_debug("IPs file does not include our IP - adding it in")
        data['ips'] << ip
        new_timestamp = Time.now.to_i
        data['last_updated'] = new_timestamp
        self.set(IP_LIST, JSON.dump(data), NOT_EPHEMERAL)
        Djinn.log_debug("Updated timestamp in ips list to " +
          "#{data['last_updated']}")
      else
        Djinn.log_debug("IPs file already includes our IP - skipping")
      end
    else
      Djinn.log_debug("IPs file does not exist - creating it")
      new_timestamp = Time.now.to_i
      data = {'ips' => [ip], 'last_updated' => new_timestamp}
      self.set(IP_LIST, JSON.dump(data), NOT_EPHEMERAL)
      Djinn.log_debug("Updated timestamp in ips list to " +
        "#{data['last_updated']}")
    end

    return new_timestamp
  end


  # Accesses the list of IP addresses stored in ZooKeeper and removes the
  # given IP address from that list.
  def self.remove_ip_from_ip_list(ip)
    if !self.exists?(IP_LIST)
      return
    end

    data = JSON.load(self.get(IP_LIST))
    data['ips'].delete(ip)
    new_timestamp = Time.now.to_i
    data['last_updated'] = new_timestamp
    self.set(IP_LIST, JSON.dump(data), NOT_EPHEMERAL)
    return new_timestamp
  end


  # Updates the timestamp in the IP_LIST file, to let other nodes know that
  # an update has been made and that they should update their local @nodes
  def self.update_ips_timestamp()
    data = JSON.load(self.get(IP_LIST))
    new_timestamp = Time.now.to_i
    data['last_updated'] = new_timestamp
    self.set(IP_LIST, JSON.dump(data), NOT_EPHEMERAL)
    Djinn.log_debug("Updated timestamp in ips list to #{data['last_updated']}")
    return new_timestamp
  end


  # Queries ZooKeeper for a list of all IPs that are currently up, and then
  # checks if each of those IPs has an ephemeral link indicating that they
  # are alive. Returns an Array of IPs corresponding to failed nodes.
  def self.get_failed_nodes
    failed_nodes = []

    ips = self.get_ip_info['ips']
    Djinn.log_debug("All IPs are [#{ips.join(', ')}]")

    ips.each { |ip|
      if self.exists?("#{APPCONTROLLER_NODE_PATH}/#{ip}/live")
        Djinn.log_debug("Node at #{ip} is alive")
      else
        Djinn.log_debug("Node at #{ip} has failed")
        failed_nodes << ip
      end
    }

    Djinn.log_debug("Failed nodes are [#{failed_nodes.join(', ')}]")
    return failed_nodes
  end


  # Creates files in ZooKeeper that relate to a given AppController's
  # role information, so that other AppControllers can detect if it has
  # failed, and if so, what functionality it was providing at the time.
  def self.write_node_information(node, done_loading)
    # Create the folder for all nodes if it doesn't exist.
    if !self.exists?(APPCONTROLLER_NODE_PATH)
      self.run_zookeeper_operation {
        @@zk.create(:path => APPCONTROLLER_NODE_PATH, 
          :ephemeral => NOT_EPHEMERAL, :data => DUMMY_DATA)
      }
    end

    # Create the folder for this node.
    my_ip_path = "#{APPCONTROLLER_NODE_PATH}/#{node.public_ip}"
    self.run_zookeeper_operation {
      @@zk.create(:path => my_ip_path, :ephemeral => NOT_EPHEMERAL, 
        :data => DUMMY_DATA)
    }

    # Create an ephemeral link associated with this node, which other
    # AppControllers can use to quickly detect dead nodes.
    self.set_live_node_ephemeral_link(node.public_ip)


    # Since we're reporting on the roles we've started, we are done loading
    # roles right now, so write that information for others to read and act on.
    self.set_done_loading(node.public_ip, done_loading)

    # Finally, dump the data from this node to ZK, so that other nodes can
    # reconstruct it as needed.
    self.set_job_data_for_ip(node.public_ip, node.serialize())

    return
  end


  # Deletes all information for a given node, whose data is stored in ZooKeeper.
  def self.remove_node_information(ip)
    return self.recursive_delete("#{APPCONTROLLER_NODE_PATH}/#{ip}")
  end


  # Checks ZooKeeper to see if the given node has finished loading its roles,
  # which it indicates via a file in a particular path.
  def self.is_node_done_loading?(ip)
    if !self.exists?(APPCONTROLLER_NODE_PATH)
      return false
    end

    loading_file = "#{APPCONTROLLER_NODE_PATH}/#{ip}/done_loading"
    if !self.exists?(loading_file)
      return false
    end

    begin
      json_contents = self.get(loading_file)
      return JSON.load(json_contents)
    rescue FailedZooKeeperOperationException
      return false
    end
  end

  
  # Writes the ephemeral link in ZooKeeper that represents a given node
  # being alive. Callers should only use this method to indicate that their
  # own node is alive, and not do it on behalf of other nodes.
  def self.set_live_node_ephemeral_link(ip)
    self.run_zookeeper_operation {
      @@zk.create(:path => "#{APPCONTROLLER_NODE_PATH}/#{ip}/live", 
        :ephemeral => EPHEMERAL, :data => DUMMY_DATA)
    }
  end

  
  # Provides a convenience function that callers can use to indicate that their
  # node is done loading (if they have finished starting/stopping roles), or is
  # not done loading (if they have roles they need to start or stop).
  def self.set_done_loading(ip, val)
    return self.set("#{APPCONTROLLER_NODE_PATH}/#{ip}/done_loading", 
      JSON.dump(val), NOT_EPHEMERAL)
  end


  # Checks ZooKeeper to see if the given node is alive, by checking if the
  # ephemeral file it has created is still present.
  def self.is_node_live?(ip)
    return self.exists?("#{APPCONTROLLER_NODE_PATH}/#{ip}/live")
  end


  # Writes the integer corresponding to the maximum number of nodes that
  # should be acquired (whether they be already running open nodes or newly
  # spawned virtual machines) to become Babel slaves (workers).
  def self.set_max_machines_for_babel_slaves(maximum)
    if !self.exists?(BABEL_PATH)
      self.set(BABEL_PATH, DUMMY_DATA, NOT_EPHEMERAL)
    end

    self.set(BABEL_MAX_MACHINES_PATH, JSON.dump(maximum), NOT_EPHEMERAL)
  end

  
  # Returns the maximum number of nodes that should be used to run Babel
  # jobs (not including the Babel Master).
  def self.get_max_machines_for_babel_slaves()
    if !self.exists?(BABEL_MAX_MACHINES_PATH)
      return 0
    end

    return JSON.load(self.get(BABEL_MAX_MACHINES_PATH))
  end
  

  # Returns an Array of Hashes that correspond to the App Engine applications
  # hosted on the given ip address. Each hash contains the application's name,
  # the IP address (which should be the same as the given IP), and the nginx
  # port that the app is hosted on.
  def self.get_app_instances_for_ip(ip)
    app_instance_file = "#{APPCONTROLLER_NODE_PATH}/#{ip}/#{APP_INSTANCE}"
    if !self.exists?(app_instance_file)
      return []
    end

    json_instances = self.get(app_instance_file)
    return JSON.load(json_instances)
  end


  # Adds an entry to ZooKeeper for the given IP, storing information about the
  # Google App engine application it is hosting that can be used to update the
  # AppDashboard should that node fail.
  def self.add_app_instance(app_name, ip, port)
    app_instance_file = "#{APPCONTROLLER_NODE_PATH}/#{ip}/#{APP_INSTANCE}"
    if self.exists?(app_instance_file)
      json_instances = self.get(app_instance_file)
      instances = JSON.load(json_instances)
    else
      instances = []
    end

    instances << {'app_name' => app_name, 'ip' => ip, 'port' => port}
    self.set(app_instance_file, JSON.dump(instances), NOT_EPHEMERAL)
  end


  # Returns a serialized DjinnJobData string that we store in ZooKeeper for the
  # given IP address, which callers can deserialize to get a DjinnJobData
  # object.
  def self.get_job_data_for_ip(ip)
    return self.get("#{APPCONTROLLER_NODE_PATH}/#{ip}/job_data")
  end


  def self.set_job_data_for_ip(ip, job_data)
    return self.set("#{APPCONTROLLER_NODE_PATH}/#{ip}/job_data", 
      job_data, NOT_EPHEMERAL)
  end


  # Adds the specified role to the given node in ZooKeeper. A node can call this
  # function to add a role to another node, and the other node should take on
  # this role, or a node can call this function to let others know that it is
  # taking on a new role.
  # Callers should acquire the ZK Lock before calling this function.
  # roles should be an Array of Strings, where each String is a role to add
  # node should be a DjinnJobData representing the node that we want to add
  # the roles to
  def self.add_roles_to_node(roles, node)
    old_job_data = self.get_job_data_for_ip(node.public_ip)
    new_node = DjinnJobData.deserialize(old_job_data)
    new_node.add_roles(roles.join(":"))
    new_job_data = new_node.serialize()
    self.set_job_data_for_ip(node.public_ip, new_job_data)
    self.set_done_loading(node.public_ip, false)
    self.update_ips_timestamp()
  end


  # Removes the specified roles from the given node in ZooKeeper. A node can 
  # call this function to remove roles from another node, and the other node 
  # should take on this role, or a node can call this function to let others 
  # know that it is stopping existing roles.
  # Callers should acquire the ZK Lock before calling this function.
  # roles should be an Array of Strings, where each String is a role to remove
  # node should be a DjinnJobData representing the node that we want to remove
  # the roles from
  def self.remove_roles_from_node(roles, node)
    old_job_data = self.get_job_data_for_ip(node.public_ip)
    new_node = DjinnJobData.deserialize(old_job_data)
    new_node.remove_roles(roles.join(":"))
    new_job_data = new_node.serialize()
    self.set_job_data_for_ip(node.public_ip, new_job_data)
    self.set_done_loading(node.public_ip, false)
    self.update_ips_timestamp()
  end


  # Asks ZooKeeper for all of the scaling requests (e.g., scale up or scale
  # down) for the given application.
  #
  # Args:
  #   appid: A String that names the application whose scaling requests we
  #     wish to query.
  # Returns:
  #   An Array of Strings, where each String is a request to either add or
  #   remove AppServers for this application. If no requests have been made
  #   for this application, an empty Array is returned.
  def self.get_scaling_requests_for_app(appid)
    path = "#{SCALING_DECISION_PATH}/#{appid}"
    requestors = self.get_children(path)
    scaling_requests = []
    requestors.each { |ip|
      scaling_requests << self.get("#{path}/#{ip}")
    }
    return scaling_requests
  end


  # Erases all requests to scale AppServers up or down for the named
  # application.
  #
  # Args:
  #   appid: A String that names the application whose scaling requests we
  #     wish to erase.
  def self.clear_scaling_requests_for_app(appid)
    self.recursive_delete("#{SCALING_DECISION_PATH}/#{appid}")
  end


  # Writes a node in ZooKeeper indicating that the named application needs
  # additional AppServers running to serve the amount of traffic currently
  # accessing the caller's machine.
  #
  # Args:
  #   appid: A String that names the application that should be scaled up.
  #   ip: A String that names the IP address of the machine that is requesting
  #     more AppServers for this application.
  # Returns:
  #   true if the request was successfully made, and false otherwise.
  def self.request_scale_up_for_app(appid, ip)
    return self.request_scaling_for_app(appid, ip, :scale_up)
  end


  # Writes a node in ZooKeeper indicating that the named application needs
  # less AppServers running to serve the amount of traffic currently
  # accessing the caller's machine.
  #
  # Args:
  #   appid: A String that names the application that should be scaled down.
  #   ip: A String that names the IP address of the machine that is requesting
  #     less AppServers for this application.
  # Returns:
  #   true if the request was successfully made, and false otherwise.
  def self.request_scale_down_for_app(appid, ip)
    return self.request_scaling_for_app(appid, ip, :scale_down)
  end


  def self.request_scaling_for_app(appid, ip, decision)
    begin
      path = "#{SCALING_DECISION_PATH}/#{appid}/#{ip}"
      self.set(SCALING_DECISION_PATH, DUMMY_DATA, NOT_EPHEMERAL)
      self.set("#{SCALING_DECISION_PATH}/#{appid}", DUMMY_DATA, NOT_EPHEMERAL)
      self.set(path, decision.to_s, NOT_EPHEMERAL)
      return true
    rescue FailedZooKeeperOperationException
      return false
    end
  end


  private


  def self.run_zookeeper_operation(&block)
    begin
      yield
    rescue ZookeeperExceptions::ZookeeperException::ConnectionClosed,
      ZookeeperExceptions::ZookeeperException::NotConnected,
      ZookeeperExceptions::ZookeeperException::SessionExpired

      Djinn.log_warn("Lost our ZooKeeper connection - making a new " +
        "connection and trying again.")
      self.reinitialize()
      Kernel.sleep(1)
      retry
    rescue Exception => e
      Djinn.log_warn("Saw a transient ZooKeeper error of class #{e.class}" +
        " - trying again.")
      Kernel.sleep(1)
      retry
    end
  end


  def self.exists?(key)
    return self.run_zookeeper_operation {
      @@zk.get(:path => key)[:stat].exists
    }
  end


  def self.get(key)
    info = self.run_zookeeper_operation {
      @@zk.get(:path => key)
    }
    if info[:rc].zero?
      return info[:data]
    else
      raise FailedZooKeeperOperationException.new("Failed to get #{key}, " +
        "with info #{info.inspect}")
    end
  end


  def self.get_children(key)
    children = self.run_zookeeper_operation {
      @@zk.get_children(:path => key)[:children]
    }

    if children.nil?
      return []
    else
      return children
    end
  end


  def self.set(key, val, ephemeral)
    retries_left = 5
    begin
      info = {}
      if self.exists?(key)
        info = self.run_zookeeper_operation {
          @@zk.set(:path => key, :data => val)
        }
      else
        info = self.run_zookeeper_operation {
          @@zk.create(:path => key, :ephemeral => ephemeral, :data => val)
        }
      end

      if !info[:rc].zero?
        raise FailedZooKeeperOperationException.new("Failed to set path " +
          "#{key} with data #{val}, ephemeral = #{ephemeral}, saw " +
          "info #{info.inspect}")
      end
    rescue FailedZooKeeperOperationException => e
      retries_left -= 1
      Djinn.log_warn("Saw a failure trying to write to ZK, with " +
        "info [#{e}]")
      if retries_left > 0
        Djinn.log_warn("Retrying write operation, with #{retries_left}" +
          " retries left")
        Kernel.sleep(5)
        retry
      else
        Djinn.log_error("[ERROR] Failed to write to ZK and no retries " +
          "left. Skipping on this write for now.")
      end
    end
  end


  def self.recursive_delete(key)
    child_info = self.get_children(key)
    if child_info.empty?
      return
    end

    child_info.each { |child|
      self.recursive_delete("#{key}/#{child}")
    }

    begin
      self.delete(key)
    rescue FailedZooKeeperOperationException
      Djinn.log_error("Failed to delete key #{key} - continuing onward")
    end
  end


  def self.delete(key)
    info = self.run_zookeeper_operation {
      @@zk.delete(:path => key)
    }
    if !info[:rc].zero?
      Djinn.log_error("Delete failed - #{info.inspect}")
      raise FailedZooKeeperOperationException.new("Failed to delete " +
        " path #{key}, saw info #{info.inspect}")
    end
  end


  def self.get_zk_location(my_node, all_nodes)
    if my_node.is_zookeeper?
      return my_node.private_ip
    end

    zk_node = nil
    all_nodes.each { |node|
      if node.is_zookeeper?
        zk_node = node
        break
      end
    }

    if zk_node.nil?
      no_zks = "No ZooKeeper nodes were found. All nodes are #{nodes}," +
        " while my node is #{my_node}."
      abort(no_zks)
    end

    return zk_node.private_ip
  end


end
