#!/usr/bin/ruby -w

$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'fileutils'
require 'monitor'

SUCCESS = 0
FAILURE = -1

EPHEMERAL = true
NOT_EPHEMERAL = false

ROOT_APP_PATH = "/apps"

class ZKInterface
  public

  def self.init(my_node, all_nodes)
    require 'rubygems'
    require 'zookeeper'

    unless defined?(@@lock)
      @@lock = Monitor.new
    end

    zk_location = self.get_zk_location(my_node, all_nodes)

    @@lock.synchronize {
      @@zk = Zookeeper.new(zk_location)
    }
  end

  def self.add_app_entry(appname, ip, location)
    appname_path = ROOT_APP_PATH + "/#{appname}"
    full_path = appname_path + "/#{ip}"

    # can't just create path in ZK
    # need to do create the nodes at each level

    self.set(ROOT_APP_PATH, "nothing special here", NOT_EPHEMERAL)
    self.set(appname_path, "nothing special here", NOT_EPHEMERAL)
    self.set(full_path, location, EPHEMERAL)
  end

  def self.remove_app_entry(appname)
    appname_path = ROOT_APP_PATH + "/#{appname}"
    self.delete(appname_path)
  end

  def self.get_app_hosters(appname)
    appname_path = ROOT_APP_PATH + "/#{appname}"
    app_hosters = self.get_children(appname_path)
    #converted = app_hosters
    converted = []
    app_hosters.each { |serialized|
      converted << DjinnJobData.deserialize(serialized)
    }
    return converted
  end

  private

  def self.get(key)
    Djinn.log_debug("[ZK] trying to get #{key}")
    info = @@zk.get(:path => key)
    if info[:rc] == 0
      return info[:data]
    else
      return FAILURE
    end
  end

  def self.get_children(key)
    Djinn.log_debug("[ZK] trying to get children of #{key}")
    children = @@zk.get_children(:path => key)[:children]
    if children.nil?
      return []
    else
      return children
    end
  end

  def self.set(key, val, ephemeral)
    Djinn.log_debug("[ZK] trying to set #{key} to #{val} with ephemeral = #{ephemeral}")
    info = @@zk.create(:path => key, :ephemeral => ephemeral, :data => val)
    if info[:rc] == 0
      return SUCCESS
    else
      return FAILURE
    end
  end

  def self.delete(key)
    Djinn.log_debug("[ZK] trying to delete #{key}")

    child_info = @@zk.get_children(:path => key)
    unless child_info[:stat].numChildren.zero?
      child_info[:children].each { |child|
        fullkey = key + "/" + child
        self.delete(fullkey)
      }
    end

    info = @@zk.delete(:path => key)
    if info[:rc] == 0
      return SUCCESS
    else
      return FAILURE
    end
  end

  def self.get_zk_location(my_node, all_nodes)
    if my_node.is_zookeeper?
      return my_node.private_ip + ":2181"
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

    return zk_node.public_ip + ":2181"
  end
end

