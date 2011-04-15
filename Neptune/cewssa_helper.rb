#!/usr/bin/ruby
# Programmer: Chris Bunch
# baz

require 'djinn'

BIRTH_DEATH = "/usr/local/lib/R/site-library/cewSSA/data/birth_death.r"
OUTPUT_HOME = "/usr/local/cewssa/data"
OUR_CEWSSA_CODE = "#{APPSCALE_HOME}/Neptune/run_dwSSA.R"
MERGE_SCRIPT = "#{APPSCALE_HOME}/Neptune/average_probs.R"

public 

def neptune_cewssa_run_job(nodes, job_data, secret)
  Djinn.log_debug("cewssa - pre-run")
  return BAD_SECRET_MSG unless valid_secret?(secret)

  #message = validate_environment(job_data, secret)
  #return message unless message == "no error"

  Djinn.log_debug("cewssa - run")

  Thread.new {

    start_time = Time.now

    keyname = @creds['keyname']
    nodes = Djinn.convert_location_array_to_class(nodes, keyname)

    num_nodes = nodes.length
    num_sims = job_data["@simulations"]
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

    threads = []
    at = 0

    random_numbers = []
    nodes.length.times {
      loop {
        possible_rand = rand(1000)
        unless random_numbers.include?(possible_rand)
          random_numbers << possible_rand
          break
        end
      }
    }
 
    nodes.each_with_index { |node, i|
      threads << Thread.new {
        ip = node.private_ip
        ssh_key = node.ssh_key
        start = at
        fin = at + sims[i]
        at = fin
        remote_del_command = "rm -rf #{OUTPUT_HOME}/*"
        Djinn.log_run("ssh -i #{ssh_key} -o StrictHostkeyChecking=no root@#{ip} '#{remote_del_command}'")

        iterations = fin - start # don't need to add one here
        seed = random_numbers[i]

        output_file = "#{OUTPUT_HOME}/data#{i}.txt"
        remote_run_command = "#{OUR_CEWSSA_CODE} #{BIRTH_DEATH} #{iterations} #{seed} 1.454 0.686 > #{output_file}" 
        Djinn.log_run("ssh -i #{ssh_key} -o StrictHostkeyChecking=no root@#{ip} '#{remote_run_command}'")
      }
    }

    Djinn.log_debug("cewssa - joining threads")

    threads.each { |t| t.join }

    Djinn.log_debug("cewssa - retrieving run data")

    nodes.each { |node|
      ip = node.private_ip
      ssh_key = node.ssh_key
      remote_cp_command = "scp -i #{ssh_key} -o StrictHostkeyChecking=no root@#{ip}:#{OUTPUT_HOME}/data* #{OUTPUT_HOME}/"
      Djinn.log_run(remote_cp_command)
    }

    Djinn.log_debug("cewssa - collecting stats")

    collect_stats = "#{MERGE_SCRIPT} #{OUTPUT_HOME}/data* > #{OUTPUT_HOME}/finalresult.txt"
    Djinn.log_run(collect_stats)

    fin_time = Time.now
    total = fin_time - start_time
    Djinn.log_debug("cewssa - done!")
    Djinn.log_debug("TIMING: Took #{total} seconds.")

    shadow = get_shadow
    shadow_ip = shadow.private_ip
    shadow_key = shadow.ssh_key

    final_result = "#{OUTPUT_HOME}/finalresult.txt"
    HelperFunctions.scp_file(final_result, final_result, shadow_ip, shadow_key)

    neptune_write_job_output(job_data, final_result)

    remove_lock_file(job_data)
  }

  return "OK"
end

private

def neptune_cewssa_get_output(job_data)
  return OUTPUT_HOME
end

def start_cewssa_master()
  Djinn.log_debug("#{my_node.private_ip} is starting cewssa master")
end

def start_cewssa_slave()
  Djinn.log_debug("#{my_node.private_ip} is starting cewssa slave")
end

def stop_cewssa_master()
  Djinn.log_debug("#{my_node.private_ip} is stopping cewssa master")
  # tell the shadow we're done running cewssa jobs
end

def stop_cewssa_slave()
  Djinn.log_debug("#{my_node.private_ip} is stopping cewssa slave")
end

