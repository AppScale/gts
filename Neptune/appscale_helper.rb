#!/usr/bin/ruby
# Programmer: Chris Bunch
# baz

require 'djinn'

public 

def neptune_appscale_run_job(nodes, job_data, secret)
  return BAD_SECRET_MSG unless valid_secret?(secret)
  Djinn.log_debug("appscale - run")

  Thread.new {
    start_time = Time.now
    time_allotted = Integer(job_data["@time_needed_for"])
    item_spawned = job_data["@add_component"]

    loop {
      now = Time.now
      time_elapsed = now - start_time
      Djinn.log_debug("time elapsed for #{item_spawned} so far is #{time_elapsed}, time allotted is #{time_allotted}")
      break if time_elapsed > time_allotted
      sleep(60)
    }

    remove_lock_file(job_data)
  }

  return "OK"
end

