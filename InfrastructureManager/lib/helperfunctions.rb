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


  SLEEP_TIME = 20


  IP_REGEX = /\d+\.\d+\.\d+\.\d+/


  FQDN_REGEX = /[\w\d\.\-]+/


  IP_OR_FQDN = /#{IP_REGEX}|#{FQDN_REGEX}/


  DELTA_REGEX = /([1-9][0-9]*)([DdHhMm]|[sS]?)/


  TIME_IN_SECONDS = { "d" => 86400, "h" => 3600, "m" => 60, "s" => 1 }


  CLOUDY_CREDS = ["EC2_ACCESS_KEY", "EC2_SECRET_KEY", "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY"]


  # A constant that indicates that SSL should be used when checking if a given
  # port is open.
  USE_SSL = true


  # A constant that indicates that SSL should not be used when checking if a
  # given port is open.
  DONT_USE_SSL = false


  def self.shell(cmd)
    Kernel.puts(cmd)
    return `#{cmd}`
  end

  def self.write_file(location, contents)
    File.open(location, "w+") { |file| file.write(contents) }
  end


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
    possibleLength = possible.length
     
    length.times { |index|
      random << possible[Kernel.rand(possibleLength)]
    }
     
    return random
  end

  def self.get_cert(filename)
    return nil unless File.exists?(filename)
    OpenSSL::X509::Certificate.new(File.open(filename) { |f|
      f.read
    })
  end
  
  def self.get_key(filename)
    return nil unless File.exists?(filename)
    OpenSSL::PKey::RSA.new(File.open(filename) { |f|
      f.read
    })
  end
  
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
        
    #actual_public.each_index { |index|
    #  actual_public[index] = HelperFunctions.convert_fqdn_to_ip(actual_public[index])
    #}

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


  def self.set_creds_in_env(creds, cloud_num)
    ENV['EC2_JVM_ARGS'] = nil

    creds.each_pair { |k, v|
      next unless k =~ /\ACLOUD#{cloud_num}/
      env_key = k.scan(/\ACLOUD#{cloud_num}_(.*)\Z/).flatten.to_s
      ENV[env_key] = v
    }

    # note that key and cert vars are set wrong - they refer to
    # the location on the user's machine where the key is
    # thus, let's fix that

    cloud_keys_dir = File.expand_path("/etc/appscale/keys/cloud#{cloud_num}")
    ENV['EC2_PRIVATE_KEY'] = "#{cloud_keys_dir}/mykey.pem"
    ENV['EC2_CERT'] = "#{cloud_keys_dir}/mycert.pem"

    Kernel.puts("Setting private key to #{cloud_keys_dir}/mykey.pem, cert to #{cloud_keys_dir}/mycert.pem")
  end

  def self.spawn_hybrid_vms(creds, nodes)
    info = "Spawning hybrid vms with creds #{self.obscure_creds(creds).inspect} and nodes #{nodes.inspect}"
    Kernel.puts(info)

    cloud_info = []

    cloud_num = 1
    loop {
      cloud_type = creds["CLOUD#{cloud_num}_TYPE"]
      break if cloud_type.nil?

      self.set_creds_in_env(creds, cloud_num)

      if cloud_type == "euca"
        machine = creds["CLOUD#{cloud_num}_EMI"]
      elsif cloud_type == "ec2"
        machine = creds["CLOUD#{cloud_num}_AMI"]
      else
        abort("cloud type was #{cloud_type}, which is not a supported value.")
      end

      num_of_vms = 0
      jobs_needed = []
      nodes.each_pair { |k, v|
        if k =~ /\Acloud#{cloud_num}-\d+\Z/
          num_of_vms += 1
          jobs_needed << v
        end
      }

      instance_type = "m1.large"
      keyname = creds["keyname"]
      cloud = "cloud#{cloud_num}"
      group = creds["group"]

      this_cloud_info = self.spawn_vms(num_of_vms, jobs_needed, machine, 
        instance_type, keyname, cloud_type, cloud, group)

      Kernel.puts("Cloud#{cloud_num} reports the following info: #{this_cloud_info.join(', ')}")

      cloud_info += this_cloud_info
      cloud_num += 1
    }

    Kernel.puts("Hybrid cloud spawning reports the following info: #{cloud_info.join(', ')}")

    return cloud_info
  end

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

  def self.create_appscale_security_group(infrastructure, group)
    self.shell("#{infrastructure}-add-group #{group} -d appscale 2>&1")
    self.shell("#{infrastructure}-authorize #{group} -p 1-65535 -P udp 2>&1")
    self.shell("#{infrastructure}-authorize #{group} -p 1-65535 -P tcp 2>&1")
    self.shell("#{infrastructure}-authorize #{group} -s 0.0.0.0/0 -P icmp -t -1:-1 2>&1")
  end

  def self.terminate_vms(nodes, infrastructure)
    instances = []
    nodes.each { |node|
      instance_id = node.instance_id
      instances << instance_id
    }
    
    self.shell("#{infrastructure}-terminate-instances #{instances.join(' ')}")
  end

  def self.terminate_hybrid_vms(creds)
    # TODO: kill my own cloud last
    # otherwise could orphan other clouds

    cloud_num = 1
    loop {
      key = "CLOUD#{cloud_num}_TYPE"
      cloud_type = creds[key]
      break if cloud_type.nil?

      self.set_creds_in_env(creds, cloud_num)

      keyname = creds["keyname"]
      Kernel.puts("Killing Cloud#{cloud_num}'s machines, of type #{cloud_type} and with keyname #{keyname}")
      self.terminate_all_vms(cloud_type, keyname)

      cloud_num += 1
    }

  end
  
  def self.terminate_all_vms(infrastructure, keyname)
    self.log_obscured_env
    desc_instances = self.shell("#{infrastructure}-describe-instances")
    instances = desc_instances.scan(/INSTANCE\s+(i-\w+)\s+[\w\-\s\.]+#{keyname}/).flatten
    self.shell("#{infrastructure}-terminate-instances #{instances.join(' ')}")
  end

  def self.get_hybrid_ips(creds)
    Kernel.puts("creds are #{self.obscure_creds(creds).inspect}")

    public_ips = []
    private_ips = []

    keyname = creds["keyname"]

    cloud_num = 1
    loop {
      key = "CLOUD#{cloud_num}_TYPE"
      cloud_type = creds[key]
      break if cloud_type.nil?

      self.set_creds_in_env(creds, cloud_num)

      this_pub, this_priv = self.get_cloud_ips(cloud_type, keyname)
      Kernel.puts("CLOUD#{cloud_num} reports public ips [#{this_pub.join(', ')}] and private ips [#{this_priv.join(', ')}]")
      public_ips = public_ips + this_pub
      private_ips = private_ips + this_priv

      cloud_num += 1
    }

    Kernel.puts("all public ips are [#{public_ips.join(', ')}] and private ips [#{private_ips.join(', ')}]")
    return public_ips, private_ips
  end

  def self.get_cloud_ips(infrastructure, keyname)
    self.log_obscured_env

    describe_instances = ""
    loop {
      describe_instances = self.shell("#{infrastructure}-describe-instances 2>&1")
      Kernel.puts("[oi!] #{describe_instances}")
      break unless describe_instances =~ /Message replay detected./
      Kernel.sleep(10)
    }

    running_machine_regex = /\s+(#{IP_OR_FQDN})\s+(#{IP_OR_FQDN})\s+running\s+#{keyname}\s/
    all_ip_addrs = describe_instances.scan(running_machine_regex).flatten
    Kernel.puts("[oi!] all ips are [#{all_ip_addrs.join(', ')}]")
    public_ips, private_ips = HelperFunctions.get_ips(all_ip_addrs)
    return public_ips, private_ips
  end
    

  def self.get_random_alphanumeric(length=10)
    random = ""
    possible = "0123456789abcdefghijklmnopqrstuvxwyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    possibleLength = possible.length

    length.times { |index|
      random << possible[Kernel.rand(possibleLength)]
    }

    random
  end


  def self.obscure_string(string)
    return string if string.nil? or string.length < 4
    last_four = string[string.length-4, string.length]
    obscured = "*" * (string.length-4)
    return obscured + last_four
  end

  def self.obscure_creds(creds)
    obscured = {}
    creds.each { |k, v|
      if CLOUDY_CREDS.include?(k)
        obscured[k] = self.obscure_string(v)
      else
        obscured[k] = v
      end
    }

    return obscured
  end


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
