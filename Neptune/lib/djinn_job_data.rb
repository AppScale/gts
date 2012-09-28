#!/usr/bin/ruby


$:.unshift File.join(File.dirname(__FILE__), "..")
require 'neptune_manager'




# A class that represents a single node running in AppScale. It provides methods
# to easily see the IP address of a node, how to access it, and what roles
# (jobs) a node is currently running. If running in a cloud infrastructure, it
# also contains info about when we spawned the node (helpful for optimizing
# costs, which may charge on an hourly basis).
class DjinnJobData


  # The location where we store Neptune job type files, each of which defining
  # 'start/stop_job_master' and 'start/stop_job_slave' functions.
  JOB_TYPES_FOLDER = File.join(File.dirname(__FILE__), "job_types")


  # A constant representing the number of seconds in an hour, useful for the
  # per-hour metering performed by Amazon Web Services.
  ONE_HOUR = 3600


  attr_accessor :public_ip, :private_ip, :jobs, :instance_id, :cloud, :ssh_key


  attr_accessor :creation_time, :destruction_time
 

  def initialize(roles, keyname)
    # format: "publicIP:privateIP:load_balancer:appengine:table-master:table-slave:instance_id:cloud"

    if roles.class != String
      abort("Roles must be a string, not a #{roles.class} containing #{roles}")
    end

    split_roles = roles.split(":")

    @public_ip = split_roles[0]
    @private_ip = split_roles[1]
    @jobs = []
    @instance_id = split_roles[-2]

    # TODO: this is a bit hackey - would like to fix this someday
    if split_roles[-1].include?(".key")
      @cloud = split_roles[-2]
    else
      @cloud = split_roles[-1]
    end

    @ssh_key = File.expand_path("/etc/appscale/keys/#{@cloud}/#{keyname}.key")
    @creation_time = nil
    @destruction_time = nil  # best variable name EVER

    neptune_jobs = ["shadow"]  # add in shadow since methods call .is_shadow?
    Dir.foreach(JOB_TYPES_FOLDER) { |filename|
      if filename =~ /\A(.*)_helper.rb\Z/
        neptune_jobs << "#{$1}_master"
        neptune_jobs << "#{$1}_slave"
      end
    } 
        
    neptune_jobs.each { |job|
      @jobs << job if roles.include?(job)
    }
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


  # not the best name for this but basically correct
  def serialize
    keyname = @ssh_key.split("/")[-1]
    serialized = "#{@public_ip}:#{@private_ip}:#{@jobs.join(':')}:#{@instance_id}:#{@cloud}:#{keyname}"
    NeptuneManager.log("Serialized current node to #{serialized}")
    return serialized
  end


  def self.deserialize(serialized)
    NeptuneManager.log("serialized is [#{serialized}]")
    split_data = serialized.split(":")
    roles = split_data[0..-2].join(":")
    keyname = split_data[-1].split(".")[0]
    NeptuneManager.log("Current roles are [#{roles}] and keyname is [#{keyname}]")
    return DjinnJobData.new(roles, keyname)
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
      'creation_time' => @creation_time,
      'destruction_time' => @destruction_time
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
      " priv IP #{@private_ip}, and is currently #{@jobs.join(', ')}." +
      " It was created at #{@creation_time} and should be destroyed at " +
      " #{@destruction_time}."
    return status  
  end


  def set_time_info(creation_time, destruction_time)
    @creation_time = creation_time
    @destruction_time = destruction_time
  end


  def should_destroy?
    return false if @creation_time.nil? or @destruction_time.nil?
    if Time.now > @destruction_time
      return true
    else
      return false
    end
  end


  def should_extend?
    return false if @creation_time.nil? or @destruction_time.nil?
    # if we are about to kill the VM, don't do it if it's being used
    if should_destroy? and !@jobs.include?("open")
      return true
    else
      return false
    end
  end


  def extend_time
    return if @creation_time.nil? or @destruction_time.nil?
    @destruction_time += ONE_HOUR
  end


  # method_missing: will intercept calls to is_load_balancer?, is_appengine?
  # and so on, without having all these methods to copy pasta
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


end
