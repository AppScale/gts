#!/usr/bin/ruby
# Programmer: Chris Bunch
# baz

require 'djinn'

public 

def neptune_urdme_run_job(nodes, job_data, secret)
  return BAD_SECRET_MSG unless valid_secret?(secret)
  Djinn.log_debug("urdme - run")

  Thread.new {
    start_time = Time.now

    keyname = @creds['keyname']
    nodes = Djinn.convert_location_array_to_class(nodes, keyname)

    # copy code to /tmp on all boxen
    # get unique seeds for all boxen
    # on each box, run the code
    # pipe stdout/err > somewhere (progress bar later?)

    # find where the output is being saved to
    # tell each box to store the data into the db,
    # or just copy it to master and tgz it?
  }

  return "OK"
end

private

def neptune_urdme_get_output(job_data)
  abort("definitely not implemented yet")
  return DFSP_HOME
end

def start_urdme_master()
  Djinn.log_debug("#{my_node.private_ip} is starting urdme master")
end

def start_urdme_slave()
  Djinn.log_debug("#{my_node.private_ip} is starting urdme slave")
end

def stop_urdme_master()
  Djinn.log_debug("#{my_node.private_ip} is stopping urdme master")
end

def stop_urdme_slave()
  Djinn.log_debug("#{my_node.private_ip} is stopping urdme slave")
end


