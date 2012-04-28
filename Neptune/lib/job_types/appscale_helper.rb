#!/usr/bin/ruby
# Programmer: Chris Bunch
# baz

require 'djinn'

public 


def neptune_appscale_run_job(nodes, job_data, secret)
  if !valid_secret?(secret)
    return BAD_SECRET_MSG
  end

  Djinn.log_debug("appscale - run")

  required_params = %w{@time_needed_for @add_component}
  if !has_all_required_params?(job_data, required_params)
    return MISSING_PARAM
  end

  Thread.new {
    wait_for_allotted_time(job_data)
  }

  return STARTED_SUCCESSFULLY
end


# When spawning up nodes to use for AppScale, we force the user to specify
# how long the nodes should live for. This method simply waits that long.
# TODO(cgb): What about cases when the nodes should last forever?
def wait_for_allotted_time(job_data)
  start_time = Time.now
  time_allotted = Integer(job_data["@time_needed_for"])
  item_spawned = job_data["@add_component"]

  loop {
    now = Time.now
    time_elapsed = now - start_time
    Djinn.log_debug("time elapsed for #{item_spawned} so far is" +
      " #{time_elapsed}, time allotted is #{time_allotted}")
    break if time_elapsed > time_allotted
    Kernel.sleep(60)
  }

  remove_lock_file(job_data)
end
