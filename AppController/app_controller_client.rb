#!/usr/bin/ruby -w
# Programmer: Chris Bunch

require 'openssl'
require 'soap/rpc/driver'
require 'timeout'

IP_REGEX = /\d+\.\d+\.\d+\.\d+/
FQDN_REGEX = /[\w\d\.\-]+/
IP_OR_FQDN = /#{IP_REGEX}|#{FQDN_REGEX}/

NO_TIMEOUT = -1
RETRY_ON_FAIL = true
ABORT_ON_FAIL = false

class AppControllerClient
  attr_reader :conn, :ip, :secret
  
  def initialize(ip, secret)
    @ip = ip
    @secret = secret
    
    @conn = SOAP::RPC::Driver.new("https://#{@ip}:17443")
    @conn.add_method("set_parameters", "djinn_locations", "database_credentials", "app_names", "secret")
    @conn.add_method("set_apps", "app_names", "secret")
    @conn.add_method("status", "secret")
    @conn.add_method("update", "app_names", "secret")
    @conn.add_method("stop_app", "app_name", "secret")    
    @conn.add_method("get_all_public_ips", "secret")
    @conn.add_method("backup_appscale", "backup_in_info", "secret")
    @conn.add_method("backup_database_state", "backup_info", "secret")
    @conn.add_method("done", "secret")
    @conn.add_method("add_role", "new_role", "secret")
    @conn.add_method("remove_role", "old_role", "secret")
  end
  
  def make_call(time, retry_on_except, ok_to_fail=false)
    refused_count = 0
    max = 10

    begin
      Timeout::timeout(time) {
        yield if block_given?
      }
    rescue Errno::ECONNREFUSED
      if refused_count > max
        return false if ok_to_fail
        abort("Connection was refused. Is the AppController running?")
      else
        refused_count += 1
        sleep(1)
        retry
      end
    rescue Timeout::Error
      return false if ok_to_fail
      retry
    rescue OpenSSL::SSL::SSLError, NotImplementedError, Errno::EPIPE, Errno::ECONNRESET
      retry
    rescue Exception => except
      if retry_on_except
        retry
      else
        abort("We saw an unexpected error of the type #{except.class} with the following message:\n#{except}.")
      end
    end
  end

  def get_userappserver_ip(verbose_level="low") 
    userappserver_ip, status, state, new_state = "", "", "", ""
    loop {
      status = get_status()

      new_state = status.scan(/Current State: ([\w\s\d\.,]+)\n/).flatten.to_s.chomp
      if verbose_level == "high" and new_state != state
        puts new_state
        state = new_state
      end
    
      if status == "false: bad secret"
        abort("\nWe were unable to verify your secret key with the head node specified in your locations file. Are you sure you have the correct secret key and locations file?\n\nSecret provided: [#{@secret}]\nHead node IP address: [#{@ip}]\n")
      end
        
      if status =~ /Database is at (#{IP_OR_FQDN})/ and $1 != "not-up-yet"
        userappserver_ip = $1
        break
      end
      
      sleep(10)
    }
    
    return userappserver_ip
  end

  def set_parameters(locations, creds, apps_to_start)
    result = ""
    make_call(10, ABORT_ON_FAIL) { 
      result = conn.set_parameters(locations, creds, apps_to_start, @secret)
    }  
    abort(result) if result =~ /Error:/
  end

  def set_apps(app_names)
    result = ""
    make_call(10, ABORT_ON_FAIL) { 
      result = conn.set_apps(app_names, @secret)
    }  
    abort(result) if result =~ /Error:/
  end

  def status(print_output=true)
    status = get_status()
         
    if print_output
      puts "Status of node at #{ip}:"
      puts "#{status}"
    end

    return status
  end

  def get_status(ok_to_fail=false)
    make_call(10, !ok_to_fail, ok_to_fail) { @conn.status(@secret) }
  end

  def stop_app(app_name)
    make_call(30, RETRY_ON_FAIL) { @conn.stop_app(app_name, @secret) }
  end
  
  def update(app_names)
    make_call(30, RETRY_ON_FAIL) { @conn.update(app_names, @secret) }
  end

  def done()
    make_call(30, RETRY_ON_FAIL) { @conn.done(@secret) }
  end
 
  def get_all_public_ips()
    make_call(30, RETRY_ON_FAIL) { @conn.get_all_public_ips(@secret) }
  end

  def backup_appscale(backup_info)
    make_call(NO_TIMEOUT, RETRY_ON_FAIL) { @conn.backup_appscale(backup_info, @secret) }
  end

  def backup_database_state(backup_info)
    make_call(NO_TIMEOUT, RETRY_ON_FAIL) { @conn.backup_database_state(backup_info, @secret) }
  end

  def add_role(role)
    make_call(NO_TIMEOUT, RETRY_ON_FAIL) { @conn.add_role(role, @secret) }
  end

  # CGB - removed timeout here - removing cassandra slave requires it to port
  # the data it owns to somebody else, which takes ~30 seconds in the trivial
  # case
  def remove_role(role)
    make_call(NO_TIMEOUT, RETRY_ON_FAIL) { @conn.remove_role(role, @secret) }
  end

  def run_neptune_job(nodes, job_data)
    type = job_data["@type"]

    if NEPTUNE_JOBS.include?(type)
      method_to_call = "neptune_#{type}_run_job"
      @conn.add_method(method_to_call, "nodes", "job_data", "secret")
      make_call(30, RETRY_ON_FAIL) { @conn.send(method_to_call.to_sym, nodes, job_data, @secret) }
    else
      not_supported_message = "The job type you specified, '#{type}', is " +
       "not supported. Supported jobs are #{NEPTUNE_JOBS.join(', ')}."
      abort(not_supported_message)
    end
  end

  def wait_for_node_to_be(new_roles)
    roles = new_roles.split(":")

    loop {
      ready = true
      status = get_status
      Djinn.log_debug("ACC: Node at #{@ip} said [#{status}]")
      roles.each { |role|
        if status =~ /#{role}/
          Djinn.log_debug("ACC: Node is #{role}")
        else
          ready = false
          Djinn.log_debug("ACC: Node is not yet #{role}")
        end
      }

      break if ready      
    }

    Djinn.log_debug("ACC: Node at #{@ip} is now #{new_roles}")
    return
  end
end
