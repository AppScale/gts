#!/usr/bin/ruby

require 'base64'

# The current costs for EC2 instances in the East Coast region.
# TODO(cgb): Find out some way to get this dynamically so we can record
# costs in more than one region, or utilize clouds with a different
# cloud model (e.g., community or private clouds).
COST = {"m1.large" => 0.36}

# EC2 meters on a per-hour basis, so keep a constant for later use that
# corresponds to a single hour.
ONE_HOUR = 3600.0


class NeptuneJobData
  attr_accessor :name, :num_nodes, :start_time, :end_time, :instance_type
  
  def initialize(name, num_nodes, start_time, end_time, instance_type)
    @name = name
    @num_nodes = num_nodes
    @start_time = start_time
    @end_time = end_time
    @instance_type = instance_type
  end

  def total_time
    @end_time - @start_time
  end

  # Computes the cost incurred to utilize the number of nodes in this job on a
  # per-hour basis. Right now, we only assume a constant price per node.
  def cost
    hours_used = (total_time / ONE_HOUR).ceil
    return @num_nodes * hours_used * COST[@instance_type]
  end

  # Returns a string version of this object's info. Since to_hash already does
  # this in hash form, just use that and return it as a String.
  def to_s
    return to_hash.inspect
  end

  def to_hash
    return {
      "name" => @name,
      "num_nodes" => @num_nodes,
      "start_time" => Base64.encode64(@start_time._dump),
      "end_time" => Base64.encode64(@end_time._dump),
      "instance_type" => @instance_type,
      "total_time" => total_time(),
      "cost" => cost()
    }
  end

  def self.from_hash(data)
    name = data["name"]
    num_nodes = Integer(data["num_nodes"])
    start_time = Time._load(Base64.decode64(data["start_time"])) 
    end_time = Time._load(Base64.decode64(data["end_time"]))
    instance_type = data["instance_type"]
    return NeptuneJobData.new(name, num_nodes, start_time, end_time,
      instance_type)
  end
end
