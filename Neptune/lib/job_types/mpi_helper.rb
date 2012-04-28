#!/usr/bin/ruby
# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..", "AppController")
require 'djinn'


$:.unshift File.join(File.dirname(__FILE__), "..", "AppController", "lib")
require 'datastore_factory'


MPD_HOSTS = "/tmp/mpd.hosts"
MPI_OUTPUT = "/tmp/thempioutput"

public 

def neptune_mpi_run_job(nodes, job_data, secret)
  return BAD_SECRET_MSG unless valid_secret?(secret)
  Djinn.log_debug("mpi - run")

  Thread.new {
    job_data['@metadata_info'] = {'received_job_at' => Time.now.to_i}

    keyname = @creds['keyname']
    nodes = Djinn.convert_location_array_to_class(nodes, keyname)

    ENV['LD_LIBRARY_PATH'] = "/usr/lib"
    Djinn.log_debug("library path = #{ENV['LD_LIBRARY_PATH']}")

    start_nfs(nodes)

    sleep(5) # CGB

    shadow = get_shadow
    shadow_ip = shadow.private_ip
    shadow_key = shadow.ssh_key

    remote = job_data['@code']
    splitted_code = remote.split('/')
    remote_dir = splitted_code[0..splitted_code.length-2].join('/')
    filename_to_exec = splitted_code[2..splitted_code.length-1].join('/')
    Djinn.log_debug("remote dir is [#{remote_dir}], filename_to_exec is #{filename_to_exec}")

    storage = job_data['@storage']

    unless my_node.is_shadow?
      Djinn.log_run("rm -fv /tmp/#{filename_to_exec}")
    end

    working_dir = "/mirrornfs/#{HelperFunctions.get_random_alphanumeric()}"
    FileUtils.mkdir_p(working_dir)
    Djinn.copy_code_and_inputs_to_dir(job_data, working_dir)

    start_mpd(nodes)
    sleep(5)

    if job_data["@procs_to_use"]
      num_of_procs = job_data["@procs_to_use"]
    else
      num_of_procs = nodes.length
    end

    # Some job types (e.g., kdt) need to specify something a program to use
    # to run the user's code (e.g., Python), so let them do so via the
    # executable parameter.
    if job_data["@executable"]
      executable = job_data["@executable"]
    else
      executable = ""
    end

    # If the user specifies an argv to pass to the code to exec, be sure to
    # capture it and pass it along
    if job_data["@argv"]
      argv = job_data["@argv"]
      # TODO(cgb): filter out colons and other things that malicious users could
      # use to hijack the system
    else
      argv = ""
    end

    output_file = "/tmp/mpi-output-#{rand()}"
    error_file = "/tmp/mpi-error-#{rand()}"

    full_path_to_file = "#{working_dir}/#{filename_to_exec}"

    start_time = Time.now
    Djinn.log_run("mpiexec -env X10_NTHREADS 1 -n #{num_of_procs} " +
      "#{executable} #{full_path_to_file} #{argv} 1>#{output_file} 2>#{error_file}")
    end_time = Time.now
 
    total = end_time - start_time
    Djinn.log_debug("MPI: Done running job!")
    Djinn.log_debug("TIMING: Took #{total} seconds")

    job_data['@metadata_info']['start_time'] = start_time.to_i
    job_data['@metadata_info']['end_time'] = end_time.to_i
    job_data['@metadata_info']['total_execution_time'] = total

    stop_mpd()

    stop_nfs(nodes)

    Djinn.write_babel_outputs(output_file, error_file, job_data)

    # clean up after ourselves - remove the user's code and any outputs
    # it may have produced
    Djinn.log_debug("Removing working dir #{working_dir}")
    FileUtils.rm_rf(working_dir)
    FileUtils.rm_rf(output_file)
    FileUtils.rm_rf(error_file)

    remove_lock_file(job_data)
  }

  return "OK"
end

private

def neptune_mpi_get_output(job_data)
  return MPI_OUTPUT
end 

def start_nfs(nodes)
  Djinn.log_run("/etc/init.d/nfs-kernel-server start")
  sleep(10)

  slave_nodes = nodes - [my_node]
  return if slave_nodes.empty?

  slave_mount = "mount #{my_node.private_ip}:/mirrornfs /mirrornfs"
  slave_nodes.each { |node|
    Djinn.log_debug("[nfs master] node at #{node.private_ip} is currently doing #{node.jobs.join(', ')}")
    next if node.private_ip == my_node.private_ip
    Djinn.log_debug("mounting /mirrornfs on machine located at [#{node.private_ip}]")
    HelperFunctions.run_remote_command(node.private_ip, slave_mount, node.ssh_key, NO_OUTPUT)
  }

  sleep(10)
end

def stop_nfs(nodes)
  slave_nodes = nodes - [my_node]

  unless slave_nodes.empty?
    slave_nodes.each { |node|
      next if node.private_ip == my_node.private_ip
      unmount_nfs_store(node.private_ip, node.ssh_key)
    }
  end

  Djinn.log_run("/etc/init.d/nfs-kernel-server stop")

  nodes.each { |node|
    Djinn.log_run("ssh #{node.private_ip} 'ps ax | grep nfs'")
    sleep(1)
  }
end

def unmount_nfs_store(ip, ssh_key)
  slave_umount = "umount /mirrornfs"

  loop {
    Djinn.log_debug("unmounting mirrornfs at #{ip} with ssh key #{ssh_key}")
    HelperFunctions.run_remote_command(ip, slave_umount, ssh_key, NO_OUTPUT)
    sleep(5)
    mount_status = `ssh root@#{ip} 'mount'`
    nfs_mounted = mount_status.scan(/mirrornfs/)
    Djinn.log_debug("NFS mount status at #{ip} is [#{nfs_mounted}]")

    if nfs_mounted == []
      Djinn.log_debug("NFS is stopped at #{ip}")
      break
    else
      Djinn.log_debug("NFS still not stopped at #{ip}")
    end
  }
end

def start_mpd(nodes)
  mpd_hosts_contents = ""
  nodes.each { |node|
    mpd_hosts_contents << "#{node.private_ip}\n"
  }
  mpd_hosts_contents.chomp!
  Djinn.log_debug("MPD Hosts are: #{mpd_hosts_contents}")
  HelperFunctions.write_file(MPD_HOSTS, mpd_hosts_contents) 

  ssh_keys = []
  nodes.each { |node|
     ssh_keys << node.ssh_key
  }
  ssh_keys.uniq!

  Djinn.log_run("mpdboot -r 'ssh -o StrictHostkeyChecking=no -i #{ssh_keys.join(' -i ')}' -f #{MPD_HOSTS} -n #{nodes.length}")
end

def stop_mpd()
  Djinn.log_run("mpdallexit")
  `rm -fv #{MPD_HOSTS}`
end

def start_mpi_master()
  Djinn.log_debug("#{my_node.private_ip} is starting mpi master")
end

def start_mpi_slave()
  Djinn.log_debug("#{my_node.private_ip} is starting mpi slave")
end

def stop_mpi_master()
  Djinn.log_debug("#{my_node.private_ip} is stopping mpi master")
end

def stop_mpi_slave()
  Djinn.log_debug("#{my_node.private_ip} is stopping mpi slave")
end

