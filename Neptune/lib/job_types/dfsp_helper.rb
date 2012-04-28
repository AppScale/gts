#!/usr/bin/ruby
# Programmer: Chris Bunch
# baz

require 'djinn'

DFSP_HOME = "/usr/local/dfsp"

public 

def neptune_dfsp_run_job(nodes, job_data, secret)
  return BAD_SECRET_MSG unless valid_secret?(secret)
  Djinn.log_debug("dfsp - run")

  Thread.new {
    start_time = Time.now

    keyname = @creds['keyname']
    nodes = Djinn.convert_location_array_to_class(nodes, keyname)
    sims = neptune_get_ssa_num_simulations(nodes, job_data)

    threads = []
    at = 0 
    nodes.each_with_index { |node, i|
      threads << Thread.new {
        ip = node.private_ip
        ssh_key = node.ssh_key
        start = at
        fin = at + sims[i]
        at = fin
        remote_del_command = "rm -rf #{DFSP_HOME}/data*"
        remote_run_command = "cd #{DFSP_HOME}; ./multi_run.pl #{start} #{fin}"
        Djinn.log_run("ssh -i #{ssh_key} -o StrictHostkeyChecking=no root@#{ip} '#{remote_del_command}'")
        Djinn.log_run("ssh -i #{ssh_key} -o StrictHostkeyChecking=no root@#{ip} '#{remote_run_command}'")
      }
    }

    Djinn.log_debug("dfsp - joining threads")

    threads.each { |t| t.join }

    Djinn.log_debug("dfsp - retrieving run data")

    nodes.each { |node|
      ip = node.private_ip
      ssh_key = node.ssh_key
      remote_cp_command = "scp -i #{ssh_key} -o StrictHostkeyChecking=no root@#{ip}:#{DFSP_HOME}/data* #{DFSP_HOME}/"
      Djinn.log_run(remote_cp_command)
    }  

    Djinn.log_debug("dfsp - collecting stats")

    collect_stats = "cd #{DFSP_HOME}/; ./collect_stats.pl #{at} >out 2>err"
    Djinn.log_run(collect_stats)

    fin_time = Time.now
    total = fin_time - start_time
    Djinn.log_debug("dfsp - done!")
    Djinn.log_debug("TIMING: Took #{total} seconds.")

    shadow = get_shadow
    shadow_ip = shadow.private_ip
    shadow_key = shadow.ssh_key

    out = "#{DFSP_HOME}/out"
    HelperFunctions.scp_file(out, out, shadow_ip, shadow_key)

    err = "#{DFSP_HOME}/err"
    HelperFunctions.scp_file(err, err, shadow_ip, shadow_key)

    data = "#{DFSP_HOME}/data*"
    HelperFunctions.scp_file(data, DFSP_HOME, shadow_ip, shadow_key)

    neptune_write_job_output(job_data, out)

    remove_lock_file(job_data)
  }

  return "OK"
end

private

def neptune_dfsp_get_output(job_data)
  return DFSP_HOME
end

def start_dfsp_master()
  Djinn.log_debug("#{my_node.private_ip} is starting dfsp master")
end

def start_dfsp_slave()
  Djinn.log_debug("#{my_node.private_ip} is starting dfsp slave")
end

def stop_dfsp_master()
  Djinn.log_debug("#{my_node.private_ip} is stopping dfsp master")
end

def stop_dfsp_slave()
  Djinn.log_debug("#{my_node.private_ip} is stopping dfsp slave")
end


