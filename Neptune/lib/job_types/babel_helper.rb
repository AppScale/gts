# Programmer: Chris Bunch


# Imports for RubyGems
require 'rubygems'
require 'json'


# Imports for other AppController libraries
$:.unshift File.join(File.dirname(__FILE__), "..", "..")
require 'neptune_manager'


$:.unshift File.join(File.dirname(__FILE__), "..", "task_queues")
require 'queue_factory'


$:.unshift File.join(File.dirname(__FILE__), "..", "task_engines")
require 'engine_factory'


$:.unshift File.join(File.dirname(__FILE__), "..", "datastores")
require 'datastore_factory'
require 'datastore_s3'


# The name of the queue to use when storing or receiving tasks. Since some
# providers use it as part of a FQDN, don't put underscores or other non-FQDN
# characters in it.
TASK_QUEUE_NAME = "neptune"


# When executing over AppScale resources only, we can utilize RabbitMQ as a
# queue and use Executor, our task engine, or we can make the app into an
# App Engine app and exeucte it via the App Engine Task Queue API.
INTERNAL_ENGINES = [TaskQueueRabbitMQ::NAME, TaskEngineAppScale::NAME]


# When executing over AppScale with Amazon credentials, we can utilize 
# Amazon SQS (Simple Queue Service) as a queue and use Executor to execute
# tasks.
AMAZON_CREDENTIALS = ["@EC2_SECRET_KEY", "@EC2_ACCESS_KEY", "@S3_URL"]
AMAZON_ENGINES = [TaskQueueSQS::NAME]


# When executing over AppScale with Google credentials, we can utilize
# Google App Engine's push queues as the queue and task engine or
# Google App Engine's pull queues as the queue and Executor to execute tasks.
# Since our pull queue support is done via an App Engine app, the same
# credentials will work for pull queues as for push queues (minus @function).
GOOGLE_CREDENTIALS = ["@appid", "@appcfg_cookies", "@function"]
GOOGLE_ENGINES = [TaskEngineGoogleAppEngine::NAME, TaskQueueGoogleAppEngine::NAME]


# When executing over AppScale with Azure credentials, we can utilize
# the Windows Azure Queue Service as a queue and use Executor to execute
# tasks.
AZURE_CREDENTIALS = ["@AZURE_STORAGE_ACCOUNT_NAME", "@AZURE_STORAGE_ACCESS_KEY"]
AZURE_ENGINES = [TaskQueueAzureQueue::NAME]


# Files stored in remote datastores are referenced in a POSIX-like fashion:
# /bucket/file refers to a file stored in S3, with the named bucket and
# file.
STORAGE_PARAM_REGEX = /\A\/(.*)\/(.*)\Z/


# Constants that are used to indicate which engine runs a task.
RUN_LOCALLY = "OK: run locally"
RUN_VIA_EXECUTOR = "OK: run via Executor"
RUN_VIA_REMOTE_ENGINE = "OK: run via a remote engine"


# Constants that are used to indicate how long a babel_master node should
# sleep for if there are no tasks to schedule, and how long to sleep for
# if new babel_slaves have been spawned and need time to fetch tasks off
# of queues.
TIME_TO_WAIT_FOR_NEW_TASKS = 10
TIME_FOR_NEW_NODES_TO_GET_TASKS = 30


# The amount of time that we should hold the babel_slave role for, even if we
# receive no tasks. Dynamically adding and removing this role frees it up to
# take on other roles for fault tolerance purposes, and we keep the value 
# non-trivially high because starting and stopping RabbitMQ (which we always
# start for babel_slave since rabbitmq is one of the possible backends) can
# take a while.
# TODO(cgb): Maybe only start rabbitmq if we get an item from the queue that
# specifies it should be used?
MAX_IDLE_TIME = 300


# A mapping of Amazon EC2 instance types that maps instance types to
# the number of cores they have.
# TODO(cgb): Should we eventually include memory / disk info here?
INSTANCE_CPU_INFO = {
  # Standard instances
  "m1.small" => 1,
  "m1.medium" => 1,
  "m1.large" => 2,
  "m1.xlarge" => 4,

  # Micro instances
  "t1.micro" => 1,

  # High-Memory instances
  "m2.xlarge" => 2,
  "m2.2xlarge" => 4,
  "m2.4xlarge" => 8,

  # High-CPU instances
  "c1.medium" => 2,
  "c1.xlarge" => 8,

  # Cluster Compute instances
  "cc1.4xlarge" => 8,
  "cc1.8xlarge" => 16,

  # Cluster GPU instances
  "cg1.4xlarge" => 8
}


# This debug flag is used to keep the user's code on the local filesystem,
# which can be useful to debug why code did not run successfully.
DEBUG = true


public


# Tasks can execute over a number of different engines (a queue and an
# executor). From the credentials the user has given us (job_data), determine
# which engines can be used.
def neptune_get_supported_babel_engines(job_data, secret)
  return BAD_SECRET_MSG if !valid_secret?(secret)

  Djinn.log_debug("checking supported engines for job data #{job_data.inspect}")

  # all jobs can use the internal engines
  engines = INTERNAL_ENGINES

  # but not necessarily the others, so check them one by one
  engines << get_engines_for_creds(job_data, AMAZON_CREDENTIALS, AMAZON_ENGINES)
  engines << get_engines_for_creds(job_data, AZURE_CREDENTIALS, AZURE_ENGINES)
  engines << get_engines_for_creds(job_data, GOOGLE_CREDENTIALS, GOOGLE_ENGINES)
 
  # since we're appending arrays to arrays but want it to be a 1D array
  engines.flatten!.uniq!

  Djinn.log_debug("supported engines for job data #{job_data.inspect} are [#{engines.join(', ')}]")

  return engines
end


# Checks the credentials that the user has given us (job_data) to see if
# they match up to the credentials needed for the given engine. If so, we
# return the list of engines that can be safely added.
def get_engines_for_creds(job_data, credentials, engines_to_add)

  credentials.each { |cred|
    if !job_data.include?(cred)
      Djinn.log_debug("credentials did not have #{cred}, so not " +
        "#{engines_to_add.join(', ')}")
      return []
    end
  }

  Djinn.log_debug("adding engines #{engines_to_add.join(', ')}")
  return engines_to_add
end


# This method is the spawning service for Babel - that is, it decides where 
# tasks should be spawned. For now, we don't intelligently decide where to
# run tasks - we just run tasks where the user tells us to run them. Since
# this method is accessible via SOAP, it has a time limit on its execution,
# so as soon as we can, we spawn off a new thread to do the real work and
# return.
def neptune_babel_run_job(nodes, jobs, secret)
  return BAD_SECRET_MSG if !valid_secret?(secret)

  if jobs.class == Hash
    jobs = [jobs]
  end

  Thread.new {
    run_or_delegate_tasks(jobs)
  }

  return "OK"
end


def run_or_delegate_tasks(jobs)
  where_tasks_were_run = []

  jobs.each { |job|
    Djinn.log_debug("prejob - this job's data is #{job.inspect}")
  }

  jobs.each { |job|
    job_data = job.dup
    Djinn.log_debug("This job's data is #{job_data.inspect}")

    # Add in a metadata hash so that any method can add in profiling info,
    # with an initial piece of data - when we received the task to run.
    if !job_data['@metadata_info']
      job_data['@metadata_info'] = {}
    end

    job_data['@metadata_info']['received_task_at'] = Time.now.to_f
    job_data['@metadata_info']['queue_pop_time'] = 0.0

    if job_data['@run_local']
      Djinn.log_debug("running job with data #{job_data.inspect} locally")
      run_task(job_data)
      where_tasks_were_run << RUN_LOCALLY
      next
    end

    engine = job_data['@engine']
    if engine.include?("executor")
      run_via_executor(engine, job_data)
      where_tasks_were_run << RUN_VIA_EXECUTOR
      next
    else
      run_via_engine(engine, job_data)
      where_tasks_were_run << RUN_VIA_REMOTE_ENGINE
      next
    end
  }

  return where_tasks_were_run
end


# Tasks can be run via our task executor, which will run tasks within AppScale
# and store task data in a queue service, which may not be local to AppScale.
def run_via_executor(engine, job_data)
  Djinn.log_debug("running job with data #{job_data.inspect} via executor")
  q = QueueFactory.get_queue(engine, job_data)
  credentials = q.get_creds()
  queue_and_creds = {engine => credentials}

  # the user has to tell us the maximum number of machines that can be used
  # for babel slaves, so update that info in ZooKeeper
  ZKInterface.set_max_machines_for_babel_slaves(job_data['@global_max_nodes'])

  # since the same queue / credentials can be used repeatedly, don't keep
  # adding the same queue info over and over again
  if @queues_to_read.include?(queue_and_creds)
    Djinn.log_debug("not adding queue and creds #{queue_and_creds.inspect} " +
      "to @queues_to_read - it's already in the list")
  else
    Djinn.log_debug("adding queue and creds #{queue_and_creds.inspect} to " +
      "@queues_to_read")
    @queues_to_read << queue_and_creds
  end

  Djinn.log_debug("@queues_to_read now contains " +
    "[#{@queues_to_read.join(', ')}]")
  q.push(job_data)
end


# Tasks may also be run via remote engines - that is, they may have an internal
# queue but definitely have a remote executor that we can blindly push the task
# to and let it take care of.
def run_via_engine(engine, job_data)
  Djinn.log_debug("running job with data #{job_data.inspect} via a remote engine")

  # When pushing jobs to AppScale's push queues, we need to know where the
  # app is located (via the login node's IP address) and the UserAppServer's
  # IP address, so pass that info along.
  if engine == "appscale-push-q"
    job_data['@login_ip'] = get_login.public_ip
    job_data['@uaserver_ip'] = @userappserver_public_ip
    job_data['@secret'] = HelperFunctions.get_secret()
    Djinn.log_debug("Adding info for AppScale push queues - " +
      "job data is now #{job_data.inspect}")
  end

  e = EngineFactory.get_engine(engine, job_data)
  e.push(job_data)
end


# Tasks can be stored in multiple queues concurrently, so this method provides
# workers (babel_slaves) with the way to learn what queues are currently in use
# and the credentials needed to access them.
def get_queues_in_use(secret)
  return BAD_SECRET_MSG if !valid_secret?(secret)
  Djinn.log_debug("@queues_to_read is #{@queues_to_read.join(', ')}, class #{@queues_to_read.class}")
  return JSON.dump(@queues_to_read)
end


# The nodes that runs as a babel_master is a master in the system. It decides
# when to spawn new workers, and how many to spawn, based on the number of tasks
# waiting to be executed in all queues.
def start_babel_master()
  Djinn.log_debug("#{my_node.private_ip} is starting babel master")

  while !@kill_sig_received do
    queues = get_queues_from_shadow()
    num_of_waiting_tasks = get_length_of_all_queues(queues)
    if num_of_waiting_tasks.zero?
      Djinn.log_debug("all queues are empty - waiting for tasks to arrive")
      Kernel.sleep(TIME_TO_WAIT_FOR_NEW_TASKS)
    else
      spawn_babel_slaves(num_of_waiting_tasks)
      Djinn.log_debug("workers spawned - waiting for them to run tasks")
      Kernel.sleep(TIME_FOR_NEW_NODES_TO_GET_TASKS)
    end
  end
end


# Nodes that run as babel_slaves are workers in the system. They ask the
# master what queues tasks are stored on, and try to execute a configurable
# number of tasks at a time.
def start_babel_slave()
  Thread.new {
  Djinn.log_debug("#{my_node.private_ip} is starting babel slave")

  time_spent_idle = 0.0
  loop {
    queues = get_queues_from_shadow()
    cores_per_machine = HelperFunctions.get_num_cpus()
    tasks = get_n_items_of_work(cores_per_machine, queues)
    if tasks.length.zero?
      if time_spent_idle > MAX_IDLE_TIME
        Djinn.log_debug("Spent too much time idle - reverting to open for now")
        break
      else
        Djinn.log_debug("no tasks found, waiting for more to arrive")
        Kernel.sleep(TIME_TO_WAIT_FOR_NEW_TASKS)
        time_spent_idle += TIME_TO_WAIT_FOR_NEW_TASKS
      end
    else
      Djinn.log_debug("#{tasks.length} tasks found, executing")
      execute_multiple_tasks(tasks)
      time_spent_idle = 0.0
    end
  }

  Djinn.log_debug("Removing babel slave roles from this node")
  ZKInterface.lock_and_run {
    ZKInterface.remove_roles_from_node(["rabbitmq_slave, ""babel_slave"], 
      my_node)
    ZKInterface.add_roles_to_node(["open"], my_node)
  }
  Djinn.log_debug("Finished removing roles via ZooKeeper")
  }
end


def stop_babel_master()
  Djinn.log_debug("#{my_node.private_ip} is stopping babel master")
end


def stop_babel_slave()
  Djinn.log_debug("#{my_node.private_ip} is stopping babel slave")
end


def run_task(job_data)
  dir = Djinn.create_temp_dir()
  Djinn.copy_code_and_inputs_to_dir(job_data, dir)
  output, error = Djinn.run_code(job_data, dir)
  Djinn.write_babel_outputs(output, error, job_data)
  Djinn.cleanup(dir)
end


class Djinn
  def self.create_temp_dir()
    dir = "/tmp/babel-#{rand(10000)}/"
    FileUtils.mkdir_p(dir)
    return dir
  end


  def self.copy_code_and_inputs_to_dir(job_data, dir)
    input_storage_start_time = Time.now
    Djinn.copy_code_to_dir(job_data, dir)
    Djinn.copy_inputs_to_dir(job_data, dir)
    input_storage_end_time = Time.now
    job_data['@metadata_info']['input_storage_time'] = input_storage_end_time - input_storage_start_time
  end

  def self.copy_code_to_dir(job_data, dir)
    if !is_storage_location?(job_data['@code'])
      abort("The given code, #{job_data['@code']}, is not something we can fetch")
    end

    Djinn.log_debug("old code is #{job_data['@code']}")
    local_folder = self.copy_file_to_dir(File.dirname(job_data['@code']), dir, job_data)
    job_data['@code'] = local_folder + '/' + File.basename(job_data['@code'])

    # If the code isn't going to be executed by a different program (e.g., python)
    # then we need to make it executable
    if job_data["@executable"].nil? or job_data["@executable"].empty?
      Djinn.log_debug("making code executable")
      Djinn.log_run("chmod +x #{job_data['@code']}")
    end

    Djinn.log_debug("new code is #{job_data['@code']}")
    return job_data['@code']
  end


  def self.copy_inputs_to_dir(job_data, dir)
    return if job_data['@argv'].class != Array

    new_argv = []

    Djinn.log_debug("old argv is #{job_data['@argv'].join(' ')}")
    job_data['@argv'].each { |arg|
      if is_storage_location?(arg)
        new_argv << self.copy_file_to_dir(arg, dir, job_data)
      else
        new_argv << arg
      end
    }

    job_data['@argv'] = new_argv
    Djinn.log_debug("new argv is #{job_data['@argv'].join(' ')}")
    return
  end


  def self.copy_file_to_dir(remote, local, job_data)
    bucket, file = DatastoreS3.parse_s3_key(remote)
    remote_dir = file
    local_file = File.expand_path(local + "/" + remote_dir)
    Djinn.log_debug("downloading remote file #{remote} to local location #{local_file}")
    Djinn.log_debug("bucket is #{bucket}, file is #{file}")

    datastore = DatastoreFactory.get_datastore(job_data['@storage'], job_data)
    datastore.get_output_and_save_to_fs(remote, local)
    return local_file
  end


  def self.run_code(job_data, dir)
    filename_to_exec = job_data['@code']

    executable = job_data['@executable'] || ""
  
    # If the user specifies an argv to pass to the code to exec, be sure to
    # capture it and pass it along
    if job_data["@argv"]
      argv = job_data["@argv"].join(' ')
      # TODO(cgb): filter out colons and other things that malicious users could
      # use to hijack the system
    else
      argv = ""
    end
  
    output_file = "#{dir}/stdout-#{HelperFunctions.get_random_alphanumeric()}"
    error_file = "#{dir}/stderr-#{HelperFunctions.get_random_alphanumeric()}"
  
    # For most file types, we can use the full path when executing them. For
    # programs that run over the JVM (e.g., Java, Scala), we can't - we need 
    # to change into the directory where the file is located and exec the file 
    # from there.
    # TODO(cgb): Consider a job_data['@jvm_args'] option (with an array val)
    # that users can set to pass in arguments that we should pass to the JVM
    # we are about to run.
    if executable == "java" or executable == "scala"
      dir = File.dirname(filename_to_exec)
      file = File.basename(filename_to_exec)
      exec_command = "cd #{dir}; #{executable} #{file} #{argv} 1>#{output_file} 2>#{error_file}"
    else
      exec_command = "#{executable} #{filename_to_exec} #{argv} 1>#{output_file} 2>#{error_file}"
    end

    start_time = Time.now
    ret_val = Djinn.log_run(exec_command)
    end_time = Time.now
  
    total = end_time - start_time
    Djinn.log_debug("Babel: Done running job!")
    Djinn.log_debug("TIMING: Took #{total} seconds")

    # Save some data about the task we just ran. At a high level, there are two
    # types of information we want to save: debugging information (in case the
    # task failed and the user needs to deduce why), and profiling information
    # (so the user can see how long their code took to run).

    # Add in debugging information.
    job_data['@metadata_info']['command'] = exec_command
    job_data['@metadata_info']['return_value'] = ret_val
    job_data['@metadata_info']['cpu_info'] = HelperFunctions.shell("cat /proc/cpuinfo")
    job_data['@metadata_info']['mem_info'] = HelperFunctions.shell("cat /proc/meminfo")
    job_data['@metadata_info']['df_h'] = HelperFunctions.shell("df -h")

    # Add in profiling information, with all times converted to seconds since epoch.
    job_data['@metadata_info']['start_time'] = start_time.to_i
    job_data['@metadata_info']['end_time'] = end_time.to_i
    job_data['@metadata_info']['total_execution_time'] = total

    return output_file, error_file
  end


  # Writes the stdout and stderr that a Babel task produces to the remote
  # datastore that the user has specified to use. We also automatically collect
  # some metadata about the task, so we write that to the datastore as well.
  def self.write_babel_outputs(output, error, job_data)
    datastore = DatastoreFactory.get_datastore(job_data['@storage'], job_data)

    # Write our stdout file
    Djinn.log_debug("Saving stdout at #{output} to remote location" + 
      " #{job_data['@output']}")
    output_storage_start_time = Time.now
    datastore.write_remote_file_from_local_file(job_data['@output'], output)

    # Write our stderr file
    Djinn.log_debug("Saving stderr #{error} to remote location" +
      " #{job_data['@error']}")
    datastore.write_remote_file_from_local_file(job_data['@error'], error)
    output_storage_end_time = Time.now
    total_output_time = output_storage_end_time - output_storage_start_time
    job_data['@metadata_info']['output_storage_time'] = total_output_time

    local_input_storage_time = job_data['@metadata_info']['time_to_store_inputs']
    total_input_time = job_data['@metadata_info']['input_storage_time']
    job_data['@metadata_info']['total_storage_time'] = local_input_storage_time + 
      total_input_time + total_output_time

    end_of_task_time = Time.now.to_f
    start_of_task_time = job_data['@metadata_info']['received_task_at']
    total_task_time = end_of_task_time - start_of_task_time
    job_data['@metadata_info']['total_task_time'] = total_task_time

    # Write our metadata info, which is not a file, but a hash we will turn to
    # a string via JSON
    Djinn.log_debug("Saving metadata #{job_data['@metadata_info'].inspect} " +
      "to remote location #{job_data['@metadata']}")
    metadata_file = "/tmp/metadata-#{HelperFunctions.get_random_alphanumeric()}"
    HelperFunctions.write_file(metadata_file, 
      JSON.dump(job_data['@metadata_info']))
    datastore.write_remote_file_from_local_file(job_data['@metadata'], 
      metadata_file)
    FileUtils.rm_f(metadata_file)
  end


  def self.save_output(remote_output, local_output, job_data)
    Djinn.log_debug("Saving local output #{local_output} to remote location #{remote_output}")
    datastore = DatastoreFactory.get_datastore(job_data['@storage'], job_data)
    datastore.write_remote_file_from_local_file(remote_output, local_output)
  end


  def self.cleanup(dir)
    Djinn.log_debug("Cleaning up directory #{dir}")
    # don't clean up if we want to debug the system
    return if DEBUG
    FileUtils.rm_rf(dir)
  end
end


def is_storage_location?(file)
  return STORAGE_PARAM_REGEX.match(file)
end


def get_queues_from_shadow()
  secret = HelperFunctions.get_secret()
  acc = AppControllerClient.new(get_shadow.public_ip, secret)
  json_queue_and_cred_info = acc.get_queues_in_use()
  Djinn.log_debug("raw json received is '#{json_queue_and_cred_info}'")
  queue_and_cred_info = JSON.load(json_queue_and_cred_info)
  Djinn.log_debug("json formatted data is [#{queue_and_cred_info}]")

  queues = []
  if queue_and_cred_info.nil?
    Djinn.log_debug("queues from shadow are nil")
    return queues
  end

  queue_and_cred_info.each { |info|
    Djinn.log_debug("this queue's info is #{info.inspect}")
    engine = info.keys[0]
    credentials = info.values[0]
    Djinn.log_debug("engine is [#{engine}], credentials are [#{credentials.inspect}]")
    queues << QueueFactory.get_queue(engine, credentials)
  }

  Djinn.log_debug("queues from shadow are [#{queues.join(', ')}]")
  return queues
end


def get_length_of_all_queues(queues)
  # something to consider: do leased tasks count in the size?
  length = 0
  queues.each { |q|
    length += q.size
  }
  return length
end


def get_n_items_of_work(n, queues)
  items = []

  queues.each { |q|
    loop {
      Djinn.log_debug("popping an item of work off of queue #{q}")
      start_time = Time.now
      new_item = q.pop
      end_time = Time.now
      if new_item.nil?
        Djinn.log_debug("#{q} is empty - moving on to next queue")
        break  # the queue is empty
      end
  
      # add how long it took to grab the item from the queue to our metadata
      if !new_item["@metadata_info"]
        new_item = {}
      end
      queue_pop_time = end_time - start_time
      new_item['@metadata_info']['queue_pop_time'] = queue_pop_time

      Djinn.log_debug("adding [#{new_item}][#{new_item.class}] to items" +
        " - took #{queue_pop_time} seconds to pop it off the queue")
      items << new_item

      break if items.length >= n
    }

    break if items.length >= n
  }

  Djinn.log_debug("returning [#{items.join(', ')}] items of work")
  return items
end


# A Babel master can call this method to add more workers (Babel slaves) to the
# system as needed.
def spawn_babel_slaves(num_of_waiting_tasks)
  Djinn.log_debug("spawning workers to handle #{num_of_waiting_tasks} tasks")

  if is_cloud?
    instance_type = "m1.large"
    #instance_type = "m2.4xlarge"
    cores_per_machine = INSTANCE_CPU_INFO[instance_type]
  else
    instance_type = "m1.large"
    cores_per_machine = 2
  end
  Djinn.log_debug("Using #{cores_per_machine} cores/machine")

  # First, calculate how many machines we would need to run all the tasks
  # as fast as possible, by running one task per core.
  optimal_num_of_vms = (num_of_waiting_tasks / Float(cores_per_machine)).ceil
  Djinn.log_debug("Will run #{num_of_waiting_tasks} on " +
    "#{optimal_num_of_vms} VMs")

  # The optimal number of VMs is optimal with respect to performance, but
  # is not optimal with respect to cost. As the user has told us what the
  # maximum number of machines they want to run are, grab that number and
  # compare the two to see how many machines we should actually acquire.
  user_num_of_vms = ZKInterface.get_max_machines_for_babel_slaves()

  total_num_of_vms_needed = [optimal_num_of_vms, user_num_of_vms].min
  Djinn.log_debug("For #{num_of_waiting_tasks} tasks, the optimal number of " +
    "VMs to use is #{optimal_num_of_vms} VMs, while the user specified that " +
    "no more than #{user_num_of_vms} VMs - using #{total_num_of_vms_needed} " +
    "total VMs")

  # A previous invocation of this function may have already spawned up
  # babel slaves, so to obey the maximum that the user has given us, we have to
  # subtract any already running babel slaves out of the value calculated above.
  babel_slaves_already_running = 0
  @nodes.each { |node|
    babel_slaves_already_running += 1 if node.is_babel_slave?
  }

  num_of_vms_needed = total_num_of_vms_needed - babel_slaves_already_running

  if num_of_vms_needed > 0
    Djinn.log_debug("#{babel_slaves_already_running} VMs are already running " +
      "as babel slaves, so we still need to spawn #{num_of_vms_needed} VMs")

    # Include rabbitmq_slave in here since we want to always be able to point
    # our RabbitMQ client to localhost to get tasks
    nodes_needed = []
    num_of_vms_needed.times { |i|
      nodes_needed << ["rabbitmq_slave", "babel_slave"]
    }

    start_new_roles_on_nodes(nodes_needed, instance_type,
      HelperFunctions.get_secret())
  else
    Djinn.log_debug("#{babel_slaves_already_running} VMs are already " +
      "running, and as can only have a maximum of #{num_of_vms_needed}, we " +
      "don't need to acquire more babel slaves right now")
  end

  return
end


# This method spawns a thread for each task given to execute them in parallel.
# It then waits for all tasks to complete before returning.
def execute_multiple_tasks(tasks)
  threads = []
  tasks.each { |task|
    threads << Thread.new {
      run_task(task)
    }
  }

  threads.each { |t| t.join }
end
