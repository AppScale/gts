#!/usr/bin/ruby
# Programmer: Chris Bunch


require 'net/http'


require 'rubygems'
require 'httparty'


$:.unshift File.join(File.dirname(__FILE__), "..", "..")
require 'neptune_manager'

RETRY_TIME = 5  # seconds


public 

def neptune_cicero_run_job(nodes, jobs, secret)
  if !valid_secret?(secret)
    return BAD_SECRET_MSG
  end

  if nodes.class != Array
    return "nodes must be an Array"
  end

  job_data = jobs[0]
  if job_data.class != Hash
    return "job_data must be a Hash"
  end

  Djinn.log_debug("cicero - run")

  Thread.new {
    run_via_cicero(nodes, job_data, secret)
  }

  return "OK"
end

private

# Runs a Cicero job on the given nodes or via a remote cloud, indicated within
# job_data.
def run_via_cicero(nodes, job_data, secret)
  Djinn.log_debug("job data is #{job_data.inspect}")

  resource_info = parse_resource_info(job_data)

  keyname = @creds['keyname']
  nodes = Djinn.convert_location_array_to_class(nodes, keyname)

  app_name = job_data["@app_name"]
  urls = start_appengine_on_all_nodes(resource_info, nodes, app_name)

  num_tasks_total = job_data["@tasks"]
  tasks_for_each_cloud = get_execution_plan(nodes, resource_info, num_tasks_total)

  function_name = job_data["@function"]
  inputs = get_inputs_from_job_data(job_data)

  start_time = Time.now
  threads_per_cloud = []
  urls.each { |cloud, urls|
    threads_per_cloud << Thread.new {
      num_tasks = tasks_for_each_cloud[cloud]
      num_urls = urls.length
      threads_per_url = []
      num_urls.times { |i|
        threads_per_url << Thread.new {
          # TODO - consider cases where this doesn't divide evenly
          host = urls[i]
          num_tasks_for_this_url = num_tasks / num_urls
          task_ids = []
          num_tasks_for_this_url.times { |j|
            output = job_data["@output"] + String(j)
            #self.execute_task(host, function_name, inputs, output) #Python
            task_ids << self.execute_task(host, function_name, inputs, output) #Java
            task_number = j + 1
            percent_done = task_number / Float(num_tasks_for_this_url) * 100
            Djinn.log_debug("done putting #{task_number}/" +
              "#{num_tasks_for_this_url} tasks (#{percent_done} percent)")
          }

          num_tasks_for_this_url.times { |j|
            # TODO - the task id shouldn't be the output - refactor later
            #task_id = job_data["@output"] + String(j) #Python
            task_id = task_ids[j] #Java
            self.wait_for_task_to_complete(host, task_id)
            task_number = j + 1
            percent_done = task_number / Float(num_tasks_for_this_url) * 100
            Djinn.log_debug("done with #{task_number}" +
              "/#{num_tasks_for_this_url} tasks (#{percent_done} percent)")
          }
        }
      }
      threads_per_url.each { |t| t.join }
    }
  }
  threads_per_cloud.each { |t| t.join }
  end_time = Time.now
  total_time = end_time - start_time
  Djinn.log_debug("TIMING: total execution time is #{total_time} seconds")

  stop_appengine_on_all_nodes(resource_info, nodes, app_name)
  remove_lock_file(job_data)
end

# Grabs the @nodes_to_use parameter from the given job data and returns a
# hash only containing info about the resources found in each cloud. These
# resources are either an integer (describing the number of virtual machines
# to use) or a URL (describing an opaque resource that conforms to the
# TaskQ API).
def parse_resource_info(job_data)
  nodes_to_use = job_data["@nodes_to_use"]
  if nodes_to_use.class == Integer  # only use nodes in the current cloud
    return {"cloud1" => nodes_to_use}
  end

  return Hash[*nodes_to_use]
end

def start_appengine_on_all_nodes(resource_info, nodes, app_name)
  resource_info.each { |cloud, nodes_or_url|
    if nodes_or_url =~ URL_REGEX
      resource_info[cloud] = [nodes_or_url]
    else
      resource_info[cloud] = []
    end
  }

  if nodes.empty?
    Djinn.log_debug("All resources used are remote resource - no need to" +
      " start App Engine instances")
    return resource_info
  end

  nodes.each { |node|
    # update our local copy of what we think the nodes are doing
    appengine_role = "appengine"
    node.add_roles(appengine_role)

    # tell the node that it should be running appengine apps
    acc = AppControllerClient.new(node.public_ip, HelperFunctions.get_secret)
    acc.add_role(appengine_role)

    host = node.public_ip
    port = ""
    uac = UserAppClient.new(@userappserver_private_ip, HelperFunctions.get_secret)
    loop {
      app_data = uac.get_app_data(app_name)
      Djinn.log_debug("app data for app [#{app_name}] is [#{app_data}]")
      all_hosts = app_data.scan(/^hosts:(.*)/).flatten.to_s.split(":")
      all_ports = app_data.scan(/^ports:(.*)/).flatten.to_s.split(":")

      all_hosts.each_with_index { |this_host, index|
        if this_host == host
          port = all_ports[index].strip
          Djinn.log_debug("found a match: #{host}:#{port}")
          break
        end
      }
      break if !port.empty?

      Djinn.log_debug("still waiting for app to come online...")
      sleep(5)
    }
    uri = "http://#{host}:#{port}"
    Djinn.log_debug("adding uri [#{uri}] to cloud [#{node.cloud}]")
    resource_info[node.cloud] << uri
  }

  return resource_info
end

def stop_appengine_on_all_nodes(resource_info, nodes, app_name)
  if nodes.empty?
    Djinn.log_debug("All resources used are remote resource - no need to" +
      " stop App Engine instances")
    return
  end

  nodes.each { |node|
    # update our local copy of what we think the nodes are doing
    appengine_role = "appengine"
    node.remove_roles(appengine_role)

    # tell the node that it should no longer be running appengine apps
    acc = AppControllerClient.new(node.public_ip, HelperFunctions.get_secret)
    acc.remove_role(appengine_role)
  }

  return
end

# The user can specify an arbitrary number of inputs to be used for a
# TaskQ job. The inputs must be sequentially numbered, so search through
# all the job data starting at input1 until we fail to find a match,
# and return all inputs found.
def get_inputs_from_job_data(job_data)
  inputs = []
  input_number = 1
  loop {
    current_input = "@input#{input_number}"
    current_val = job_data[current_input]
    if current_val.nil?
      Djinn.log_debug("Didn't see [#{current_input}] - no more inputs")
      break
    end

    Djinn.log_debug("Saw [#{current_input}] -> [#{current_val}], adding" +
      " to the input list")
    inputs << current_val
    input_number += 1
  }

  Djinn.log_debug("all inputs for this job are [#{inputs.join(', ')}]")
  return inputs
end

def get_execution_plan(nodes, resource_info, num_tasks)
  # based on the resource info given, deduce where to run tasks
  # and how many should be run in each cloud

  # for now, just divide the work evenly on all the clouds the user has given us

  execution_plan = {}
  num_clouds = resource_info.length
  num_tasks_left = num_tasks

  num_tasks_per_cloud = num_tasks / num_clouds
  resource_info.each { |k, v|
    execution_plan[k] = num_tasks_per_cloud
    num_tasks_left -= num_tasks_per_cloud
  }

  if !num_tasks_left.zero?
    # TODO - the user may not have specified cloud1, so refactor later to use
    # whatever the first cloud specified was
    execution_plan["cloud1"] += num_tasks_left
  end

  Djinn.log_debug("num_tasks_per_cloud = #{execution_plan.inspect}")
  return execution_plan
end

def start_cicero_master(my_node)
  Djinn.log_debug("#{my_node.private_ip} is starting cicero master")
end

def start_cicero_slave(my_node)
  Djinn.log_debug("#{my_node.private_ip} is starting cicero slave")
end

def stop_cicero_master(my_node)
  Djinn.log_debug("#{my_node.private_ip} is stopping cicero master")
end

def stop_cicero_slave(my_node)
  Djinn.log_debug("#{my_node.private_ip} is stopping cicero slave")
end


class Djinn
  def self.execute_task(host, function_name, inputs, output)
    # do a put request on the url in question - don't forget the params!
    Djinn.log_debug("executing a task at [#{host}] with function name " +
      "#{function_name}, inputs [#{inputs.join(', ')}], and output [#{output}]")

    query_params = {:f => function_name, :num_inputs => inputs.length,
      :output => output}

    begin
      # be sure to specify :body => '', so that HTTParty fills in Content-Length
      # of zero, as required for App Engine
      response = JSONClient.put("#{host}/task", :body => '', 
        :query => query_params)
      Djinn.log_debug("PUT /task returned #{response.inspect}")
      if response["result"] == "failure"
        Djinn.log_debug("Could not enqueue task: [#{response.inspect}]" +
          ", retrying in #{RETRY_TIME} sec")
        sleep(RETRY_TIME)
        raise NoMethodError  # so that the put is retried
      end
    rescue NoMethodError  # if the host is down
      Djinn.log_debug("PUT task failed on #{host}, retrying")
      sleep(RETRY_TIME)
      retry
    end

    # right now, we have tasks store data with the output as the
    # key name, so return that so that others can read the task's info
    Djinn.log_debug("done enqueuing task for output #{output}")
    return output
    #Djinn.log_debug("done enqueuing task, got id #{response['id']}")
    #return response["id"] #response
  end

  def self.wait_for_task_to_complete(host, task_id)
    response = {}
    start_time = Time.now
    loop {
      query_params = {:id => task_id, :task_id => task_id}
      begin
        response = JSONClient.get("#{host}/task", :body => '', 
          :query => query_params)
      rescue NoMethodError  # if the host is down
        Djinn.log_debug("Host [#{host}] is down, retrying in #{RETRY_TIME} sec")
        sleep(RETRY_TIME)
        retry
      end

      state = response['state']
      #start_time = response['start_time']
      if state == "finished"
        Djinn.log_debug("Task with id [#{task_id}] has finished")
        break
      end

      #if Time.now - start_time > 60
      #  Djinn.log_debug("Task with id [#{task_id}] took too long to run - skipping it.")
      #  break
      #end

      Djinn.log_debug("Current state of job with task id [#{task_id}], " +
        "is #{state}, waiting for it to become 'finished'")
      #Djinn.log_debug("Current state of job with task id [#{task_id}], started" +
      #  " at #{start_time}, is '#{state}', waiting for it to become 'finished'")
      sleep(RETRY_TIME)
    }

    return response
  end

  def self.get_output(host, output)
    begin
      query_params = {:location => output}
      response = JSONClient.get("#{host}/data", :body => '', 
        :query => query_params)
    rescue NoMethodError  # the host is down
      Djinn.log_debug("Failed to retrieve output from #{host}, retrying")
      sleep(RETRY_TIME)
      retry
    end
  
    return response["output"]
  end
end
