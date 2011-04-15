#!/usr/bin/ruby
# Programmer: Chris Bunch
# baz

require 'djinn'

ERLANG_OUTPUT = "/tmp/erlang_output"

public 

def neptune_erlang_run_job(nodes, job_data, secret)
  return BAD_SECRET_MSG unless valid_secret?(secret)
  Djinn.log_debug("erlang - run")

  Thread.new {
    keyname = @creds['keyname']
    nodes = Djinn.convert_location_array_to_class(nodes, keyname)

    ENV['HOME'] = "/root"

    code = job_data['@code'].split(/\//)[-1]

    unless my_node.is_shadow?
      Djinn.log_run("rm -rfv /tmp/#{code}")
      copyFromShadow("/tmp/#{code}")
    end
    sleep(1)

    module_name = code.split(/\./)[0]
    Djinn.log_debug("got code #{code}, trying to run module #{module_name}")
    Djinn.log_run("cd /tmp; erl -noshell -run #{module_name} main > #{ERLANG_OUTPUT}")

    shadow = get_shadow
    shadow_ip = shadow.private_ip
    shadow_key = shadow.ssh_key

    HelperFunctions.scp_file(ERLANG_OUTPUT, ERLANG_OUTPUT, shadow_ip, shadow_key)

    neptune_write_job_output(job_data, ERLANG_OUTPUT)

    remove_lock_file(job_data)

    Djinn.log_run("rm -rfv /tmp/#{code}")
  }

  return "OK"
end

private

def start_erlang_master()
  Djinn.log_debug("#{my_node.private_ip} is starting erlang master")
end

def start_erlang_slave()
  Djinn.log_debug("#{my_node.private_ip} is starting erlang slave")
end

def stop_erlang_master()
  Djinn.log_debug("#{my_node.private_ip} is stopping erlang master")
end

def stop_erlang_slave()
  Djinn.log_debug("#{my_node.private_ip} is stopping erlang slave")
end

