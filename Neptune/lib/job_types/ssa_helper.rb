#!/usr/bin/ruby
# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..", "..")
require 'neptune_manager'


$:.unshift File.join(File.dirname(__FILE__), "..", "AppController", "lib")
require 'datastore_factory'


MULTICORE = true
SSA_HOME = "/usr/local/StochKit2.0/"


IS_FILE = true
NOT_A_FILE = false


public 


def neptune_ssa_run_job(nodes, job_data, secret)
  return BAD_SECRET_MSG unless valid_secret?(secret)
  Djinn.log_debug("ssa - run")

  Thread.new {
    start_time = Time.now
    total_compute_time = 0
    total_storage_time = 0
    total_slowest_path = 0
    c_times = []
    s_times = []

    Djinn.log_debug("job data is #{job_data.inspect}")
    keyname = @creds['keyname']

    nodes = Djinn.convert_location_array_to_class(nodes, keyname)

    sims = neptune_get_ssa_num_simulations(nodes, job_data)

    working_dir = "/tmp/ssa-#{rand(10000)}"
    FileUtils.mkdir_p(working_dir)

    tar = working_dir + "/" + File.basename(job_data['@tar'])

    Djinn.log_debug("tar is #{job_data['@tar']}")
    Djinn.log_debug("working dir is #{working_dir}")

    remote = job_data['@tar']

    datastore = DatastoreFactory.get_datastore(job_data['@storage'], job_data)
    datastore.get_output_and_save_to_fs(remote, tar)

    neptune_uncompress_file(tar)

    num_sims = job_data["@trajectories"] || job_data["@simulations"]

    param_num = job_data['@param_num']

    threads = []
    node_times = []
    at = 0 
    nodes.each_with_index { |node, i|
      threads << Thread.new {
        node_times[i] = 0

        ip = node.private_ip
        ssh_key = node.ssh_key
        start = at
        fin = at + sims[i]
        at = fin
        fin -= 1 
        Djinn.log_debug("This node will run trajectories #{start} to #{fin}")

        code_path = "#{working_dir}/code/run.sh"
        Djinn.log_run("chmod +x #{code_path}")
        exec = "bash #{code_path}"

        input = "#{working_dir}/code/#{job_data['@input']}"

        unless ip == HelperFunctions.local_ip
          Djinn.log_run("scp -r -i #{ssh_key} -o StrictHostkeyChecking=no #{working_dir} root@#{ip}:#{working_dir}")
        end

        trajectories = fin - start + 1 

        if MULTICORE
          cores = HelperFunctions.get_num_cpus()
        else
          cores = 1
        end

        done = 0
        loop {
          trajectories_left = trajectories - done
          Djinn.log_debug("Need to run #{trajectories_left} more trajectories on #{cores} cores")
          break if trajectories_left.zero?
          need_to_run = [trajectories_left, cores].min

          Djinn.log_debug("Running #{need_to_run} trajectories")
          core_threads = []
          current_times = []
          need_to_run.times { |j|
            core_threads << Thread.new {
              my_trajectory = start+done+j
              Djinn.log_debug("Thread #{j} is running trajectory #{my_trajectory}")
              output = File.expand_path("#{working_dir}/output-#{my_trajectory}")

              # run the computation, remembering to place StochKit in the user's PATH
              path = "PATH=$PATH:#{SSA_HOME}"
              run_command = "#{path} #{exec} #{input} #{output} #{my_trajectory} #{param_num}"

              start_compute = Time.now
              Djinn.log_run("ssh -i #{ssh_key} -o StrictHostkeyChecking=no root@#{ip} '#{run_command}'")
              end_compute = Time.now
              c_time = end_compute - start_compute
              total_compute_time += c_time
              c_times << c_time

              # copy the output back to this box - in the future we can do merges here
              # or in the future we can just have the node upload to s3
              start_storage = Time.now
              unless HelperFunctions.local_ip == ip
                remote_cp_command = "scp -r -i #{ssh_key} -o StrictHostkeyChecking=no root@#{ip}:#{output} #{output}"
                Djinn.log_run(remote_cp_command)

              end

              remote_location = "#{job_data['@output']}/output-#{my_trajectory}"
              datastore.write_remote_file_from_local_file(remote_location, output)
              end_storage = Time.now
              s_time = end_storage - start_storage
              total_storage_time += s_time
              s_times << s_time

              node_times[i] += (c_time + s_time)

              # remove our output - we can't want the disk to fill up
              remove_cmd = "rm -rf #{output}"
              Djinn.log_run("ssh -i #{ssh_key} -o StrictHostkeyChecking=no root@#{ip} '#{remove_cmd}'")
              Djinn.log_run(remove_cmd)
            }
          }

          core_threads.each { |c| c.join }

          done += need_to_run
          Djinn.log_debug("Done running #{need_to_run} trajectories, #{trajectories - done} to go")
        }
      }
    }

    Djinn.log_debug("ssa - joining threads")

    threads.each { |t| t.join }

    # clean up after ourselves
    Djinn.log_run("rm -rf #{working_dir}")

    fin_time = Time.now
    total = fin_time - start_time
    total_slowest_path = node_times.max
    total_overhead_time = total - total_slowest_path

    timing_info = <<BAZ
    TIMING: total execution time is #{total} seconds.
    TIMING: total compute time is #{total_compute_time} seconds.
    TIMING: total storage time is #{total_storage_time} seconds.
    TIMING: slowest path time is #{total_slowest_path} seconds.
    TIMING: overhead time is #{total_overhead_time} seconds.
    TIMING: average compute time is #{average(c_times)} seconds.
    TIMING: stddev compute time is #{standard_deviation(c_times)} seconds.
    TIMING: average storage time is #{average(s_times)} seconds.
    TIMING: stddev storage time is #{standard_deviation(s_times)} seconds.
    RAW_DATA: node times are: [#{node_times.join(', ')}]
    RAW_DATA: compute times are: [#{c_times.join(', ')}]
    RAW_DATA: storage times are: [#{s_times.join(', ')}]
BAZ

    Djinn.log_debug(timing_info)

    remote_location = "#{job_data['@output']}/timing_info.txt"
    datastore.write_remote_file_from_string(remote_location, timing_info)

    remove_lock_file(job_data)
  }

  return "OK"
end

private

def neptune_ssa_get_output(job_data)
  return SSA_HOME
end

def start_ssa_master()
  Djinn.log_debug("#{my_node.private_ip} is starting ssa master")
end

def start_ssa_slave()
  Djinn.log_debug("#{my_node.private_ip} is starting ssa slave")
end

def stop_ssa_master()
  Djinn.log_debug("#{my_node.private_ip} is stopping ssa master")
end

def stop_ssa_slave()
  Djinn.log_debug("#{my_node.private_ip} is stopping ssa slave")
end

def neptune_get_ssa_seed_vals(num_vals)
  random_numbers = []
  loop {
    possible_rand = rand(32000)
    unless random_numbers.include?(possible_rand)
      random_numbers << possible_rand
    end
    break if num_vals == random_numbers.length
  }

  return random_numbers
end

def neptune_get_ssa_num_simulations(nodes, job_data)
  num_nodes = nodes.length
  num_sims = job_data["@trajectories"] || job_data["@simulations"]
  sims_per_node = num_sims / num_nodes

  Djinn.log_debug("num nodes = #{num_nodes}")
  Djinn.log_debug("num_sims = #{num_sims}")
  Djinn.log_debug("sims_per_node = #{sims_per_node}")

  # set up how many simulations each node
  # should run by divying it up equally
  # any remainder can be assigned to an
  # arbitrary node

  sims = [sims_per_node] * num_nodes
  remainder = num_sims % num_nodes
  sims[-1] += remainder

  Djinn.log_debug("sims = #{sims.join(', ')}")
  Djinn.log_debug("remainder = #{remainder}")

  return sims
end

def average(population)
  total = 0.0
  n = 0

  population.each { |val|
    total += val
    n += 1
  }

  return total / n
end

def variance(population)
  n    = 0
  mean = 0.0

  sum = population.reduce(0.0) do |sum, x|
    n     += 1
    delta  = x - mean
    mean  += delta / n

    sum + delta * (x - mean)
  end

  sum / n
end

def standard_deviation(population)
  Math.sqrt(variance(population))
end
