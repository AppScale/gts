#!/usr/bin/ruby

ONE_HOUR = 3600 # seconds
HEARTBEAT_THRESHOLD = 10

class DjinnJobData
  attr_accessor :public_ip, :private_ip, :jobs, :instance_id, :cloud, :ssh_key
  attr_accessor :creation_time, :destruction_time, :failed_heartbeats
 
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

    @ssh_key = File.expand_path("#{APPSCALE_HOME}/.appscale/keys/#{@cloud}/#{keyname}.key")
    @creation_time = nil
    @destruction_time = nil # best variable name EVER
    @failed_heartbeats = 0

    appscale_jobs = ["load_balancer", "shadow"]
    appscale_jobs += ["db_master", "db_slave"]
    appscale_jobs += ["zookeeper"]
    appscale_jobs += ["login"]
    appscale_jobs += ["open"]
    appscale_jobs += ["appengine"] # appengine must go last
        
    appscale_jobs.each { |job|
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
    Djinn.log_debug("serialized myself to #{serialized}")
    return serialized
  end

  def self.deserialize(serialized)
    Djinn.log_debug("serialized is [#{serialized}]")
    split_data = serialized.split(":")
    roles = split_data[0..-2].join(":")
    keyname = split_data[-1].split(".")[0]
    Djinn.log_debug("i'm pretty sure roles is [#{roles}] and keyname is [#{keyname}]")
    return DjinnJobData.new(roles, keyname)
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
      " It was created at #{@creation_time} and should be destroyed at #{@destruction_time}." +
      " It has failed to respond to #{@failed_heartbeats} in a row."
    return status  
  end

  def set_time_info(creation_time, destruction_time)
    @creation_time = creation_time
    @destruction_time = destruction_time
  end

  def should_destroy?
    return false if @creation_time.nil? or @destruction_time.nil?
    return true if @failed_heartbeats > HEARTBEAT_THRESHOLD
    return Time.now > @destruction_time
  end

  def should_extend?
    return false if @creation_time.nil? or @destruction_time.nil?
    # if we are about to kill the VM, don't do it if it's being used
    return should_destroy? && !is_open?
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
