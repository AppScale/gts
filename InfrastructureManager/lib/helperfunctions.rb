#!/usr/bin/ruby -w


# Imports within Ruby's standard libraries
require 'base64'
require 'digest/sha1'
require 'fileutils'
require 'openssl'
require 'socket'
require 'timeout'


# BadConfigurationExceptions represent an exception that can be thrown by the
# AppController or any other library it uses, if a method receives inputs
# it isn't expecting.
class BadConfigurationException < Exception
end


# HelperFunctions holds miscellaneous functions - functions that really aren't
# bound to a particular service, but are reused across multiple functions.
module HelperFunctions


  # The maximum amount of time, in seconds, that we are willing to wait for
  # a virtual machine to start up, from the initial run-instances request.
  # Setting this value is a bit of an art, but we choose the value below
  # because our image is roughly 10GB in size, and if Eucalyptus doesn't
  # have the image cached, it could take half an hour to get our image
  # started.
  MAX_VM_CREATION_TIME = 1800


  # The amount of time that spawn_vms waits between each describe-instances
  # request. Setting this value too low can cause Eucalyptus to interpret
  # requests as replay attacks.
  SLEEP_TIME = 20


  # A regular expression that matches IP addresses, used to parse output
  # from describe-instances to see the IPs for machines currently running.
  IP_REGEX = /\d+\.\d+\.\d+\.\d+/


  # A regular expression that matches fully qualified domain names, used to 
  # parse output from describe-instances to see the FQDNs for machines 
  # currently running.
  FQDN_REGEX = /[\w\d\.\-]+/


  # A regular expression that matches IPs or FQDNs.
  # TODO(cgb): The FQDN_REGEX seems general enough to match all of these -
  # replace this and IP_REGEX with FQDN_REGEX?
  IP_OR_FQDN = /#{IP_REGEX}|#{FQDN_REGEX}/


  # A constant that indicates that SSL should be used when checking if a given
  # port is open.
  USE_SSL = true


  # A constant that indicates that SSL should not be used when checking if a
  # given port is open.
  DONT_USE_SSL = false


  # Logs and executes a shell command - useful for mocking since flexmock can't
  # mock out the backticks method (Kernel:`), but it can mock out this method.
  def self.shell(cmd)
    Kernel.puts(cmd)
    return `#{cmd}`
  end

  # A convenience method that can be used to write a String to a file, creating
  # that file if it does not exist.
  def self.write_file(location, contents)
    File.open(location, "w+") { |file| file.write(contents) }
  end


  # A convenience method that can be used to read a file and return its
  # contents as a String.
  def self.read_file(location, chomp=true)
    file = File.open(location) { |f| f.read }
    if chomp
      return file.chomp
    else
      return file
    end
  end

  
  # Returns a random string composed of alphanumeric characters, as long
  # as the user requests.
  def self.get_random_alphanumeric(length=10)
    random = ""
    possible = "0123456789abcdefghijklmnopqrstuvxwyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    possible_length = possible.length
     
    length.times { |index|
      random << possible[Kernel.rand(possible_length)]
    }
     
    return random
  end


  # Reads the given file and parses the X509 certificate data it contains.
  def self.get_cert(filename)
    return nil unless File.exists?(filename)
    OpenSSL::X509::Certificate.new(File.open(filename) { |f|
      f.read
    })
  end
  
  
  # Reads the given file and parses the SSL private key data that it contains.
  def self.get_key(filename)
    return nil unless File.exists?(filename)
    OpenSSL::PKey::RSA.new(File.open(filename) { |f|
      f.read
    })
  end
  

  # Reads a file that contains the AppScale shared secret (a password that is
  # used to authenticate remote calls/callers), returning the secret that
  # file contains.
  def self.get_secret(filename="/etc/appscale/secret.key")
    return self.read_file(File.expand_path(filename), chomp=true)
  end
  

  # In cloudy deployments, the recommended way to determine a machine's true
  # private IP address from its private FQDN is to use dig. This method
  # attempts to resolve IPs in that method, deferring to other methods if that
  # fails.
  def self.convert_fqdn_to_ip(host)
    return host if host =~ /#{IP_REGEX}/
  
    ip = self.shell("dig #{host} +short").chomp
    if ip.empty?
      Kernel.puts("couldn't use dig to resolve [#{host}]")
      abort("Couldn't convert #{host} to an IP address. Result of dig was \n#{ip}")
    end

    return ip
  end


  # Given an array containing public and private IPs, separates them into
  # one public IP array and a private IP array. Any private IPs are then
  # checked to see if they resolve properly (which may fail in hybrid cloud
  # deployments), and any private IPs that do not resolve are replaced with
  # their public IP equivalents.
  def self.get_ips(ips)
    abort("ips not even length array") if ips.length % 2 != 0
    reported_public = []
    reported_private = []
    ips.each_index { |index|
      if index % 2 == 0
        reported_public << ips[index]
      else
        reported_private << ips[index]
      end
    }
    
    Kernel.puts("Reported Public IPs: [#{reported_public.join(', ')}]")
    Kernel.puts("Reported Private IPs: [#{reported_private.join(', ')}]")

    actual_public = []
    actual_private = []
    
    reported_public.each_index { |index|
      pub = reported_public[index]
      pri = reported_private[index]
      if pub != "0.0.0.0" and pri != "0.0.0.0"
        actual_public << pub
        actual_private << pri
      end
    }
        
    actual_private.each_index { |index|
      begin
        actual_private[index] = HelperFunctions.convert_fqdn_to_ip(actual_private[index])
      rescue Exception
        # this can happen if the private ip doesn't resolve
        # which can happen in hybrid environments: euca boxes wont be 
        # able to resolve ec2 private ips, and vice-versa in euca-managed-mode
        Kernel.puts("rescued! failed to convert #{actual_private[index]} to public")
        actual_private[index] = actual_public[index]
      end
    }
    
    return actual_public, actual_private
  end


  # Similar to get_ips, but does not attempt to resolve the private IPs seen.
  # Returns a single array with the public IPs from the original array
  # (which contains both public and private IPs).
  def self.get_public_ips(ips)
    abort("ips not even length array") if ips.length % 2 != 0
    reported_public = []
    reported_private = []
    ips.each_index { |index|
      if index % 2 == 0
        reported_public << ips[index]
      else
        reported_private << ips[index]
      end
    }
    
    Kernel.puts("Reported Public IPs: [#{reported_public.join(', ')}]")
    Kernel.puts("Reported Private IPs: [#{reported_private.join(', ')}]")
    
    public_ips = []
    reported_public.each_index { |index|
      if reported_public[index] != "0.0.0.0"
        public_ips << reported_public[index]
      elsif reported_private[index] != "0.0.0.0"
        public_ips << reported_private[index]
      end
    }
    
    return public_ips.flatten
  end

  
  # Queries Amazon EC2's Spot Instance pricing history to see how much other
  # users have paid for the given instance type (assumed to be a Linux box),
  # so that we can place a bid that is similar to the average price. How
  # similar to the average price to pay is a bit of an open problem - for now,
  # we pay 20% more so that in case the market price goes up a little bit, we
  # still get to keep our instances.
  def self.get_optimal_spot_price(instance_type)
    command = "ec2-describe-spot-price-history -t #{instance_type} | " +
      "grep 'Linux/UNIX' | awk '{print $2}'".split("\n")
    prices = self.shell("#{command}")

    average = prices.reduce(0.0) { |sum, price|
      sum += Float(price)
    }
    
    average /= prices.length
    plus_twenty = average * 1.20
    
    Kernel.puts("The average spot instance price for a #{instance_type} " +
      "machine is $#{average}, and 20% more is $#{plus_twenty}")
    return plus_twenty
  end


  # Given a Hash of EC2 credentials, sets them as environment variables in the
  # current environment. This avoids having to specify them as command-line
  # arguments once we attempt to run any EC2 command-line tools.
  def self.set_creds_in_env(creds, cloud_num)
    ENV['EC2_JVM_ARGS'] = nil

    creds.each_pair { |k, v|
      Kernel.puts("Setting #{k} to #{v} in our environment.")
      ENV[k] = v
    }

    # note that key and cert vars are set wrong - they refer to
    # the location on the user's machine where the key is
    # thus, let's fix that

    cloud_keys_dir = File.expand_path("/etc/appscale/keys/cloud#{cloud_num}")
    ENV['EC2_PRIVATE_KEY'] = "#{cloud_keys_dir}/mykey.pem"
    ENV['EC2_CERT'] = "#{cloud_keys_dir}/mycert.pem"

    Kernel.puts("Setting private key to #{cloud_keys_dir}/mykey.pem, cert to #{cloud_keys_dir}/mycert.pem")
  end


  # This method spawns virtual machines in a supported cloud infrastructure.
  # It dispatches the initial request for machines, waits for them to start,
  # and returns the public IPs, private IPs, and instance IDs of the machines
  # that were started.
  def self.spawn_vms(parameters)
    num_of_vms_to_spawn = Integer(parameters['num_vms'])
    image_id = parameters['image_id']
    instance_type = parameters['instance_type']
    keyname = parameters['keyname']
    infrastructure = parameters['infrastructure']
    cloud = parameters['cloud']
    group = parameters['group']
    spot = false
    Kernel.puts("[#{num_of_vms_to_spawn}] [#{image_id}]  [#{instance_type}] [#{keyname}] [#{infrastructure}] [#{cloud}] [#{group}] [#{spot}]")

    start_time = Time.now

    public_ips = []
    private_ips = []
    instance_ids = []

    if num_of_vms_to_spawn < 1
      return public_ips, private_ips, instance_ids
    end

    ssh_key = File.expand_path("/etc/appscale/keys/#{cloud}/#{keyname}.key")
    Kernel.puts("About to spawn VMs, expecting to find a key at #{ssh_key}")

    self.log_obscured_env

    new_cloud = !File.exists?(ssh_key)
    if new_cloud # need to create security group and key
      Kernel.puts("Creating keys/security group for #{cloud}")
      self.generate_ssh_key(ssh_key, keyname, infrastructure)
      self.create_appscale_security_group(infrastructure, group)
    else
      Kernel.puts("Not creating keys/security group for #{cloud}")
    end

    instance_ids_up = []
    public_up_already = []
    private_up_already = []
    Kernel.puts("EC2_URL = [#{ENV['EC2_URL']}]")
    loop { # need to make sure ec2 doesn't return an error message here
      describe_instances = self.shell("#{infrastructure}-describe-instances 2>&1")
      Kernel.puts("describe-instances says [#{describe_instances}]")
      all_ip_addrs = describe_instances.scan(/\s+(#{IP_OR_FQDN})\s+(#{IP_OR_FQDN})\s+running\s+#{keyname}\s/).flatten
      instance_ids_up = describe_instances.scan(/INSTANCE\s+(i-\w+)/).flatten
      public_up_already, private_up_already = HelperFunctions.get_ips(all_ip_addrs)
      vms_up_already = describe_instances.scan(/(#{IP_OR_FQDN})\s+running\s+#{keyname}\s+/).length
      break if vms_up_already > 0 or new_cloud # crucial for hybrid cloud, where one box may not be running yet
    }
 
    args = "-k #{keyname} -n #{num_of_vms_to_spawn} --instance-type #{instance_type} --group #{group} #{image_id}"
    if spot
      price = HelperFunctions.get_optimal_spot_price(instance_type)
      command_to_run = "ec2-request-spot-instances -p #{price} #{args}"
    else
      command_to_run = "#{infrastructure}-run-instances #{args}"
    end

    loop {
      Kernel.puts(command_to_run)
      run_instances = self.shell("#{command_to_run} 2>&1")
      Kernel.puts("run_instances says [#{run_instances}]")
      if run_instances =~ /Please try again later./
        Kernel.puts("Error with run_instances: #{run_instances}. Will try again in a moment.")
      elsif run_instances =~ /try --addressing private/
        Kernel.puts("Need to retry with addressing private. Will try again in a moment.")
        command_to_run << " --addressing private"
      elsif run_instances =~ /PROBLEM/
        Kernel.puts("Error: #{run_instances}")
        abort("Saw the following error message from EC2 tools. Please resolve the issue and try again:\n#{run_instances}")
      else
        Kernel.puts("Run instances message sent successfully. Waiting for the image to start up.")
        break
      end
      Kernel.puts("sleepy time")
      Kernel.sleep(5)
    }
    
    instance_ids = []
    public_ips = []
    private_ips = []

    Kernel.sleep(10) # euca 2.0.3 can throw forbidden errors if we hit it too fast
    # TODO: refactor me to use rightaws gem, check for forbidden, and retry accordingly

    end_time = Time.now + MAX_VM_CREATION_TIME
    while (now = Time.now) < end_time
      describe_instances = self.shell("#{infrastructure}-describe-instances 2>&1")
      Kernel.puts("[#{Time.now}] #{end_time - now} seconds left...")
      Kernel.puts(describe_instances)
 
      # TODO: match on instance id
      #if describe_instances =~ /terminated\s+#{keyname}\s+/
      #  terminated_message = "An instance was unexpectedly terminated. " +
      #    "Please contact your cloud administrator to determine why " +
      #    "and try again. \n#{describe_instances}"
      #  Kernel.puts(terminated_message)
      #  abort(terminated_message)
      #end
      
      # changed regexes so ensure we are only checking for instances created
      # for appscale only (don't worry about other instances created)
      
      all_ip_addrs = describe_instances.scan(/\s+(#{IP_OR_FQDN})\s+(#{IP_OR_FQDN})\s+running\s+#{keyname}\s+/).flatten
      public_ips, private_ips = HelperFunctions.get_ips(all_ip_addrs)
      public_ips = public_ips - public_up_already
      private_ips = private_ips - private_up_already
      instance_ids = describe_instances.scan(/INSTANCE\s+(i-\w+)\s+[\w\-\s\.]+#{keyname}/).flatten - instance_ids_up
      break if public_ips.length == num_of_vms_to_spawn
      Kernel.sleep(SLEEP_TIME)
    end
    
    if public_ips.length.zero?
      abort("No public IPs were able to be procured within the time limit.")
    end
    
    if public_ips.length != num_of_vms_to_spawn
      potential_dead_ips = HelperFunctions.get_ips(all_ip_addrs) - public_up_already
      potential_dead_ips.each_index { |index|
        if potential_dead_ips[index] == "0.0.0.0"
          instance_to_term = instance_ids[index]
          Kernel.puts("Instance #{instance_to_term} failed to get a public IP address and is being terminated.")
          self.shell("#{infrastructure}-terminate-instances #{instance_to_term}")
        end
      }
    end         
    
    end_time = Time.now
    total_time = end_time - start_time

    if spot
      Kernel.puts("TIMING: It took #{total_time} seconds to spawn " +
        "#{num_of_vms_to_spawn} spot instances")
    else
      Kernel.puts("TIMING: It took #{total_time} seconds to spawn " +
        "#{num_of_vms_to_spawn} regular instances")
    end

    return public_ips, private_ips, instance_ids
  end


  # Generates a new SSH key for use with the given cloud infrastructure. If
  # the keyname was already in the system, this method removes it and adds a
  # new one.
  def self.generate_ssh_key(outputLocation, name, infrastructure)
    ec2_output = ""
    loop {
      ec2_output = self.shell("#{infrastructure}-add-keypair #{name} 2>&1")
      break if ec2_output.include?("BEGIN RSA PRIVATE KEY")
      Kernel.puts("Trying again. Saw this from #{infrastructure}-add-keypair: #{ec2_output}")
      self.shell("#{infrastructure}-delete-keypair #{name} 2>&1")
    }

    # output is the ssh private key prepended with info we don't need
    # delimited by the first \n, so rip it off first to get just the key

    if outputLocation.class == String
      outputLocation = [outputLocation]
    end

    outputLocation.each { |path|
      fullPath = File.expand_path(path)
      File.open(fullPath, "w") { |file|
        file.puts(ec2_output)
      }
      FileUtils.chmod(0600, fullPath) # else ssh won't use the key
    }

    return
  end


  # Creates a new security group in the given cloud infrastructure and opens
  # all the TCP, UDP, and ICMP ports within it. We open the ports under the
  # presumption that the AppScale firewall rules will be applied to iptables
  # to lock back down any ports that need not be open to the world.
  def self.create_appscale_security_group(infrastructure, group)
    self.shell("#{infrastructure}-add-group #{group} -d appscale 2>&1")
    self.shell("#{infrastructure}-authorize #{group} -p 1-65535 -P udp 2>&1")
    self.shell("#{infrastructure}-authorize #{group} -p 1-65535 -P tcp 2>&1")
    self.shell("#{infrastructure}-authorize #{group} -s 0.0.0.0/0 -P icmp -t -1:-1 2>&1")
  end


  # Given a list of instance ids, terminates them in the given cloud
  # infrastructure.
  def self.terminate_vms(ids, infrastructure)
    self.shell("#{infrastructure}-terminate-instances #{ids.join(' ')} 2>&1")
  end


  # Obscures out sensitive strings by replacing most of the characters with
  # a dummy character. Callers can use this method to print out credentials
  # that may be logged and thus sent over e-mail (and thus should not be
  # completely exposed in cleartext).
  def self.obscure_string(string)
    return string if string.nil? or string.length < 4
    last_four = string[string.length-4, string.length]
    obscured = "*" * (string.length-4)
    return obscured + last_four
  end


  # Prints out a list of environment variables currently set in this process'
  # runtime and their values. For any EC2 user credentials, we obscure out
  # any sensitive information.
  def self.log_obscured_env()
    env = self.shell("env")
  
    ["EC2_ACCESS_KEY", "EC2_SECRET_KEY"].each { |cred|
      if env =~ /#{cred}=(.*)/
        env.gsub!(/#{cred}=(.*)/, "#{cred}=#{self.obscure_string($1)}")
      end
    }
 
    Kernel.puts(env)
  end


end
