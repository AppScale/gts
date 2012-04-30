#!/usr/bin/ruby -w


# Imports for general Neptune stuff
$:.unshift File.join(File.dirname(__FILE__), "lib")
require "neptune_job_data"
require 'helperfunctions'


# Imports for each of the supported Neptune job types
$:.unshift File.join(File.dirname(__FILE__), "lib", "job_types")
require 'all_job_types'


# Imports for pluggable datastore support
$:.unshift File.join(File.dirname(__FILE__), "lib", "datastores")
require 'datastore_factory'


# Imports for pluggable task queue support
$:.unshift File.join(File.dirname(__FILE__), "lib", "task_queues")
require 'queue_factory'


# Imports for pluggable task engine support
$:.unshift File.join(File.dirname(__FILE__), "lib", "task_engines")
require 'engine_factory'


=begin
things to fix

fix @nodes from AC

move VM reuse (and per-hour killing of VMs) into this file

periodically dump and revive info to-from ZK

remove all dead code from AppController/helperfunctions

remove all dead code from Neptune/helperfunctions

make the AppController start this daemon via god

make terminate.rb kill this daemon
=end


class NeptuneManager

  
  # The port that the NeptuneManager runs on, by default.
  SERVER_PORT = 17445


  # The string that should be returned to the caller if they call a publicly
  # exposed SOAP method but provide an incorrect secret.
  BAD_SECRET_MSG = "false: bad secret"


  ALLOWED_STORAGE_TYPES = ["appdb", "s3"]


  NO_INPUT_NEEDED = ["ssa", "taskq"]


  NO_NODES_NEEDED = ["acl", "babel", "compile", "input", "output"]


  JOB_IN_PROGRESS = "job is in progress"


  BAD_TYPE_MSG = "bad type of job asked for"


  MISSING_PARAM = "Error: a required parameter was missing"


  STARTED_SUCCESSFULLY = "OK"


  NOT_QUITE_AN_HOUR = 3300


  INFINITY = 1.0 / 0


  URL_REGEX = /http:\/\/.*/

  
  # The shared secret that is used to authenticate remote callers.
  attr_accessor :secret


  # An Array of Hashes, where each Hash contains information about a 
  # virtual machine that the NeptuneManager has launched to run Neptune
  # jobs.
  attr_accessor :nodes


  # A Hash that contains profiling information about each job run via
  # Neptune, which will hopefully be used one day to optimize where we
  # place jobs.
  attr_accessor :jobs


  # An Array that contains the credentials for each pull queue that
  # Babel tasks can be stored in.
  attr_accessor :queues_to_read

  
  def initialize()
    @secret = HelperFunctions.get_secret()
    @nodes = []
    @jobs = {}
    @queues_to_read = []
  end


  def self.log(msg)
    Kernel.puts(msg)
    STDOUT.flush()
  end


  def start_job(jobs, secret)
    if jobs.class == Hash
      jobs = [jobs]
    end

    Thread.new {
      can_run_at_once = true
      jobs.each { |job_data|
        if !job_data['@type'] == "babel"
          self.log("job data #{job_data.inspect} is not a babel job - " +
            " not running in parallel")
          can_run_at_once = false
          break
        end
      }

      if can_run_at_once
          self.log("running jobs with optimized path")
          # TODO(cgb): be a bit more intelligent about batch_info
          # e.g., it's global_nodes should be the max of all in jobs
          batch_info = jobs[0]
          touch_lock_file(batch_info)

          nodes_to_use = acquire_nodes(batch_info)

          self.log("nodes to use are [#{nodes_to_use.join(', ')}]")
          start_job(nodes_to_use, batch_info)

          start_time = Time.now()
          master_node = nodes_to_use.first 
          run_job_on_master(master_node, nodes_to_use, jobs)
          end_time = Time.now()

          stop_job(nodes_to_use, job_data)

          release_nodes(nodes_to_use, batch_info)
          add_timing_info(batch_info, nodes_to_use, start_time, end_time)

          cleanup_code(batch_info['@code'])
      else
        self.log("running jobs with non-optimized path")
        jobs.each_with_index { |job_data, i|
            self.log("on job data number #{i}")
            #message = validate_environment(job_data, secret)
            #return message if message != "no error"

            touch_lock_file(job_data)
            self.log("got run request - #{job_data.inspect}")

            #prejob_status = can_run_job(job_data)
            #self.log("Pre-job status for job_data [#{job_data}] is " +
            #  "[#{prejob_status}]")
            #if prejob_status != :ok
            #  return prejob_status
            #end

            nodes_to_use = acquire_nodes(job_data)

            self.log("nodes to use are [#{nodes_to_use.join(', ')}]")
            start_job(nodes_to_use, job_data)

            start_time = Time.now()
            master_node = nodes_to_use.first 
            run_job_on_master(master_node, nodes_to_use, job_data)
            end_time = Time.now()

            stop_job(nodes_to_use, job_data)

            release_nodes(nodes_to_use, job_data)
            add_timing_info(job_data, nodes_to_use, start_time, end_time)

            cleanup_code(job_data['@code'])
        }
      end
    }

    return "job is now running"
  end


  def is_job_running(job_data, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    return lock_file_exists?(job_data)
  end


  def put_input(job_data, secret)
    message = validate_environment(job_data, secret)
    return message unless message == "no error"

    self.log("requesting input")

    type = job_data["@type"]

    ["type", "storage", "local", "remote"].each { |item|
      if job_data["@#{item}"].nil?
        return "error: #{item} not specified"
      end
    }

    input_location = job_data["@remote"]

    local_fs_location = File.expand_path(job_data["@local"])

    loop {
      self.log("waiting for file #{local_fs_location} to exist")
      break if File.exists?(local_fs_location)
      sleep(1)
    }

    msg = "storing local file #{local_fs_location} with size " + 
      "#{File.size(local_fs_location)}, storing to #{input_location}"

    self.log(msg)

    datastore = DatastoreFactory.get_datastore(job_data['@storage'], job_data)
    ret_val = datastore.write_remote_file_from_local_file(input_location, local_fs_location)

    # also, if we're running on hbase or hypertable, put a copy of the data
    # into HDFS for later processing via mapreduce

    table = @creds["table"]

    if ["hbase", "hypertable"].include?(table)
      unless my_node.is_db_master?
        db_master = get_db_master
        ip = db_master.private_ip
        ssh_key = db_master.ssh_key
        HelperFunctions.scp_file(local_fs_location, local_fs_location, ip, ssh_key)
      end

      cmd = "#{HADOOP} fs -put #{local_fs_location} #{input_location}"
      self.log("putting input in hadoop with command [#{cmd}]")
      run_on_db_master(cmd)
    end

    return ret_val
  end


  def does_file_exist(file, job_data, secret)
    datastore = DatastoreFactory.get_datastore(job_data['@storage'], job_data)
    return datastore.does_file_exist?(file)
  end


  def get_output(job_data, secret)
    message = validate_environment(job_data, secret)
    return message unless message == "no error"

    self.log("requesting output")

    type = job_data["@type"]

    output_location = job_data["@output"]
    if output_location.nil?
      return "error: output not specified"
    else
      datastore = DatastoreFactory.get_datastore(job_data['@storage'], job_data)
      if datastore.does_file_exist?(output_location)
        # TODO: maybe write to file or have
        # special flag for this?
        return datastore.get_output_and_return_contents(output_location)
      else
        return "error: output does not exist"
      end
    end
  end


  def get_acl(job_data, secret)
    message = validate_environment(job_data, secret)
    return message unless message == "no error"

    self.log("requesting acl")

    type = job_data["@type"]

    output_location = job_data["@output"]
    if output_location.nil?
      return "error: output not specified"
    else
      datastore = DatastoreFactory.get_datastore(job_data['@storage'], job_data)
      if datastore.does_file_exist?(output_location)
        return datastore.get_acl(output_location)
      else
        return "error: output does not exist"
      end
    end
  end


  def set_acl(job_data, secret)
    message = validate_environment(job_data, secret)
    return message unless message == "no error"

    self.log("setting acl")

    type = job_data["@type"]

    new_acl = job_data["@acl"]

    if new_acl != "public" and new_acl != "private"
      return "error: new acl is neither public nor private"
    end

    output_location = job_data["@output"]
    if output_location.nil?
      return "error: output not specified"
    else
      datastore = DatastoreFactory.get_datastore(job_data['@storage'], job_data)
      if datastore.does_file_exist?(output_location)
        return datastore.set_acl(output_location, new_acl)
      else
        return "error: output does not exist"
      end
    end
  end


  def compile_code(job_data, secret)
    message = validate_environment(job_data, secret)
    return message unless message == "no error"

    self.log("compiling code")

    main_file = job_data["@main"]
    input_loc = job_data["@code"]
    target = job_data["@target"]

    compiled_dir = "/tmp/compiled-#{HelperFunctions.get_random_alphanumeric}"

    Thread.new {
      makefile = input_loc + "/Makefile"
      makefile2 = input_loc + "/makefile"
      if !(File.exists?(makefile) or File.exists?(makefile2))
        HelperFunctions.generate_makefile(main_file, input_loc)
      end

      compile_cmd = "cd #{input_loc}; make #{target} 2>compile_err 1>compile_out"

      self.log("compiling code by running [#{compile_cmd}]")

      result = `#{compile_cmd}`
      HelperFunctions.shell("cp -r #{input_loc} #{compiled_dir}")

    }

    return compiled_dir  
  end


  def can_run_job(job_data)
    # no input / output for appscale jobs
    return :ok if job_data["@type"] == "appscale"

    storage = job_data["@storage"]

    if !ALLOWED_STORAGE_TYPES.include?(storage)
      return "error: bad storage type - supported types are #{ALLOWED_STORAGE_TYPES.join(', ')}"
    end

    datastore = DatastoreFactory.get_datastore(storage, job_data)

    input_location = job_data["@input"]
    if input_location and !NO_INPUT_NEEDED.include?(job_data['@type'])
      input_exists = datastore.does_file_exist?(input_location)
      self.log("input specified - did #{input_location} exist? #{input_exists}")
      unless input_exists
        return "error: input specified but did not exist"
      end
    else
      self.log("input not specified - moving on")
    end

    output_location = job_data["@output"]
    output_exists = datastore.does_file_exist?(output_location)
    self.log("output specified - did #{output_location} exist? #{output_exists}")
    if output_exists
      return "error: output already exists"
    end

    self.log("job type is [#{job_data["@type"]}]")

    if NO_NODES_NEEDED.include?(job_data["@type"])
      return :ok
    else
      unless job_data["@nodes_to_use"]
        return "error: failed to specify nodes_to_use, a required parameter"
      end
    end

    if !(is_cloud? or is_hybrid_cloud?)
      self.log("not in cloud")
      # make sure we have enough open nodes
      # a bit race-y, see the TODO on set for more info

      # In non-hybrid clouds, if the user specifies that they want to run over
      # multiple clouds, then either all clouds must be using remote resources
      # (e.g., only URLs are specified), or the first cloud has an integer value
      # (which we interpret as our cloud) and the others are remote clouds
      if job_data["@nodes_to_use"].class == Array
        hash_job_data = Hash[*job_data["@nodes_to_use"]]
        hash_job_data.each { |cloud, nodes_needed|
          if nodes_needed =~ URL_REGEX
            self.log("Saw URL [#{nodes_needed}] for cloud [#{cloud}] - " +
              "moving on to next cloud")
            next
          end

          if cloud == "cloud1" and nodes_needed.class == Fixnum
            self.log("Saw [#{nodes_needed}] nodes needed for cloud " +
              "[#{cloud}] - moving on to next cloud")
            next
          end

          self.log("Saw cloud [#{cloud}] and nodes needed " + 
            "[#{nodes_needed}], which was not acceptable in non-hybrid " + 
            "cloud deployments")

          return "error: cannot specify hybrid deployment in non-hybrid cloud runs"
        }

        if hash_job_data["cloud1"].class == Fixnum
          num_of_vms_needed = Integer(hash_job_data["cloud1"])
        else
          return :ok
        end
      elsif job_data["@nodes_to_use"].class == Fixnum
        num_of_vms_needed = Integer(job_data["@nodes_to_use"])
      else
        return "error: nodes_to_use specified was not an Array or Fixnum" +
          " but was a #{job_data['@nodes_to_use'].class}"
      end

      nodes_to_use = []
        @nodes.each { |node|
          if node.is_open?
            nodes_to_use << node
            break if nodes_to_use.length == num_of_vms_needed
          end
        } 

      if nodes_to_use.length < num_of_vms_needed   
        return "error: not enough free nodes (requested = #{num_of_vms_needed}, available = #{nodes_to_use.length})"
      end
    end

    return :ok
  end


  def start_job(nodes, job_data)
    self.log("job - start")

    # if all the resources are remotely owned, we can't add roles to
    # them, so don't
    if nodes.empty?
      self.log("no nodes to add roles to, returning...")
      return
    end

    master_role, slave_role = get_node_roles(job_data)

    other_nodes = nodes - [nodes.first]
    add_roles_and_wait(other_nodes, slave_role)
    if !other_nodes.nil? and !other_nodes.empty? # TODO: prettify me
    other_nodes.each { |node|
      node.add_roles(slave_role)
    }
    end

    master_node = nodes.first
    master_node_ip = master_node.private_ip

    master_acc = AppControllerClient.new(master_node_ip, HelperFunctions.get_secret)
    master_acc.add_role(master_role)

    # finally, update our local copy of what the master is doing
    master_node.add_roles(master_role)
  end


  def get_node_roles(job_data)
    self.log("getting node roles")
    job_type = job_data["@type"]

    if job_type == "appscale"
      component_to_add = job_data["@add_component"]
      master_role = component_to_add
      slave_roles = component_to_add
    elsif job_type == "mapreduce"
      master_role = "db_slave:mapreduce_master"
      slave_roles = "db_slave:mapreduce_slave"
    else
      master_role = "#{job_type}_master"
      slave_roles = "#{job_type}_slave"
    end

    self.log("master role is [#{master_role}], slave roles are " +
      "[#{slave_roles}]")
    return master_role, slave_roles
  end


  def run_job_on_master(master_node, nodes_to_use, job_data)
    self.log("run job on master")
    converted_nodes = Djinn.convert_location_class_to_array(nodes_to_use)

    # in cases where only remote resources are used, we don't acquire a master
    # node. therefore, let this node be the master node for this job
    if master_node.nil?
      self.log("No master node found - using my node as the master node")
      master_node = my_node
    end

    master_node_ip = master_node.private_ip
    master_acc = AppControllerClient.new(master_node_ip, HelperFunctions.get_secret)

    result = master_acc.run_neptune_job(converted_nodes, job_data)
    self.log("run job result was #{result}")

    loop {
      shadow = get_shadow
      lock_file = get_lock_file_path(job_data)
      command = "ls #{lock_file}; echo $?"
      self.log("shadow's ssh key is #{shadow.ssh_key}")
      job_is_running = `ssh -i #{shadow.ssh_key} -o StrictHostkeyChecking=no root@#{shadow.private_ip} '#{command}'`
      self.log("is job running? [#{job_is_running}]")
      if job_is_running.length > 1
        return_val = job_is_running[-2].chr
        self.log("return val for file #{lock_file} is #{return_val}")
        break if return_val != "0"
      end
      sleep(30)
    }
  end


  def stop_job(nodes, job_data)
    self.log("job - stop")

    # if all the resources are remotely owned, we can't add roles to
    # them, so don't
    if nodes.empty?
      self.log("no nodes to add roles to, returning...")
      return
    end

    master_role, slave_role = get_node_roles(job_data)

    master_node = nodes.first
    master_node_ip = master_node.private_ip
    master_node.remove_roles(master_role)

    master_acc = AppControllerClient.new(master_node_ip, HelperFunctions.get_secret)
    master_acc.remove_role(master_role)

    other_nodes = nodes - [nodes.first]
    remove_roles(other_nodes, slave_role)
    if !other_nodes.nil? and !other_nodes.empty? # TODO: prettify me
      other_nodes.each { |node|
        node.remove_roles(slave_role)
      }
    end
  end


  def validate_environment(job_data, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    #return JOB_IN_PROGRESS if lock_file_exists?(job_data)
    return BAD_TYPE_MSG unless NEPTUNE_JOBS.include?(job_data["@type"])

    if job_data["@type"] == "mapreduce"
      return BAD_TABLE_MSG unless DBS_W_HADOOP.include?(@creds["table"])
    end

    return "no error"
  end


  def lock_file_exists?(job_data)
    return File.exists?(get_lock_file_path(job_data))
  end


  def touch_lock_file(job_data)
    job_data["@job_id"] = rand(1000000)
    touch_lock_file = "touch #{get_lock_file_path(job_data)}"
    HelperFunctions.shell(touch_lock_file)
  end


  def remove_lock_file(job_data)
    shadow = get_shadow
    shadow_ip = shadow.private_ip
    shadow_key = shadow.ssh_key
    done_running = "rm #{get_lock_file_path(job_data)}"

    HelperFunctions.run_remote_command(shadow_ip, done_running, shadow_key, NO_OUTPUT)
  end 


  def get_lock_file_path(job_data)
    "/tmp/#{job_data['@type']}-#{job_data['@job_id']}-started"
  end


  def spawn_nodes_for_neptune?(job_data)
    self.log("neptune_info = #{job_data}")
    return !job_data["@nodes_to_use"].nil?
  end


  def acquire_nodes(job_data)
    # for jobs where no nodes need to be acquired (e.g., concurrent but not
    # distributed programs), run them on the shadow node
    if NO_NODES_NEEDED.include?(job_data["@type"])
      self.log("No nodes needed for job type [#{job_data['@type']}]," +
        " not acquiring nodes")
      return [my_node]
    end

    self.log("acquiring nodes")

    #num_of_vms_needed = optimal_nodes_hill_climbing(job_data, "performance")
    nodes_needed = optimal_nodes(job_data)

    self.log("acquiring nodes for hybrid cloud neptune job")

    if nodes_needed.class == Array
      nodes_needed = Hash[*nodes_needed]
      self.log("request received to spawn hybrid nodes: #{nodes_needed.inspect}")
    elsif nodes_needed.class == Fixnum
      nodes_needed = {"cloud1" => nodes_needed}
    else
      self.log("nodes_needed was not the right class - should have been Array or Fixnum but was #{nodes_needed.class}")
      # TODO: find a way to reject the job here
    end

    nodes_to_use = []

    nodes_needed.each { |cloud, nodes_to_acquire|
      # nodes_to_acquire can either be an integer or a URL
      # if it's an integer, spawn up that many nodes
      # if it's a URL, it refers to a remote cloud resource we don't control
      # (e.g., Google App Engine), so skip it

      # in non-hybrid cloud runs, cloud1 will be the only cloud that specifies
      # an integer value
      if nodes_to_acquire =~ URL_REGEX
        self.log("nodes to acquire for #{cloud} was a URL " + 
          "[#{nodes_to_acquire}], so not spawning nodes")
        next
      end

      self.log("acquiring #{nodes_to_acquire} nodes for #{cloud}")
      nodes_for_cloud = find_open_nodes(cloud, nodes_to_acquire, job_data)
      nodes_to_use = [nodes_to_use + nodes_for_cloud].flatten
      # TODO: should check for failures acquiring nodes
    }

    return nodes_to_use
  end


  def find_open_nodes(cloud, nodes_needed, job_data)
    # TODO: assigning nodes -> nodes_to_use should be atomic?
    # or should going through this list be atomic?

    cloud_num = cloud.scan(/cloud(.*)/).flatten.to_s

    nodes_to_use = []
    @nodes.each { |node|
      break if nodes_to_use.length == nodes_needed
      if node.is_open? and node.cloud == cloud
        nodes_to_use << node
      end
    }

    @neptune_nodes = nodes_to_use

    nodes_available = nodes_to_use.length
    new_nodes_needed = nodes_needed - nodes_available
    self.log("need #{nodes_needed} total, currently have #{nodes_available} to spare")

    if is_cloud?
      if new_nodes_needed > 0
        self.log("spawning up #{new_nodes_needed} for neptune job in cloud 1")
        acquire_nodes_for_cloud(cloud_num, new_nodes_needed, job_data)
      end
    else
      if new_nodes_needed > 0
        self.log("non-cloud deployment and the neptune user has asked for too many nodes")
        # TODO: find a way to reject the job here
      end
    end

    nodes_to_use = []
    @neptune_nodes.each { |node|
      break if nodes_to_use.length == nodes_needed
      if node.is_open? and node.cloud == cloud
        self.log("will use node [#{node}] for computation")
        nodes_to_use << node
      end
    }

    return nodes_to_use
  end


  def acquire_nodes_for_cloud(cloud_num, new_vms_needed, job_data)
    return if new_vms_needed < 1
    self.log("spawning up #{new_vms_needed} vms")

    job = "open" # *_helper will add the right role later
    machine = @creds["machine"]
    ENV['EC2_URL'] = @creds["ec2_url"]
    instance_type = job_data['@instance_type'] or @creds["instance_type"]
    keyname = @creds["keyname"]
    infrastructure = @creds["infrastructure"]
    group = @creds["group"]

    HelperFunctions.set_creds_in_env(@creds, cloud_num)
    new_node_info = HelperFunctions.spawn_vms(new_vms_needed, job, machine,
      instance_type, keyname, infrastructure, "cloud#{cloud_num}", group)
    add_nodes(new_node_info)
   
    self.log("got all the vms i needed!")
  end

  def add_nodes(node_info)
    keyname = @creds['keyname']
    new_nodes = Djinn.convert_location_array_to_class(node_info, keyname)

    node_start_time = Time.now
    node_end_time = Time.now + NOT_QUITE_AN_HOUR

    new_nodes.each { |node|
      node.set_time_info(node_start_time, node_end_time)
    }

    @nodes.concat(new_nodes)
    @neptune_nodes.concat(new_nodes)
    initialize_nodes_in_parallel(new_nodes)
  end


  def release_nodes(nodes_to_use, job_data)
    if is_hybrid_cloud?
      abort("hybrid cloud mode is definitely not supported")
    elsif is_cloud?
      nodes_to_use.each { |node|
        node.set_roles("open")
      }

      # don't worry about terminating the vms - the appcontroller
      # will take care of this in its heartbeat loop
    else
      return
    end
  end


  def get_job_name(job_data)
    job_name = job_data["@type"]

    ["@code", "@main", "@map", "@reduce", "@simulations", "@add_component"].each { |item|
      if job_data[item]
        job_name += " - " + "#{job_data[item]}"
      end
    }

    return job_name
  end


  def add_roles_and_wait(nodes, roles)
    return if nodes.nil?

    nodes.each { |node|
      node.add_roles(roles)
      acc = AppControllerClient.new(node.private_ip, HelperFunctions.get_secret)
      acc.add_role(roles)
      acc.wait_for_node_to_be(roles)
      self.log("[just added] node at #{node.private_ip} is now #{node.jobs.join(', ')}")
    }
  end


  def remove_roles(nodes, roles)
    return if nodes.nil?

    nodes.each { |node|
      node.remove_roles(roles)
      acc = AppControllerClient.new(node.private_ip, HelperFunctions.get_secret)
      acc.remove_role(roles)
      self.log("[just removed] node at #{node.private_ip} is now #{node.jobs.join(', ')}")
    }
  end


  def copyFromShadow(location_on_shadow)
    shadow = get_shadow
    shadow_ip = shadow.private_ip
    shadow_key = shadow.ssh_key

    copy_from_shadow = "scp -r -i #{my_node.ssh_key} #{location_on_shadow} root@#{my_node.public_ip}:#{location_on_shadow}"
    HelperFunctions.run_remote_command(shadow_ip, copy_from_shadow, shadow_key, NO_OUTPUT)
  end


  def optimal_nodes(job_data)
    return job_data["@nodes_to_use"]
  end


=begin
  Hill Climbing Algorithm
    # find minimum execution time t1
    # find neighbors t0 and t2

    # if t0 is too low set it to t1
    # if t2 is too high set it to t1

    # if no data for either, choose t2
    # if no data for t0, choose t0
    # if data for both, choose t1
=end
  def optimal_nodes_hill_climbing(job_data, thing_to_optimize)
    job_name = get_job_name(job_data)

    if thing_to_optimize != "cost" and thing_to_optimize != "performance"
      abort("bad thing to optimize - can be cost or performance but was #{thing_to_optimize}")
    end

    current_data = @jobs[job_name]
    if current_data.nil? or current_data.empty?
      self.log("neptune - no job data yet for [#{job_name}]")
      return job_data["@nodes_to_use"]
    end

    self.log("found job data for [#{job_name}]")

    min_val = INFINITY
    optimal_job = nil
    current_data.each { |job|
      self.log("current job data is [#{job}]")

      if thing_to_optimize == "performance"
        my_val = job.total_time
      elsif thing_to_optimize == "cost"
        my_val = job.cost
      else
        abort("bad thing to optimize again")
      end

      if my_val < min_val
        self.log("found a new minimum - [#{job}]")
        optimal_job = job
      end
    }

    self.log("minimum is - [#{optimal_job}]")

    search_space = job_data["@can_run_on"]
    t1 = optimal_job.num_nodes

    self.log("optimal right now is t1 = #{t1}")
    t0, t2 = find_neighbors(t1, search_space)
    self.log("t1's neighbors are #{t0} and t2 = #{t2}")

    d0 = get_job_data(job_name, t0)
    d2 = get_job_data(job_name, t2)

    return t2 if d0.nil? and d2.nil?
    return t0 if d0.nil?
    return t1
  end


  def find_neighbors(val, search_space)
    abort("no empty arrays") if search_space.nil? or search_space.empty?

    left, right = nil, nil
    length = search_space.length
    search_space.each_with_index { |item, index|
      # set left
      if index <= 0
        left = val
      else
        left = search_space[index-1]
      end

      # set right
      if index < length - 1
        right = search_space[index+1]
      else
        right = val
      end

      break if item == val
    }

    return left, right
  end


  def get_job_data(job_name, time)
    relevant_jobs = @jobs[job_name]
    relevant_jobs.each { |job|
      return job if job.total_time == time
    }

    return nil
  end


  def write_job_output(job_data, output_location)
    neptune_write_job_output_handler(job_data, output_location, is_file=true)
  end


  def write_job_output_str(job_data, string)
    neptune_write_job_output_handler(job_data, string, is_file=false)
  end


  def write_job_output_handler(job_data, output, is_file)
    db_location = job_data["@output"]
    job_type = job_data["@type"]
    self.log("[#{job_type}] job done - writing output to #{db_location}")

    datastore = DatastoreFactory.get_datastore(job_data['@storage'], job_data)
    if is_file
      datastore.write_remote_file_from_local_file(db_location, output)
    else
      datastore.write_remote_file_from_string(db_location, output)
    end
  end


  def get_seed_vals(num_vals)
    random_numbers = []
    num_vals.times {
      loop {
        possible_rand = rand(10000)
        unless random_numbers.include?(possible_rand)
          random_numbers << possible_rand
          break
        end
      }
    }

    return random_numbers
  end


  def uncompress_file(tar)
    unless File.exists?(tar)
      abort("The file #{tar} didn't exist, so we couldn't uncompress it.")
    end

    if tar.scan(/.tar.gz\Z/)
      dir = File.dirname(tar)
      HelperFunctions.shell("cd #{dir}; tar zxvf #{tar}")
      return
    end

    # TODO: add other extension types: zip, bzip2, tar, gz
    #ext = File.extname(tar)
    #
    #case ext
    #when "."
    #end
  end


  # Verifies that the given job_data has all of the parameters specified
  # by required_params.
  def has_all_required_params?(job_data, required_params)
    required_params.each { |param|
      if job_data[param].nil?
        return false
      end
    }

    return true
  end


  def add_timing_info(job_data, nodes_to_use, start_time, end_time)
    name = get_job_name(job_data)
    num_nodes = nodes_to_use.length
    this_job = NeptuneJobData.new(name, num_nodes, start_time, end_time)
    if @jobs[name].nil?
      @jobs[name] = [this_job]
    else
      @jobs[name] << this_job
    end
  end


  def cleanup_code(code)
    if code.nil?
      self.log("no code to remove")
    else
      dirs = code.split(/\//)
      code_dir = dirs[0, dirs.length-1].join("/")

      if code_dir == "/tmp"
        self.log("can't remove code located at #{code_dir}")
      else
        self.log("code is located at #{code_dir}")
        HelperFunctions.shell("rm -rf #{code_dir}")
      end
    end
  end


  def self.neptune_parse_creds(storage, job_data)
    creds = {}

    if storage == "s3"
      ['EC2_ACCESS_KEY', 'EC2_SECRET_KEY', 'S3_URL'].each { |item|
        creds[item] = job_data["@#{item}"]
      }
    end

    return creds
  end


end
