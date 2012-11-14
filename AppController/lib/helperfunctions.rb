#!/usr/bin/ruby -w


# Imports within Ruby's standard libraries
require 'base64'
require 'digest/sha1'
require 'fileutils'
require 'openssl'
require 'socket'
require 'timeout'


# Imports for AppController libraries
$:.unshift File.join(File.dirname(__FILE__))
require 'user_app_client'


# BadConfigurationExceptions represent an exception that can be thrown by the
# AppController or any other library it uses, if a method receives inputs
# it isn't expecting.
class BadConfigurationException < Exception
end


# HelperFunctions holds miscellaneous functions - functions that really aren't
# bound to a particular service, but are reused across multiple functions.
# TODO(cgb): Consider removing App Engine-related functions below into its
# own helper class
module HelperFunctions


  VER_NUM = "1.6.3"

  
  APPSCALE_HOME = ENV['APPSCALE_HOME']


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


  DEFAULT_SKIP_FILES_REGEX = /^(.*\/)?((app\.yaml)|(app\.yml)|(index\.yaml)|(index\.yml)|(\#.*\#)|(.*~)|(.*\.py[co])|(.*\/RCS\/.*)|(\..*)|)$/


  TIME_IN_SECONDS = { "d" => 86400, "h" => 3600, "m" => 60, "s" => 1 }


  CLOUDY_CREDS = ["EC2_ACCESS_KEY", "EC2_SECRET_KEY", "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY"]


  # The first port that should be used to host Google App Engine applications
  # that users have uploaded.
  APP_START_PORT = 20000


  # A constant that indicates that SSL should be used when checking if a given
  # port is open.
  USE_SSL = true


  # A constant that indicates that SSL should not be used when checking if a
  # given port is open.
  DONT_USE_SSL = false


  def self.shell(cmd)
    return `#{cmd}`
  end


  def self.write_file(location, contents)
    File.open(location, "w+") { |file| file.write(contents) }
  end


  def self.write_json_file(location, contents)
    self.write_file(location, JSON.dump(contents))
  end


  def self.read_file(location, chomp=true)
    file = File.open(location) { |f| f.read }
    if chomp
      return file.chomp
    else
      return file
    end
  end

  
  # Reads the given file, which is assumed to be a JSON-loadable object,
  # and returns that JSON back to the caller.
  def self.read_json_file(location)
    data = self.read_file(location)
    return JSON.load(data)
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


  def self.deserialize_info_from_tools(ips) 
    nodes = {}
    # FIXME: Here we make the string back into a hash using the crappy deserialization
    # Definitely change this to JSON at some point
    ips.split("..").each do |node|
      tokens = node.split("--")
      next if tokens.length != 2
      id,roles = tokens
      nodes[id] = roles
    end
    return nodes
  end


  def self.kill_process(name)
    `ps ax | grep #{name} | grep -v grep | awk '{ print $1 }' | xargs -d '\n' kill -9`
  end


  def self.sleep_until_port_is_open(ip, port, use_ssl=DONT_USE_SSL)
    sleep_time = 1

    loop {
      return if HelperFunctions.is_port_open?(ip, port, use_ssl)

      Kernel.sleep(sleep_time)
      if sleep_time < 30
        sleep_time *= 2
      end

      Kernel.puts("Waiting on #{ip}:#{port} to be open (currently closed).")
    }
  end


  def self.sleep_until_port_is_closed(ip, port, use_ssl=DONT_USE_SSL)
    sleep_time = 1

    loop {
      return unless HelperFunctions.is_port_open?(ip, port, use_ssl)

      Kernel.sleep(sleep_time)
      if sleep_time < 30
        sleep_time *= 2
      end

      Kernel.puts("Waiting on #{ip}:#{port} to be closed (currently open).")
    }
  end


  def self.is_port_open?(ip, port, use_ssl=DONT_USE_SSL)
    begin
      Timeout::timeout(1) do
        begin
          sock = TCPSocket.new(ip, port)
          if use_ssl
            ssl_context = OpenSSL::SSL::SSLContext.new() 
            unless ssl_context.verify_mode 
              ssl_context.verify_mode = OpenSSL::SSL::VERIFY_NONE 
            end 
            sslsocket = OpenSSL::SSL::SSLSocket.new(sock, ssl_context) 
            sslsocket.sync_close = true 
            sslsocket.connect          
          end
          sock.close
          return true
        rescue Errno::ECONNREFUSED, Errno::EHOSTUNREACH, Errno::ECONNRESET
          return false
        end
      end
    rescue Timeout::Error
    end
  
    return false
  end


  def self.run_remote_command(ip, command, public_key_loc, want_output)
    Kernel.puts("ip is [#{ip}], command is [#{command}], public key is [#{public_key_loc}], want output? [#{want_output}]")
    public_key_loc = File.expand_path(public_key_loc)
    
    remote_cmd = "ssh -i #{public_key_loc} -o StrictHostkeyChecking=no root@#{ip} '#{command} "
    
    output_file = "/tmp/#{ip}.log"
    if want_output
      remote_cmd << "2>&1 > #{output_file} &' &"
    else
      remote_cmd << "> /dev/null &' &"
    end

    Kernel.puts("Running [#{remote_cmd}]")

    if want_output
      return `#{remote_cmd}`
    else
      Kernel.system remote_cmd
      return remote_cmd
    end
  end

  def self.scp_file(local_file_loc, remote_file_loc, target_ip, private_key_loc)
    private_key_loc = File.expand_path(private_key_loc)
    `chmod 0600 #{private_key_loc}`
    local_file_loc = File.expand_path(local_file_loc)
    retval_file = "/etc/appscale/retval-#{Kernel.rand()}"
    cmd = "scp -i #{private_key_loc} -o StrictHostkeyChecking=no 2>&1 #{local_file_loc} root@#{target_ip}:#{remote_file_loc}; echo $? > #{retval_file}"
    #Kernel.puts(cmd)
    scp_result = `#{cmd}`

    loop {
      break if File.exists?(retval_file)
      sleep(5)
    }

    retval = (File.open(retval_file) { |f| f.read }).chomp

    fails = 0
    loop {
      break if retval == "0"
      Kernel.puts("\n\n[#{cmd}] returned #{retval} instead of 0 as expected. Will try to copy again momentarily...")
      fails += 1
      abort("SCP failed") if fails >= 5
      sleep(2)
      `#{cmd}`
      retval = (File.open(retval_file) { |f| f.read }).chomp
    }

    #Kernel.puts(scp_result)
    `rm -fv #{retval_file}`
  end

  def self.get_remote_appscale_home(ip, key)
    cat = "cat /etc/appscale/home"
    remote_cmd = "ssh -i #{key} -o NumberOfPasswordPrompts=0 -o StrictHostkeyChecking=no 2>&1 root@#{ip} '#{cat}'"
    possible_home = `#{remote_cmd}`.chomp
    if possible_home.nil? or possible_home.empty?
      return "/root/appscale/"
    else
      return possible_home
    end
  end 

  def self.get_appscale_id
    # This needs to be ec2 or euca 2ools.
    image_info = `ec2-describe-images`
    
    abort("ec2 tools can't find appscale image") unless image_info.include?("appscale")
    image_id = image_info.scan(/([a|e]mi-[0-9a-zA-Z]+)\sappscale/).flatten.to_s
    
    return image_id
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
  
  def self.setup_app(app_name, untar=true)
    meta_dir = "/var/apps/#{app_name}"
    tar_dir = "#{meta_dir}/app/"
    tar_path = "#{tar_dir}#{app_name}.tar.gz"
    #Kernel.system "rm -rf #{tar_dir}"

    self.shell("mkdir -p #{tar_dir}")
    self.shell("mkdir -p #{meta_dir}/log")
    self.shell("cp #{APPSCALE_HOME}/AppLoadBalancer/public/404.html #{meta_dir}")
    self.shell("touch #{meta_dir}/log/server.log")
    #tar_file = File.open(tar_path, "w")
    #decoded_tar = Base64.decode64(encoded_app_tar)
    #tar_file.write(decoded_tar)
    #tar_file.close
    self.shell("tar --file #{tar_path} --force-local -C #{tar_dir} -zx") if untar
  end

  # Returns pid if successful, -1 if not
  def self.run_app(app_name, port, db_location, public_ip, private_ip, app_version, app_language, nginx_port, xmpp_ip)
    secret = HelperFunctions.get_secret    

    start_cmd = ""
    stop_cmd = ""
    env_vars = {}
    
    if app_language == "python"
      if File.exist?("/var/apps/#{app_name}/app/app.yaml") == false
        Kernel.puts("The #{app_name} application was missing a app.yaml")
        return -1 
      end
      
      Kernel.puts("saw a python app coming through")
      env_vars['MY_IP_ADDRESS'] = public_ip
      env_vars['MY_PORT'] = port
      env_vars['APPNAME'] = app_name
      env_vars['GOMAXPROCS'] = self.get_num_cpus()

      start_cmd = [ "python2.5 ",
             "#{APPSCALE_HOME}/AppServer/dev_appserver.py",
             "-p #{port}",
             "--cookie_secret #{secret}",
             "--login_server #{public_ip}",
             "--admin_console_server ''",
             "--nginx_port #{nginx_port}",
             "--nginx_host #{public_ip}",
             "--require_indexes",
             "--enable_sendmail",
             "--xmpp_path #{xmpp_ip}",
             "--uaserver_path #{db_location}:#{UserAppClient::SERVER_PORT}",
             "--datastore_path #{db_location}:#{PbServer::LISTEN_PORT_NO_SSL}",
             "--history_path /var/apps/#{app_name}/data/app.datastore.history",
             "/var/apps/#{app_name}/app",
             "-a #{private_ip}",
             #">> /var/apps/#{app_name}/log/server.log 2>&1 &"
             ].join(' ')
      stop_cmd = "ps ax | grep #{start_cmd} | grep -v grep | awk '{ print $1 }' | xargs -d '\n' kill -9"
    elsif app_language == "java"
      if File.exist?("/var/apps/#{app_name}/app/war/WEB-INF/web.xml") == false and File.exist?("/var/apps/#{app_name}/app/app.yaml") == false
        Kernel.puts("The #{app_name} application was missing a web.xml or app.yaml file")
        return -1
      end

      Kernel.puts("saw a java app coming through")
      `cp #{APPSCALE_HOME}/AppServer_Java/appengine-java-sdk-repacked/lib/user/*.jar /var/apps/#{app_name}/app/war/WEB-INF/lib/`
      `cp #{APPSCALE_HOME}/AppServer_Java/appengine-java-sdk-repacked/lib/user/orm/*.jar /var/apps/#{app_name}/app/war/WEB-INF/lib/`
      start_cmd = ["cd #{APPSCALE_HOME}/AppServer_Java &&",
             "./genKeystore.sh &&",
             "./appengine-java-sdk-repacked/bin/dev_appserver.sh",
             "--port=#{port}",
             "--address=#{private_ip}",
             "--datastore_path=#{db_location}",
             "--cookie_secret=#{secret}",
             "--login_server=#{public_ip}",
             "--appscale_version=#{app_version}",
	     "--NGINX_ADDRESS=#{public_ip}",
             "--NGINX_PORT=#{nginx_port}",
             "/var/apps/#{app_name}/app/war/",
             #">> /var/apps/#{app_name}/log/server.log 2>&1 &"
             ].join(' ')
      stop_cmd = "ps ax | grep #{start_cmd} | grep -v grep | awk '{ print $1 }' | xargs -d '\n' kill -9"
    else
      Kernel.puts("Currently we only support python, go, and java applications, not #{app_language}.")
    end

    env_vars['APPSCALE_HOME'] = APPSCALE_HOME

    GodInterface.start(app_name, start_cmd, stop_cmd, port, env_vars)
    HelperFunctions.sleep_until_port_is_open(HelperFunctions.local_ip, port)

    pid = `lsof -t -i :#{port}`
    Kernel.puts("Started app #{app_name} with pid #{pid}")
    
    return pid
  end


  # Instructs god to terminate and stop watching an App Engine application, 
  # identified by its name and the port that it runs on.
  def self.stop_app(app_name, port)
    watch = "appscale-" + app_name + "-" + port.to_s
    GodInterface.stop(watch)
    Kernel.puts("Stopped #{watch} process via god.")
    GodInterface.remove(watch)
    Kernel.puts("Stopped watching #{watch} via god.")
  end


  def self.local_ip()
    ifconfig = HelperFunctions.shell("ifconfig")
    bound_addrs = ifconfig.scan(/inet addr:(\d+.\d+.\d+.\d+)/).flatten

    Kernel.puts("ifconfig reports bound IP addresses as " +
      "[#{bound_addrs.join(', ')}]")
    bound_addrs.each { |addr|
      if addr == "127.0.0.1"
        next
      end

      Kernel.puts("Returning #{addr} as our local IP address")
      return addr
    }

    raise Exception.new("Couldn't get our local IP address")
  end

  # In cloudy deployments, the recommended way to determine a machine's true
  # private IP address from its private FQDN is to use dig. This method
  # attempts to resolve IPs in that method, deferring to other methods if that
  # fails.
  def self.convert_fqdn_to_ip(host)
    return host if host =~ /#{IP_REGEX}/
  
    ip = `dig #{host} +short`.chomp
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
    prices = `#{command}`

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
      next unless k =~ /\ACLOUD/
      env_key = k.scan(/\ACLOUD_(.*)\Z/).flatten.to_s
      ENV[env_key] = v
    }

    # note that key and cert vars are set wrong - they refer to
    # the location on the user's machine where the key is
    # thus, let's fix that

    cloud_keys_dir = File.expand_path("#{APPSCALE_HOME}/.appscale/keys/cloud#{cloud_num}")
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

  def self.spawn_vms(num_of_vms_to_spawn, job, image_id, instance_type, keyname,
    infrastructure, cloud, group, spot=false)

    start_time = Time.now

    return [] if num_of_vms_to_spawn < 1

    ssh_key = File.expand_path("#{APPSCALE_HOME}/.appscale/keys/#{cloud}/#{keyname}.key")
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
    Kernel.puts("[#{num_of_vms_to_spawn}] [#{job}] [#{image_id}]  [#{instance_type}] [#{keyname}] [#{infrastructure}] [#{cloud}] [#{group}] [#{spot}]")
    Kernel.puts("EC2_URL = [#{ENV['EC2_URL']}]")
    loop { # need to make sure ec2 doesn't return an error message here
      describe_instances = `#{infrastructure}-describe-instances 2>&1`
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
      run_instances = `#{command_to_run} 2>&1`
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
      sleep(5)
    }
    
    instance_ids = []
    public_ips = []
    private_ips = []

    sleep(10) # euca 2.0.3 can throw forbidden errors if we hit it too fast
    # TODO: refactor me to use rightaws gem, check for forbidden, and retry accordingly

    end_time = Time.now + MAX_VM_CREATION_TIME
    while (now = Time.now) < end_time
      describe_instances = `#{infrastructure}-describe-instances`
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
      sleep(SLEEP_TIME)
    end
    
    abort("No public IPs were able to be procured within the time limit.") if public_ips.length == 0
    
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
    
    jobs = []
    if job.is_a?(String)
      # We only got one job, so just repeat it for each one of the nodes
      public_ips.length.times { |i| jobs << job }
    else
      jobs = job
    end

    # ip:job:instance-id
    instances_created = []
    public_ips.each_index { |index|
      instances_created << "#{public_ips[index]}:#{private_ips[index]}:#{jobs[index]}:#{instance_ids[index]}:#{cloud}"
    }
    
    end_time = Time.now
    total_time = end_time - start_time

    if spot
      Kernel.puts("TIMING: It took #{total_time} seconds to spawn " +
        "#{num_of_vms_to_spawn} spot instances")
    else
      Kernel.puts("TIMING: It took #{total_time} seconds to spawn " +
        "#{num_of_vms_to_spawn} regular instances")
    end

    return instances_created    
  end

  def self.generate_ssh_key(outputLocation, name, infrastructure)
    ec2_output = ""
    loop {
      ec2_output = `#{infrastructure}-add-keypair #{name} 2>&1`
      break if ec2_output.include?("BEGIN RSA PRIVATE KEY")
      Kernel.puts("Trying again. Saw this from #{infrastructure}-add-keypair: #{ec2_output}")
      self.shell("#{infrastructure}-delete-keypair #{name} 2>&1")
    }

    # output is the ssh private key prepended with info we don't need
    # delimited by the first \n, so rip it off first to get just the key

    #first_newline = ec2_output.index("\n")
    #ssh_private_key = ec2_output[first_newline+1, ec2_output.length-1]

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
    desc_instances = `#{infrastructure}-describe-instances`
    instances = desc_instances.scan(/INSTANCE\s+(i-\w+)\s+[\w\-\s\.]+#{keyname}/).flatten
    self.shell(`#{infrastructure}-terminate-instances #{instances.join(' ')}`)
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
      describe_instances = `#{infrastructure}-describe-instances 2>&1`
      Kernel.puts("[oi!] #{describe_instances}")
      break unless describe_instances =~ /Message replay detected./
      sleep(10)
    }

    running_machine_regex = /\s+(#{IP_OR_FQDN})\s+(#{IP_OR_FQDN})\s+running\s+#{keyname}\s/
    all_ip_addrs = describe_instances.scan(running_machine_regex).flatten
    Kernel.puts("[oi!] all ips are [#{all_ip_addrs.join(', ')}]")
    public_ips, private_ips = HelperFunctions.get_ips(all_ip_addrs)
    return public_ips, private_ips
  end
    
  def self.get_usage
    top_results = `top -n1 -d0 -b`
    usage = {}
    usage['cpu'] = nil
    usage['mem'] = nil
    
    if top_results =~ /Cpu\(s\):\s+([\d|\.]+)%us,\s+([\d|\.]+)%sy/
      user_cpu = Float($1)
      sys_cpu = Float($2)
      usage['cpu'] = user_cpu + sys_cpu
    end

    if top_results =~ /Mem:\s+(\d+)k total,\s+(\d+)k used/
      total_memory = Float($1)
      used_memory = Float($2)
      usage['mem'] = used_memory / total_memory * 100
    end

    usage['disk'] = Integer(`df /`.scan(/(\d+)%/).flatten.to_s)
    
    usage    
  end

  # Determine the port that the given app should use
  def self.application_port(app_number, index, num_of_servers)
    APP_START_PORT + (app_number * num_of_servers) + index
  end

  def self.generate_location_config handler
    return "" if !handler.key?("static_dir") && !handler.key?("static_files")

    result = "\n    location #{handler['url']} {"
    result << "\n\t" << "root $cache_dir;"
    result << "\n\t" << "expires #{handler['expiration']};" if handler['expiration']

    # TODO: return a 404 page if rewritten path doesn not exist
    if handler.key?("static_dir")
      result << "\n\t" << "rewrite #{handler['url']}(.*) /#{handler['static_dir']}/$1 break;"
    elsif handler.key?("static_files")
      result << "\n\t" << "rewrite #{handler['url']} /#{handler['static_files']} break;"
    end
    
    result << "\n" << "    }" << "\n"

    result
  end

  def self.get_app_path app_name
    "/var/apps/#{app_name}/"
  end

  def self.get_cache_path app_name
    File.join(get_app_path(app_name),"cache")
  end

  # The directory where the applications tarball will be extracted to
  def self.get_untar_dir app_name
    File.join(get_app_path(app_name),"app")
  end

  # We have the files full path (e.g. ./data/myappname/static/file.txt) but we want is
  # the files path relative to the apps directory (e.g. /static/file.txt).
  # This is the hacky way of getting that.
  def self.get_relative_filename filename, app_name
    filename[get_untar_dir(app_name).length..filename.length]
  end

  def self.parse_static_data app_name
    untar_dir = get_untar_dir(app_name)

    begin
      tree = YAML.load_file(File.join(untar_dir,"app.yaml"))
    rescue Errno::ENOENT => e
      Kernel.puts("Failed to load YAML file to parse static data")
      return []
    end

    handlers = tree["handlers"]
    default_expiration = expires_duration(tree["default_expiration"])
    
    # Create the destination cache directory
    cache_path = get_cache_path(app_name)
    FileUtils.mkdir_p cache_path

    skip_files_regex = DEFAULT_SKIP_FILES_REGEX
    if tree["skip_files"]
      # An alternate regex has been provided for the files which should be skipped
      input_regex = tree["skip_files"]
      input_regex = input_regex.join("|") if input_regex.kind_of?(Array)

      # Remove any superfluous spaces since they will break the regex
      input_regex.gsub!(/ /,"")
      skip_files_regex = Regexp.new(input_regex)
    end

    handlers.map! do |handler|
      next if !handler.key?("static_dir") && !handler.key?("static_files")
      
      # TODO: Get the mime-type setting from app.yaml and add it to the nginx config

      if handler["static_dir"]
        # This is for bug https://bugs.launchpad.net/appscale/+bug/800539
        # this is a temp fix
        if handler["url"] == "/"
          Kernel.puts("Remapped path from / to temp_fix for application #{app_name}")
          handler["url"] = "/temp_fix"
        end
        cache_static_dir_path = File.join(cache_path,handler["static_dir"])
        FileUtils.mkdir_p cache_static_dir_path

        filenames = Dir.glob(File.join(untar_dir, handler["static_dir"],"*"))

        # Remove all files which match the skip file regex so they do not get copied
        filenames.delete_if { |f| File.expand_path(f).match(skip_files_regex) }

        FileUtils.cp_r filenames, cache_static_dir_path

        handler["expiration"] = expires_duration(handler["expiration"]) || default_expiration
      elsif handler["static_files"]
        # This is for bug https://bugs.launchpad.net/appscale/+bug/800539
        # this is a temp fix
        if handler["url"] == "/"
          Kernel.puts("Remapped path from / to temp_fix for application #{app_name}")
          handler["url"] = "/temp_fix"
        end
        # Need to convert all \1 into $1 so that nginx understands it
        handler["static_files"] = handler["static_files"].gsub(/\\/,"$")

        upload_regex = Regexp.new(handler["upload"])

        filenames = Dir.glob(File.join(untar_dir,"**","*"))

        filenames.each do |filename|
          relative_filename = get_relative_filename(filename,app_name)

          # Only include files that match the provided upload regular expression
          next if !relative_filename.match(upload_regex)

          # Skip all files which match the skip file regex so they do not get copied
          next if relative_filename.match(skip_files_regex)

          file_cache_path = File.join(cache_path, File.dirname(relative_filename))
          FileUtils.mkdir_p file_cache_path if !File.exists?(file_cache_path)
          
          FileUtils.cp_r filename, File.join(file_cache_path,File.basename(filename))
        end

        handler["expiration"] = expires_duration(handler["expiration"]) || default_expiration
      end
      handler
    end

    handlers.compact
  end

  # Parses the expiration string provided in the app.yaml and returns its duration in seconds
  def self.expires_duration input_string
    return nil if input_string.nil? || input_string.empty?
    # Start with nil so we can distinguish between it not being set and 0
    duration = nil
    input_string.split.each do |token|
      match = token.match(DELTA_REGEX)
      next if not match
      amount, units = match.captures
      next if amount.empty? || units.empty?
      duration = (duration || 0) + TIME_IN_SECONDS[units.downcase]*amount.to_i
    end
    duration
  end

  def self.encrypt_password(user, pass)
    Digest::SHA1.hexdigest(user + pass)
  end

  def self.obscure_string(string)
    return string if string.nil? or string.length < 4
    last_four = string[string.length-4, string.length]
    obscured = "*" * (string.length-4)
    return obscured + last_four
  end

  def self.obscure_array(array)
    return array.map {|s| 
      if CLOUDY_CREDS.include?(s)
        obscure_string(string)
      else
        string
      end
    }
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

  def self.does_image_have_location?(ip, location, key)
    ret_val = `ssh -i #{key} -o NumberOfPasswordPrompts=0 -o StrictHostkeyChecking=no 2>&1 root@#{ip} 'ls #{location}'; echo $?`.chomp[-1]
    return ret_val.chr == "0"
  end

  def self.ensure_image_is_appscale(ip, key)
    if self.does_image_have_location?(ip, "/etc/appscale", key)
      Kernel.puts("Image at #{ip} is an AppScale image.")
    else
      fail_msg = "The image at #{ip} is not an AppScale image." +
      " Please install AppScale on it and try again."
      Kernel.puts(fail_msg)
      abort(fail_msg)
    end
  end

  def self.ensure_db_is_supported(ip, db, key)
    if self.does_image_have_location?(ip, "/etc/appscale/#{VER_NUM}/#{db}", key)
      Kernel.puts("Image at #{ip} supports #{db}.")
    else 
      fail_msg = "The image at #{ip} does not have support for #{db}." +
        " Please install support for this database and try again."
      Kernel.puts(fail_msg)
      abort(fail_msg)
    end
  end

  def self.generate_makefile(code, input_loc)
    abort("code is nil") if code.nil?

    makefile = "all:\n\t"
    if code =~ /\.x10\Z/
      out = code.scan(/\A(.*)\.x10\Z/).flatten.to_s
      makefile << "/usr/local/x10/x10.dist/bin/x10c++ -x10rt mpi -o #{out} #{code}\n\n"
    elsif code =~ /\.erl\Z/
      makefile << "HOME=/root erlc #{code}"
    elsif code =~ /\.c\Z/
      out = code.scan(/\A(.*)\.c\Z/).flatten.to_s

      code_path = File.expand_path(input_loc + "/" + code)
      contents = self.read_file(code_path)
      if contents =~ /#include .mpi\.h./
        makefile << "mpicc #{code} -o #{out} -Wall"

      # for upc, there's upc_relaxed, upc_strict, and upc
      # this should catch them all - just like pokemon
      elsif contents.include?("#include <upc")
        makefile << "/usr/local/berkeley_upc-2.12.1/upcc --network=mpi -o #{out} #{code}"
      else # its plain old c
        makefile << "gcc -o #{out} #{code} -Wall"
      end
    elsif code =~ /\.go\Z/
        prefix = code.scan(/\A(.*)\.go\Z/).flatten.to_s
        link = "#{prefix}.6"
        makefile << "GOROOT=#{GOROOT} #{GOBIN}/6g #{code} && GOROOT=#{GOROOT} #{GOBIN}/6l -o #{prefix} #{link}"
    else
      abort("code type not supported for auto-gen makefile")
    end

    makefile_location = File.expand_path(input_loc + "/Makefile")
    self.write_file(makefile_location, makefile)
  end

  def self.log_obscured_env()
    env = `env`

    ["EC2_ACCESS_KEY", "EC2_SECRET_KEY"].each { |cred|
      if env =~ /#{cred}=(.*)/
        env.gsub!(/#{cred}=(.*)/, "#{cred}=#{self.obscure_string($1)}")
      end
    }

    Kernel.puts(env)
  end

  def self.get_num_cpus()
    return Integer(`cat /proc/cpuinfo | grep 'processor' | wc -l`.chomp)
  end

  def self.shorten_to_n_items(n, array)
    len = array.length
    if len < n
      array
    else
      array[len-n..len-1]
    end
  end

  def self.find_majority_item(array)
    count = {}
    array.each { |item|
      count[item] = 0 if count[item].nil?
      count[item] += 1
    }

    max_k = nil
    max_v = 0
    count.each { |k, v|
      if v > max_v
        max_k = k
        max_v = v
      end
    }

    return max_k
  end


end
