#!/usr/bin/ruby
# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..", "AppController")
require 'djinn'


$:.unshift File.join(File.dirname(__FILE__), "..", "AppController", "lib")
require 'datastore_factory'


public 

def neptune_r_run_job(nodes, job_data, secret)
  return BAD_SECRET_MSG unless valid_secret?(secret)
  Djinn.log_debug("r - run")

  Thread.new {
    keyname = @creds['keyname']
    nodes = Djinn.convert_location_array_to_class(nodes, keyname)

    Djinn.log_debug("job data is #{job_data.inspect}")

    code = job_data['@code'].split(/\//)[-1]

    code_dir = "/tmp/r-#{rand()}/"
    code_loc = "#{code_dir}/#{code}"
    output_loc = "#{code_dir}/output.txt"
    FileUtils.mkdir_p(code_dir)

    remote = job_data['@code']
    storage = job_data['@storage']

    datastore = DatastoreFactory.get_datastore(storage, job_data)
    datastore.get_output_and_save_to_fs(remote, code_loc)

    Djinn.log_debug("got code #{code}, saved at #{code_loc}")
    Djinn.log_run("chmod +x #{code_loc}")
    Djinn.log_run("Rscript --vanilla #{code_loc} > #{output_loc}")

    datastore.write_remote_file_from_local_file(job_data['@output'], output_loc)
    remove_lock_file(job_data)
  }

  return "OK"
end

private

def start_r_master()
  Djinn.log_debug("#{my_node.private_ip} is starting r master")
end

def start_r_slave()
  Djinn.log_debug("#{my_node.private_ip} is starting r slave")
end

def stop_r_master()
  Djinn.log_debug("#{my_node.private_ip} is stopping r master")
end

def stop_r_slave()
  Djinn.log_debug("#{my_node.private_ip} is stopping r slave")
end

