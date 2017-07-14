#!/usr/bin/ruby


require 'rubygems'
require 'json'


$:.unshift File.join(File.dirname(__FILE__), "..")
require 'djinn'
require 'helperfunctions'


# A class that represents a single node running in AppScale. It provides methods
# to easily see the IP address of a node, how to access it, and what roles
# (jobs) a node is currently running. If running in a cloud infrastructure, it
# also contains info about when we spawned the node (helpful for optimizing
# costs, which may charge on an hourly basis).
class DjinnJobData
  attr_accessor :public_ip, :private_ip, :jobs, :instance_id, :cloud, :ssh_key
  attr_accessor :disk
 

  def initialize(json_data, keyname)
    if json_data.class != Hash
      HelperFunctions.log_and_crash("Roles must be a Hash, not a " +
        "#{json_data.class} containing #{json_data}")
    end

    @public_ip = json_data['public_ip']
    @private_ip = json_data['private_ip']

    jobs = json_data['jobs']
    if jobs.class == Array
      @jobs = jobs
    elsif jobs.class == String
      @jobs = [jobs]
    else
      HelperFunctions.log_and_crash("Jobs must be an Array or String, not " +
        "a #{jobs.class} containing #{jobs}")
    end

    @cloud = "cloud1"
    @instance_id = 'i-APPSCALE'
    @instance_id = json_data['instance_id'] if json_data['instance_id']
    @disk = json_data['disk']
    @ssh_key = File.expand_path("/etc/appscale/keys/#{@cloud}/#{keyname}.key")
  end


  def add_roles(roles)
    new_jobs = roles.split(":")
    @jobs = (@jobs + new_jobs).uniq
    @jobs.delete("open")
  end


  def remove_roles(roles)
    new_jobs = roles.split(":")
    @jobs = (@jobs - new_jobs)
    @jobs = ["open"] if @jobs.empty?
  end


  def set_roles(roles)
    @jobs = roles.split(":")
  end


  # Produces a Hash that contains all the information contained in this
  # object.
  def to_hash
    return {
      'public_ip' => @public_ip,
      'private_ip' => @private_ip,
      'jobs' => @jobs,
      'instance_id' => @instance_id,
      'cloud' => @cloud,
      'ssh_key' => @ssh_key,
      'disk' => @disk
    }
  end


  def to_s
    if @jobs.empty?
      jobs = "not doing anything"
    else
      jobs = @jobs.join(', ')
    end

    status = "Node in cloud #{@cloud} with instance id #{@instance_id}" +
      " responds to ssh key #{@ssh_key}, has pub IP #{@public_ip}," +
      " priv IP #{@private_ip}, and is currently #{jobs}. "

    if @disk.nil?
      status += "It does not back up its data to a persistent disk."
    else
      status += "It backs up data to a persistent disk with name #{@disk}."
    end

    return status  
  end


  # method_missing: will intercept calls to is_load_balancer?, is_appengine?
  # and so on, without having all these methods to copy paste
  # as of writing this only the two named methods are in use
  # TODO: remove this and place dynamic method adds in initialize
  def method_missing(id, *args, &block)
    if id.to_s =~ /is_(.*)\?/
      if @jobs.include?($1)
        return true
      else
        return false
      end
    end
    super
  end

  # In the process of removing roles, db_slave is no longer added to non
  # db_master nodes. A node that is a database and is not the db_master is
  # now considered a db_slave.
  def is_db_slave?
    return @jobs.include?('db_slave') ||
        (@jobs.include?('database') && !@jobs.include?('db_master'))
  end

  # In the process of removing roles, taskqueue_slave is no longer added to non
  # taskqueue_master nodes. A node that is a taskqueue and is not the
  # taskqueue_master is now considered a taskqueue_slave.
  def is_taskqueue_slave?
    return @jobs.include?('taskqueue_slave') ||
        (@jobs.include?('taskqueue') && !@jobs.include?('taskqueue_master'))
  end

  def eql?(other_node)
    self.hash.eql?(other_node.hash)
  end

  def hash
    # Consider two nodes to be the same if they have the same SSH key,
    # private IP, and public IP.
    [@ssh_key, @private_ip, @public_ip].join().hash()
  end

end
