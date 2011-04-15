#!/usr/bin/ruby
# Programmer: Chris Bunch
# baz

require 'djinn'

MPD_HOSTS = "/tmp/mpd.hosts"
MPI_OUTPUT = "/tmp/thempioutput"

public 

def neptune_mpi_run_job(nodes, job_data, secret)
  return BAD_SECRET_MSG unless valid_secret?(secret)
  Djinn.log_debug("mpi - run")

  Thread.new {
    keyname = @creds['keyname']
    nodes = Djinn.convert_location_array_to_class(nodes, keyname)

    ENV['LD_LIBRARY_PATH'] = "/usr/lib"
    Djinn.log_debug("library path = #{ENV['LD_LIBRARY_PATH']}")

    start_nfs(nodes)

    sleep(5) # CGB

    shadow = get_shadow
    shadow_ip = shadow.private_ip
    shadow_key = shadow.ssh_key

    Djinn.log_run("rm -fv /mirrornfs/thempicode #{MPI_OUTPUT}")

    unless my_node.is_shadow?
      Djinn.log_run("rm -fv /tmp/thempicode")
      copyFromShadow("/tmp/thempicode")
    end

    sleep(5)
    Djinn.log_run("cp /tmp/thempicode /mirrornfs/")
    sleep(5) # CGB

    start_mpd(nodes)
    sleep(5) # CGB

    if job_data["@procs_to_use"]
      num_of_procs = job_data["@procs_to_use"]
    else
      num_of_procs = nodes.length
    end

    start_time = Time.now
    Djinn.log_run("mpiexec -env X10_NTHREADS 1 -n #{num_of_procs} /mirrornfs/thempicode > #{MPI_OUTPUT}")
    end_time = Time.now
 
    total = end_time - start_time
    Djinn.log_debug("MPI: Done running job!")
    Djinn.log_debug("TIMING: Took #{total} seconds")

    stop_mpd()

    stop_nfs(nodes)

    shadow = get_shadow
    shadow_ip = shadow.private_ip
    shadow_key = shadow.ssh_key

    HelperFunctions.scp_file(MPI_OUTPUT, MPI_OUTPUT, shadow_ip, shadow_key)

    neptune_write_job_output(job_data, MPI_OUTPUT)

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

