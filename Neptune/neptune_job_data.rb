#!/usr/bin/ruby

require 'base64'

INSTANCE_COST = 0.40 # TODO: make this dynamic?

class NeptuneJobData
  attr_accessor :name, :num_nodes, :start_time, :end_time
  
  def initialize(name, num_nodes, start_time, end_time)
    @name = name
    @num_nodes = num_nodes
    @start_time = start_time
    @end_time = end_time
  end

  def total_time
    @end_time - @start_time
  end

  def cost
    hours_used = ((end_time - start_time) / 3600.0).ceil
    cost = @num_nodes * hours_used * INSTANCE_COST
    sprintf("$%.2f", cost)
  end

  # use two colons here since the time has one colon in it
  def to_s
    "#{@name}::#{@num_nodes}::#{Base64.encode64(@start_time._dump).chomp}::#{Base64.encode64(@end_time._dump).chomp}::#{total_time}::#{cost}"
  end
end
