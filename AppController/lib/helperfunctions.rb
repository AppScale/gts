#!/usr/bin/ruby -w

# Imports within Ruby's standard libraries
require 'base64'
require 'digest'
require 'fileutils'
require 'find'
require 'net/http'
require 'openssl'
require 'socket'
require 'timeout'
require 'tmpdir'

# Imports for RubyGems
require 'rubygems'
require 'json'

# Imports for AppController libraries
$:.unshift File.join(File.dirname(__FILE__))
require 'custom_exceptions'

# BadConfigurationExceptions represent an exception that can be thrown by the
# AppController or any other library it uses, if a method receives inputs
# it isn't expecting.
class BadConfigurationException < StandardError
end

# HelperFunctions holds miscellaneous functions - functions that really aren't
# bound to a particular service, but are reused across multiple functions.
# TODO: Consider removing App Engine-related functions below into its
# own helper class
module HelperFunctions
  APPSCALE_HOME = ENV['APPSCALE_HOME']

  # The location on the filesystem where configuration files about
  # AppScale are stored.
  APPSCALE_CONFIG_DIR = '/etc/appscale'.freeze

  # The directory where static version assets are stored.
  VERSION_ASSETS_DIR = '/var/appscale/version_assets'.freeze

  APPSCALE_KEYS_DIR = "#{APPSCALE_CONFIG_DIR}/keys/cloud1".freeze

  # The maximum amount of time, in seconds, that we are willing to wait for
  # a virtual machine to start up, from the initial run-instances request.
  # Setting this value is a bit of an art, but we choose the value below
  # because our image is roughly 10GB in size, and if Eucalyptus doesn't
  # have the image cached, it could take half an hour to get our image
  # started.
  MAX_VM_CREATION_TIME = 1800

  # Generic sleep time to take while waiting for remote operation to
  # complete.
  SLEEP_TIME = 10

  # Number of retries to do.
  RETRIES = 5

  IP_REGEX = /\d+\.\d+\.\d+\.\d+/

  FQDN_REGEX = /[\w\d\.\-]+/

  IP_OR_FQDN = /#{IP_REGEX}|#{FQDN_REGEX}/

  DELTA_REGEX = /([1-9][0-9]*)([DdHhMm]|[sS]?)/

  DEFAULT_SKIP_FILES_REGEX = /^(.*\/)?((app\.yaml)|(app\.yml)|(index\.yaml)|(index\.yml)|(\#.*\#)|(.*~)|(.*\.py[co])|(.*\/RCS\/.*)|(\..*)|)$/

  TIME_IN_SECONDS = { 'd' => 86400,
                      'h' => 3600,
                      'm' => 60,
                      's' => 1 }.freeze

  CLOUDY_CREDS = %w[ec2_access_key ec2_secret_key EC2_ACCESS_KEY
                    EC2_SECRET_KEY AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
                    CLOUD_EC2_ACCESS_KEY CLOUD_EC2_SECRET_KEY].freeze

  # A constant that indicates that SSL should be used when checking if a given
  # port is open.
  USE_SSL = true

  # A constant that indicates that SSL should not be used when checking if a
  # given port is open.
  DONT_USE_SSL = false

  # 'he IPv4 address that corresponds to the reserved localhost IP.
  LOCALHOST_IP = '127.0.0.1'.freeze

  # The file permissions that indicate that only the owner of a file
  # can read or write to it (necessary for SSH keys).
  CHMOD_READ_ONLY = 0600

  # A class variable that is used to locally cache our own IP address, so that
  # we don't keep asking the system for it.
  @@my_local_ip = nil

  # A prefix used to distinguish gae apps from appscale apps
  GAE_PREFIX = 'gae_'.freeze

  # The location on the filesystem where the AppController writes information
  # about the exception that killed it, for the tools to retrieve and pass
  # along to the user.
  APPCONTROLLER_CRASHLOG_LOCATION = '/var/log/appscale/appcontroller' \
                                    '_crashlog.txt'.freeze

  # The location on the filesystem where the AppController backs up its
  # internal state, in case it isn't able to contact ZooKeeper to retrieve it.
  APPCONTROLLER_STATE_LOCATION = '/opt/appscale/appcontroller-state.json'.freeze

  # The location on the filesystem where the resolv.conf file can be found,
  # that we may alter if the user requests.
  RESOLV_CONF = '/etc/resolv.conf'.freeze

  # Where we store the applications code.
  APPLICATIONS_DIR = '/var/apps'.freeze

  # Metadata service for Google and AWS
  GCE_METADATA = 'http://169.254.169.254/computeMetadata/v1/instance'.freeze
  AWS_METADATA = 'http://169.254.169.254/latest/meta-data'.freeze

  # Curb the number of entries to print to this number. For example when
  # we print the appengine list, we will print only up to this constant,
  # if more we print the number of entries we have.
  NUM_ENTRIES_TO_PRINT = 10

  def self.shell(cmd)
    `#{cmd}`
  end

  def self.write_file(location, contents)
    File.open(location, 'w+') { |file| file.write(contents) }
  end

  def self.write_json_file(location, contents)
    write_file(location, JSON.dump(contents))
  end

  def self.read_file(location, chomp = true)
    file = File.open(location) { |f| f.read }
    return file.chomp if chomp
    file
  end

  # Reads the given file, which is assumed to be a JSON-loadable object,
  # and returns that JSON back to the caller.
  def self.read_json_file(location)
    data = read_file(location)
    JSON.load(data)
  end

  # Extracts the version from the VERSION file.
  def self.get_appscale_version
    version_contents = read_file(APPSCALE_CONFIG_DIR + '/VERSION')
    version_line = version_contents[/AppScale version (.*)/]
    version_line.sub! 'AppScale version', ''
    version_line.strip
  end

  # Returns a random string composed of alphanumeric characters, as long
  # as the user requests.
  def self.get_random_alphanumeric(length = 10)
    random = ''
    possible = '0123456789abcdefghijklmnopqrstuvxwyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    possible_length = possible.length

    length.times {
      random << possible[Kernel.rand(possible_length)]
    }

    random
  end

  def self.deserialize_info_from_tools(ips)
    JSON.load(ips)
  end

  # Queries the operating system to see if the named process is running.
  #
  # Note: Since this does a 'grep -v grep', callers should not call this
  # method with a name of 'grep'.
  #
  # Args:
  #   name: A String naming the process that may or may not be running.
  def self.is_process_running?(name)
    return false if `ps ax | grep #{name} | grep -v grep`.empty?
    true
  end

  def self.kill_process(name)
    `ps ax | grep #{name} | grep -v grep | awk '{ print $1 }' | xargs -d '\n' kill -9`
  end

  def self.sleep_until_port_is_open(ip, port,
                                    use_ssl = DONT_USE_SSL,
                                    timeout = nil)
    total_time_slept = 0
    sleep_time = 1

    loop {
      return if HelperFunctions.is_port_open?(ip, port, use_ssl)

      Kernel.sleep(sleep_time)
      if (total_time_slept % 5).zero?
        Djinn.log_debug("Waiting on #{ip}:#{port} to be open " \
                        '(currently closed).')
      end
      total_time_slept += sleep_time

      if !timeout.nil? && total_time_slept > timeout
        raise "Waited too long for #{ip}:#{port} to open!"
      end
    }
  end

  def self.sleep_until_port_is_closed(ip, port, use_ssl = DONT_USE_SSL,
                                      timeout = nil)
    total_time_slept = 0
    sleep_time = 1

    loop {
      return unless HelperFunctions.is_port_open?(ip, port, use_ssl)

      Kernel.sleep(sleep_time)
      if (total_time_slept % 5).zero?
        Djinn.log_debug("Waiting on #{ip}:#{port} to be closed " \
                        '(currently open).')
      end
      total_time_slept += sleep_time

      if !timeout.nil? and total_time_slept > timeout
        raise "Waited too long for #{ip}:#{port} to close!"
      end
    }
  end

  def self.is_port_open?(ip, port, use_ssl = DONT_USE_SSL)
    max = 2
    refused_count = 0

    begin
      Timeout.timeout(1) do
        sock = TCPSocket.new(ip, port)
        if use_ssl
          ssl_context = OpenSSL::SSL::SSLContext.new
          unless ssl_context.verify_mode
            ssl_context.verify_mode = OpenSSL::SSL::VERIFY_NONE
          end
          sslsocket = OpenSSL::SSL::SSLSocket.new(sock, ssl_context)
          sslsocket.sync_close = true
          sslsocket.connect
        end
        sock.close
        return true
      end
    rescue OpenSSL::SSL::SSLError
      Djinn.log_debug("Retry after SSL error talking to #{ip}:#{port}")
      refused_count += 1
      if refused_count > max
        Djinn.log_warn("[is_port_open]: saw SSL error talking to " \
                       "#{ip}:#{port}")
      else
        Kernel.sleep(1)
        retry
      end
    rescue => except
      Djinn.log_warn("[is_port_open](#{ip}, #{port}): got #{except.message}.")
    end

    false
  end

  def self.run_remote_command(ip, command, public_key_loc, want_output)
    Djinn.log_debug("ip is [#{ip}], command is [#{command}], public key " \
                    "is [#{public_key_loc}], want output? [#{want_output}]")
    public_key_loc = File.expand_path(public_key_loc)

    remote_cmd = "ssh -i #{public_key_loc} -o StrictHostkeyChecking=no" \
                 " root@#{ip} '#{command} "

    if want_output
      remote_cmd << "2>&1'"
    else
      remote_cmd << "> /dev/null &' &"
    end

    Djinn.log_debug("Running [#{remote_cmd}]")

    shell("#{remote_cmd}")
  end

  # Executes the given command on the specified host, without attempting to
  # redirect standard out or standard err.
  #
  # Args:
  #   ip: A String naming the IP address or FQDN of the machine where the
  #     command should be executed.
  #   command: A String naming the command that should be executed. Callers may
  #     pass in redirection characters (>>) as part of their command, but single
  #     quotes should not be used (since single quotes are used as part of the
  #     ssh call). Use double quotes instead.
  #   public_key_loc: A String naming the location on the local filesystem where
  #     an SSH key can be found that logs into 'ip' without needing a password.
  #
  # Returns:
  #   The output of executing the command on the specified host.
  def self.run_remote_command_without_output(ip, command, public_key_loc)
    Djinn.log_debug("ip is [#{ip}], command is [#{command}], public key " \
                    "is [#{public_key_loc}]")
    public_key_loc = File.expand_path(public_key_loc)
    remote_cmd = "ssh -i #{public_key_loc} -o StrictHostkeyChecking=no " \
                 "root@#{ip} '#{command}'"
    Djinn.log_debug("Running [#{remote_cmd}]")
    shell(remote_cmd.to_s)
  end

  # Secure copies a given file to a remote location.
  # Args:
  #   local_file_loc: The local file to copy over.
  #   remote_file_loc: The remote location to copy to.
  #   target_ip: The remote target IP.
  #   private_key_loc: The private key to use.
  #   from: A Boolean to indicate to copy a file *from* the remote location.
  # Raises:
  #   AppScaleSCPException: When a scp fails.
  def self.scp_file(local_file_loc, remote_file_loc, target_ip,
                    private_key_loc, from = false)
    private_key_loc = File.expand_path(private_key_loc)
    local_file_loc = File.expand_path(local_file_loc)

    # Adjust the command to copy from or to depending on the flag.
    if from
      cmd = "scp -i #{private_key_loc} -o StrictHostkeyChecking=no " \
            "root@#{target_ip}:#{remote_file_loc} #{local_file_loc}"
    else
      cmd = "scp -i #{private_key_loc} -o StrictHostkeyChecking=no " \
            "#{local_file_loc} root@#{target_ip}:#{remote_file_loc}"
    end

    RETRIES.downto(0) {
      case system(cmd)
      when true
        # All good: command executed.
        return
      when nil
        # Something very wrong here.
        Djinn.log_warn("Shell cannot execute #{cmd}: retrying in a few.")
      when false
        Djinn.log_debug('Failed to scp: retrying in a few.')
      end
      Kernel.sleep(SLEEP_TIME)
    }

    # We get here only if scp failed RETRIES times.
    Djinn.log_warn("\n[#{cmd}] failed #{RETRIES} times.")
    raise AppScaleSCPException.new("Failed to copy over #{local_file_loc} to #{remote_file_loc} to #{target_ip} with private key #{private_key_loc}")
  end

  def self.get_remote_appscale_home(ip, key)
    cat = 'cat /etc/appscale/home'
    remote_cmd = "ssh -i #{key} -o NumberOfPasswordPrompts=0 -o " \
                 "StrictHostkeyChecking=no 2>&1 root@#{ip} '#{cat}'"
    possible_home = shell(remote_cmd.to_s).chomp
    return '/root/appscale/' if possible_home.nil? || possible_home.empty?
    possible_home
  end

  def self.get_appscale_id
    # This needs to be ec2 or euca 2ools.
    image_info = `ec2-describe-images`

    log_and_crash("ec2 tools can't find appscale image") unless image_info.include?('appscale')
    image_id = image_info.scan(/([a|e]mi-[0-9a-zA-Z]+)\sappscale/).flatten.to_s

    image_id
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

  def self.get_secret(filename = '/etc/appscale/secret.key')
    read_file(File.expand_path(filename))
  end

  # We use a hash of the secret to prevent showing the actual secret as a
  # command line argument.
  def self.get_taskqueue_secret
    Digest::SHA1.hexdigest(get_secret)
  end

  # Auxiliary function to test if a tarball is correct.
  #
  # Args:
  #   tar_gz_location: The tarball location on the local filesystem.
  #   md5: The MD5 digest of the tarball.
  # Returns:
  #   true  if the tarball is correct, false otherwise.
  def self.check_tarball(tar_gz_location, md5)
    local_md5 = Digest::MD5.file tar_gz_location
    return false unless md5 == local_md5.hexdigest

    cmd = "tar -ztf #{tar_gz_location} > /dev/null 2> /dev/null"
    case system(cmd)
    when nil
      Djinn.log_warn("Couldn't execute #{cmd}!")
    when true
      return true
    end

    Djinn.log_warn("Tarball #{tar_gz_location} is corrupted.")
    false
  end

  # Examines the given tar.gz file to see if it has an App Engine configuration
  # file in it.
  #
  # Args:
  #   tar_gz_location: The location on the local filesystem where the App Engine
  #     application to examine is located.
  # Returns:
  #   true if there is an app.yaml or appengine-web.xml file in the given tar.gz
  #     file, and false otherwise.
  def self.app_has_config_file?(tar_gz_location)
    file_listing = HelperFunctions.shell("tar -ztf #{tar_gz_location}")
    app_yaml_regex = /app\.yaml/
    appengine_web_xml_regex = /(.\/)*WEB-INF\/appengine-web\.xml/
    if file_listing =~ app_yaml_regex || file_listing =~ appengine_web_xml_regex
      return true
    end
    false
  end

  # Prepare the application code to be run by AppServers.
  #
  # Args:
  #   revision_key: A String containing the revision key.
  # Raise:
  #   AppScaleException: if the setup failed for whatever reason (ie bad
  #     tarball). The exception message would indicate the error.
  def self.setup_revision(revision_key)
    meta_dir = "#{APPLICATIONS_DIR}/#{revision_key}"
    tar_dir = "#{meta_dir}/app"
    return if File.directory?(tar_dir)

    # Make sure we have the application source. If not, we have to wait
    # till the AC populates it.
    tar_path = "#{Djinn::PERSISTENT_MOUNT_POINT}/apps/#{revision_key}.tar.gz"
    end_work = Time.now.to_i + SLEEP_TIME * RETRIES
    while Time.now.to_i < end_work
      break if File.file?(tar_path)
      Djinn.log_debug("#{tar_path} is not there yet. Waiting ...")
      Kernel.sleep(Djinn::SMALL_WAIT)
    end
    unless File.file?(tar_path)
      raise AppScaleException.new("#{tar_path} is not available.")
    end

    FileUtils.mkdir_p(tar_dir)
    FileUtils.mkdir_p("#{meta_dir}/log")
    FileUtils.cp("#{APPSCALE_HOME}/AppDashboard/setup/404.html", meta_dir)
    FileUtils.touch("#{meta_dir}/log/server.log")

    cmd = "tar -xzf #{tar_path} --force-local --no-same-owner -C #{tar_dir}"
    unless system(cmd)
      Djinn.log_warn("setup_app: #{cmd} failed.")
      FileUtils.rm_f(tar_dir)
      raise AppScaleException.new("Failed to untar #{tar_path}.")
    end

    # Separate extra dependencies for Go applications.
    begin
      FileUtils.mv("#{tar_dir}/gopath", "#{meta_dir}/gopath")
    rescue Errno::ENOENT
      Djinn.log_debug("#{revision_key} does not have a gopath directory")
    end

    true
  end

  # Queries the operating system to determine which IP addresses are
  # bound to this virtual machine.
  # Args:
  #   remove_lo: A boolean that indicates whether or not the lo
  #     device's IP should be removed from the results. By default,
  #     we remove it, since it is on all virtual machines and thus
  #     not useful towards uniquely identifying a particular machine.
  # Returns:
  #   An Array of Strings, each of which is an IP address bound to
  #     this virtual machine.
  def self.get_all_local_ips(remove_lo = true)
    ifconfig = HelperFunctions.shell('ifconfig')
    Djinn.log_debug("ifconfig returned the following: [#{ifconfig}]")

    # Normally we would scan for 'inet addr:', but in non-English locales,
    # 'addr' gets translated to the native language, which messes up that
    # regex.
    bound_addrs = ifconfig.scan(/inet .*?:(\d+.\d+.\d+.\d+) /).flatten

    Djinn.log_debug('ifconfig reports bound IP addresses as ' \
      "[#{bound_addrs.join(', ')}]")
    bound_addrs.delete(LOCALHOST_IP) if remove_lo
    bound_addrs
  end

  # Sets the locally cached IP address to the provided value. Callers
  # should use this if they believe the IP address on this machine
  # is not the first IP returned by 'ifconfig', which can occur if
  # the IP to reach this machine on is eth1, eth2, etc.
  # Args:
  #   ip: The IP address that other AppScale nodes can reach this
  #     machine via.
  def self.set_local_ip(ip)
    @@my_local_ip = ip
  end

  # Returns the IP address associated with this machine. To get around
  # issues where a VM may forget its IP address
  # (https://github.com/AppScale/appscale/issues/84), we locally cache it
  # to not repeatedly ask the system for this IP (which shouldn't be changing).
  # TODO: Consider the implications of caching the IP address if
  # VLAN tagging is used, and the IP address may be used.
  # TODO: This doesn't solve the problem if the IP address isn't there
  # the first time around - should we sleep and retry in that case?
  def self.local_ip
    unless @@my_local_ip.nil?
      Djinn.log_debug("Returning cached ip #{@@my_local_ip}")
      return @@my_local_ip
    end

    bound_addrs = get_all_local_ips
    raise 'Couldn\'t get our local IP address' if bound_addrs.length.zero?

    addr = bound_addrs[0]
    Djinn.log_debug("Returning #{addr} as our local IP address")
    @@my_local_ip = addr
    addr
  end

  # In cloudy deployments, the recommended way to determine a machine's true
  # private IP address from its private FQDN is to use dig. This method
  # attempts to resolve IPs in that method, deferring to other methods if that
  # fails.
  #
  # Args:
  #   host: the String containing the IP or hostname.
  # Returns:
  #   A String with the IP address.
  # Raises:
  #   AppScaleException: if host cannot be translated to IP.
  def self.convert_fqdn_to_ip(host)
    return host if host =~ /#{IP_REGEX}/

    ip = `dig #{host} +short`.chomp
    if ip.empty?
      Djinn.log_warn("Couldn't use dig to resolve #{host}.")
      raise AppScaleException.new("Couldn't convert #{host}: result of dig" \
                                  " was \n#{ip}.")
    end

    ip
  end

  def self.get_ips(ips)
    log_and_crash('ips not even length array') if ips.length.odd?
    reported_public = []
    reported_private = []
    ips.each_index { |index|
      if index.even?
        reported_public << ips[index]
      else
        reported_private << ips[index]
      end
    }

    Djinn.log_debug("Reported Public IPs: [#{reported_public.join(', ')}]")
    Djinn.log_debug("Reported Private IPs: [#{reported_private.join(', ')}]")

    actual_public = []
    actual_private = []

    reported_public.each_index { |index|
      pub = reported_public[index]
      pri = reported_private[index]
      if pub != '0.0.0.0' && pri != '0.0.0.0'
        actual_public << pub
        actual_private << pri
      end
    }

    actual_private.each_index { |index|
      begin
        actual_private[index] = HelperFunctions.convert_fqdn_to_ip(actual_private[index])
      rescue
        # this can happen if the private ip doesn't resolve
        # which can happen in hybrid environments: euca boxes wont be
        # able to resolve ec2 private ips, and vice-versa in euca-managed-mode
        Djinn.log_debug("rescued! failed to convert #{actual_private[index]} to public")
        actual_private[index] = actual_public[index]
      end
    }

    return actual_public, actual_private
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

    Djinn.log_debug("The average spot instance price for a #{instance_type} " \
      "machine is $#{average}, and 20% more is $#{plus_twenty}")
    plus_twenty
  end

  def self.spawn_vms(num_of_vms_to_spawn, job, image_id, instance_type,
                     keyname, infrastructure, cloud, group, spot = false)
    start_time = Time.now

    return [] if num_of_vms_to_spawn < 1

    ssh_key = File.expand_path("#{APPSCALE_CONFIG_DIR}/keys/#{cloud}/#{keyname}.key")
    Djinn.log_debug("About to spawn VMs, expecting to find a key at #{ssh_key}")

    log_obscured_env

    new_cloud = !File.exists?(ssh_key)
    if new_cloud # need to create security group and key
      Djinn.log_debug("Creating keys/security group for #{cloud}")
      generate_ssh_key(ssh_key, keyname, infrastructure)
      create_appscale_security_group(infrastructure, group)
    else
      Djinn.log_debug("Not creating keys/security group for #{cloud}")
    end

    instance_ids_up = []
    public_up_already = []
    private_up_already = []
    Djinn.log_debug("[#{num_of_vms_to_spawn}] [#{job}] [#{image_id}]  [#{instance_type}] [#{keyname}] [#{infrastructure}] [#{cloud}] [#{group}] [#{spot}]")
    Djinn.log_debug("EC2_URL = [#{ENV['EC2_URL']}]")
    loop { # need to make sure ec2 doesn't return an error message here
      describe_instances = `#{infrastructure}-describe-instances 2>&1`
      Djinn.log_debug("describe-instances says [#{describe_instances}]")
      all_ip_addrs = describe_instances.scan(/\s+(#{IP_OR_FQDN})\s+(#{IP_OR_FQDN})\s+running\s+#{keyname}\s/).flatten
      instance_ids_up = describe_instances.scan(/INSTANCE\s+(i-\w+)/).flatten
      public_up_already, private_up_already = HelperFunctions.get_ips(all_ip_addrs)
      vms_up_already = describe_instances.scan(/(#{IP_OR_FQDN})\s+running\s+#{keyname}\s+/).length

      # crucial for hybrid cloud, where one box may not be running yet
      break if vms_up_already > 0 || new_cloud 
    }

    args = "-k #{keyname} -n #{num_of_vms_to_spawn} --instance-type #{instance_type} --group #{group} #{image_id}"
    if spot
      price = HelperFunctions.get_optimal_spot_price(instance_type)
      command_to_run = "ec2-request-spot-instances -p #{price} #{args}"
    else
      command_to_run = "#{infrastructure}-run-instances #{args}"
    end

    loop {
      Djinn.log_debug(command_to_run)
      run_instances = `#{command_to_run} 2>&1`
      Djinn.log_debug("run_instances says [#{run_instances}]")
      if run_instances =~ /Please try again later./
        Djinn.log_debug("Error with run_instances: #{run_instances}. Will try again in a moment.")
      elsif run_instances =~ /try --addressing private/
        Djinn.log_debug('Need to retry with addressing private. Will try again in a moment.')
        command_to_run << " --addressing private"
      elsif run_instances =~ /PROBLEM/
        Djinn.log_debug("Error: #{run_instances}")
        log_and_crash("Saw the following error message from EC2 tools." \
          "Please resolve the issue and try again:\n#{run_instances}")
      else
        Djinn.log_debug('Run instances message sent successfully. Waiting for the image to start up.')
        break
      end
      Djinn.log_debug('sleepy time')
      sleep(SLEEP_TIME)
    }

    instance_ids = []
    public_ips = []
    private_ips = []

    end_time = Time.now + MAX_VM_CREATION_TIME
    while (now = Time.now) < end_time
      describe_instances = `#{infrastructure}-describe-instances`
      Djinn.log_debug("[#{Time.now}] #{end_time - now} seconds left...")
      Djinn.log_debug(describe_instances)

      # TODO: match on instance id

      # changed regexes so ensure we are only checking for instances created
      # for appscale only (don't worry about other instances created)
      all_ip_addrs = describe_instances.scan(/\s+(#{IP_OR_FQDN})\s+(#{IP_OR_FQDN})\s+running\s+#{keyname}\s+/).flatten
      public_ips, private_ips = HelperFunctions.get_ips(all_ip_addrs)
      public_ips -= public_up_already
      private_ips -= private_up_already
      instance_ids = describe_instances.scan(/INSTANCE\s+(i-\w+)\s+[\w\-\s\.]+#{keyname}/).flatten - instance_ids_up
      break if public_ips.length == num_of_vms_to_spawn
      sleep(SLEEP_TIME)
    end

    log_and_crash('No public IPs were able to be procured within the time' \
                  ' limit.') if public_ips.length.zero?

    if public_ips.length != num_of_vms_to_spawn
      potential_dead_ips = HelperFunctions.get_ips(all_ip_addrs) - public_up_already
      potential_dead_ips.each_index { |index|
        if potential_dead_ips[index] == '0.0.0.0'
          instance_to_term = instance_ids[index]
          Djinn.log_debug("Instance #{instance_to_term} failed to get a " \
                          'public IP address and is being terminated.')
          shell("#{infrastructure}-terminate-instances #{instance_to_term}")
        end
      }
    end

    jobs = []
    if job.is_a?(String)
      # We only got one job, so just repeat it for each one of the nodes
      public_ips.length.times { jobs << job }
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
      Djinn.log_debug("TIMING: It took #{total_time} seconds to spawn " \
        "#{num_of_vms_to_spawn} spot instances")
    else
      Djinn.log_debug("TIMING: It took #{total_time} seconds to spawn " \
        "#{num_of_vms_to_spawn} regular instances")
    end

    return instances_created
  end

  def self.generate_ssh_key(output_location, name, infrastructure)
    ec2_output = ""
    loop {
      ec2_output = `#{infrastructure}-add-keypair #{name} 2>&1`
      break if ec2_output.include?("BEGIN RSA PRIVATE KEY")
      Djinn.log_debug("Trying again. Saw this from #{infrastructure}-add-keypair: #{ec2_output}")
      self.shell("#{infrastructure}-delete-keypair #{name} 2>&1")
    }

    output_location = [output_location] if output_location.class == String
    output_location.each { |path|
      full_path = File.expand_path(path)
      File.open(full_path, "w") { |file|
        file.puts(ec2_output)
      }
      FileUtils.chmod(0600, full_path) # else ssh won't use the key
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

  def self.generate_location_config handler
    return "" if !handler.key?("static_dir") && !handler.key?("static_files")

    # TODO: return a 404 page if rewritten path doesn't exist
    if handler.key?("static_dir")
      result = "\n    location #{handler['url']}/ {"
      result << "\n\t" << "root $cache_dir;"
      result << "\n\t" << "expires #{handler['expiration']};" if handler['expiration']

      result << "\n\t" << "rewrite #{handler['url']}(.*) /#{handler['static_dir']}/$1 break;"
    elsif handler.key?("static_files")
      # Users can specify a regex that names their static files. If they specify
      # any regex characters, assume that the whole string is a regex
      # (otherwise, it's a literal string).
      if handler['url'] =~ /[\?|\:|\||\+|\(|\)|\*|\^|\$|\[|\]]/
        result = "\n    location ~ #{handler['url']} {"
      else
        result = "\n    location \"#{handler['url']}\" {"
      end

      result << "\n\t" << "root $cache_dir;"
      result << "\n\t" << "expires #{handler['expiration']};" if handler['expiration']

      result << "\n\t" << "rewrite \"#{handler['url']}\" \"/#{handler['static_files']}\" break;"
    end

    result << "\n" << "    }" << "\n"

    result
  end

  # Generate a Nginx location configuration for the given app-engine
  # URL handler configuration.
  # Params:
  #   handler - A hash containing the metadata related to the handler
  #   port - Port to which the secured traffic should be redirected
  # Returns:
  #   A Nginx location configuration as a string
  def self.generate_secure_location_config(handler, port)
    result = "\n    location ~ #{handler['url']} {"
    if handler["secure"] == "always"
      result << "\n\t" << "rewrite #{handler['url']}(.*) https://$host:#{port}$uri redirect;"
    elsif handler["secure"] == "never"
      result << "\n\t" << "rewrite #{handler['url']}(.*) http://$host:#{port}$uri? redirect;"
    else
      return ""
    end

    result << "\n" << "    }" << "\n"

    return result
  end

  def self.get_loaded_versions
    version_keys = []
    Dir["#{APPLICATIONS_DIR}/*"].each{ |revision_dir|
      revision_key = File.basename(revision_dir)

      # Ignore project directories.
      next unless revision_key.include?(Djinn::VERSION_PATH_SEPARATOR)
      version_keys << revision_key.rpartition(Djinn::VERSION_PATH_SEPARATOR)[0]
    }
    return version_keys
  end

  # Retrieves the latest revision directory for a project.
  #
  # Args:
  #   project_id: A string specifying a project ID.
  # Returns:
  #   A string specifying the location of the source directory.
  # Raises:
  #   AppScaleException when unable to find the source directory.
  def self.get_source_for_project(project_id)
    begin
      version_details = ZKInterface.get_version_details(
        project_id, Djinn::DEFAULT_SERVICE, Djinn::DEFAULT_VERSION)
    rescue VersionNotFound
      raise AppScaleException.new('Version not found')
    end

    revision_key = [
      project_id, Djinn::DEFAULT_SERVICE, Djinn::DEFAULT_VERSION,
      version_details['revision'].to_s].join(Djinn::VERSION_PATH_SEPARATOR)
    self.setup_revision(revision_key)
    return "#{APPLICATIONS_DIR}/#{revision_key}/app"
  end

  # Locates WEB-INF folder in an untarred Java app directory.
  #
  # Args:
  #  untar_dir: The location of the untarred Java app on AppScale.
  #
  # Returns:
  #  The directory that contains WEB-INF inside a Java app.
  def self.get_web_inf_dir(untar_dir)
    matches = Array.new
    Find.find(untar_dir) { |path|
      next unless File.basename(path) == 'appengine-web.xml'
      next unless File.file?(path)
      next unless File.dirname(path).end_with?('/WEB-INF')
      matches << File.dirname(path)
    }

    raise InvalidSource.new('WEB-INF directory not found') if matches.empty?

    shortest_match = matches[0]
    matches.each { |match|
      if match.split('/').length < shortest_match.split('/').length
        shortest_match = match
      end
    }
    return shortest_match
  end

  # Finds the path to appengine-web.xml configuration file.
  #
  # Args:
  #  source_dir: The location of the revision's source code.
  #
  # Returns:
  #  The absolute path of the appengine-web.xml configuration file.
  def self.get_appengine_web_xml(source_dir)
    return File.join(self.get_web_inf_dir(source_dir), "/appengine-web.xml")
  end

  # We have the files full path (e.g. ./data/myappname/static/file.txt) but we want is
  # the files path relative to the apps directory (e.g. /static/file.txt).
  # This is the hacky way of getting that.
  def self.get_relative_filename filename, untar_dir
    return filename[untar_dir.length..filename.length]
  end

  def self.parse_static_data(version_key, copy_files)
    # Retrieve latest source archive if not on this machine.
    project_id, service_id, version_id = version_key.split(
      Djinn::VERSION_PATH_SEPARATOR)
    begin
      version_details = ZKInterface.get_version_details(
        project_id, service_id, version_id)
    rescue VersionNotFound
      return []
    end

    revision_key = [version_key, version_details['revision'].to_s].join(
      Djinn::VERSION_PATH_SEPARATOR)
    begin
      self.setup_revision(revision_key)
    rescue AppScaleException
      return []
    end
    untar_dir = "#{APPLICATIONS_DIR}/#{revision_key}/app"

    begin
      tree = YAML.load_file(File.join(untar_dir,"app.yaml"))
    rescue Errno::ENOENT
      return self.parse_java_static_data(revision_key)
    end

    default_expiration = expires_duration(tree["default_expiration"])

    # Create the destination cache directory
    cache_path = "#{VERSION_ASSETS_DIR}/#{version_key}"
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

    if tree["handlers"]
      handlers = tree["handlers"]
    else
      return []
    end

    handlers.map! do |handler|
      next if !handler.key?("static_dir") && !handler.key?("static_files")

      # TODO: Get the mime-type setting from app.yaml and add it to the nginx config

      if handler["static_dir"]
        # This is for bug https://bugs.launchpad.net/appscale/+bug/800539
        # this is a temp fix
        if handler["url"] == "/"
          Djinn.log_debug("Remapped path from / to temp_fix for application #{version_key}")
          handler["url"] = "/temp_fix"
        end

        handler["expiration"] = expires_duration(handler["expiration"]) || default_expiration

        if copy_files
          cache_static_dir_path = File.join(cache_path,handler["static_dir"])
          FileUtils.mkdir_p cache_static_dir_path

          filenames = Dir.glob(File.join(untar_dir, handler["static_dir"],"*"))

          # Remove all files which match the skip file regex so they do not get copied
          filenames.delete_if { |f| File.expand_path(f).match(skip_files_regex) }

          FileUtils.cp_r filenames, cache_static_dir_path
        end
      elsif handler["static_files"]
        # This is for bug https://bugs.launchpad.net/appscale/+bug/800539
        # this is a temp fix
        if handler["url"] == "/"
          Djinn.log_debug("Remapped path from / to temp_fix for application #{version_key}")
          handler["url"] = "/temp_fix"
        end
        # Need to convert all \1 into $1 so that nginx understands it
        handler["static_files"] = handler["static_files"].gsub(/\\/,"$")

        handler["expiration"] = expires_duration(handler["expiration"]) || default_expiration

        if copy_files
          upload_regex = Regexp.new(handler["upload"])

          filenames = Dir.glob(File.join(untar_dir,"**","*"))

          filenames.each do |filename|
            relative_filename = get_relative_filename(filename, untar_dir)

            # Only include files that match the provided upload regular expression
            next unless relative_filename.match(upload_regex)

            # Skip all files which match the skip file regex so they do not get copied
            next if relative_filename.match(skip_files_regex)

            file_cache_path = File.join(cache_path, File.dirname(relative_filename))
            FileUtils.mkdir_p file_cache_path unless File.exists?(file_cache_path)

            FileUtils.cp_r filename, File.join(file_cache_path,File.basename(filename))
          end
        end
      end
      handler
    end

    return handlers.compact
  end

  # Sets up static files in nginx for this Java App Engine app, by following
  # the default static file rules. Specifically, it states that any file in
  # the app that doesn't end in .jsp that isn't in the WEB-INF directory should
  # be added as a static file.
  #
  # TODO: Check the appengine-web.xml file given to us by the app and see
  # if it specifies any files to include or exclude as static files, instead of
  # assuming they want to use the default scheme mentioned above.
  #
  # Args:
  #   revision_key: A String containing the revision key.
  # Returns:
  #   An Array of Hashes, where each hash names the URL that a static file will
  #   be accessed at, and the location in the static file directory where the
  #   file can be found.
  def self.parse_java_static_data(revision_key)
    version_key = revision_key.rpartition(Djinn::VERSION_PATH_SEPARATOR)[0]

    # Verify that revision is a Java app.
    tar_gz_location = "#{Djinn::PERSISTENT_MOUNT_POINT}/apps/" +
      "#{revision_key}.tar.gz"
    unless self.app_has_config_file?(tar_gz_location)
      Djinn.log_warn("#{revision_key} does not appear to be a Java app")
      return []
    end

    # Walk through all files in the war directory, and add them if (1) they
    # don't end in .jsp and (2) it isn't the WEB-INF directory.
    cache_path = "#{VERSION_ASSETS_DIR}/#{version_key}"
    FileUtils.mkdir_p(cache_path)
    Djinn.log_debug("Made static file dir for #{version_key} at #{cache_path}")

    untar_dir = "#{APPLICATIONS_DIR}/#{revision_key}/app"
    begin
      war_dir = self.get_web_inf_dir(untar_dir)
    rescue InvalidSource => error
      Djinn.log_error(error.message)
      return []
    end

    # Copy static files.
    handlers = []
    all_files = Dir.glob("#{war_dir}/**/*")
    all_files.each { |filename|
      next if filename.end_with?(".jsp")
      next if filename.include?("WEB-INF")
      next if File.directory?(filename)
      relative_path = filename.scan(/#{war_dir}\/(.*)/).flatten.to_s
      Djinn.log_debug("Copying static file #{filename} to cache location #{File.join(cache_path, relative_path)}")
      cache_file_location = File.join(cache_path, relative_path)
      FileUtils.mkdir_p(File.dirname(cache_file_location))
      FileUtils.cp_r(filename, cache_file_location)
      handlers << {
        'url' => "/#{relative_path}",
        'static_files' => "/#{relative_path}"
      }
    }

    handlers.compact
  end

  # Parses the app.yaml file for the specified version and returns
  # any URL handlers with a secure tag. The returns secure tags are
  # put into a hash where the hash key is the value of the secure
  # tag (always or never) and value is a list of handlers.
  # Params:
  #   version_key: A string specifying the version key.
  # Returns:
  #   A hash containing lists of secure handlers
  def self.get_secure_handlers(version_key)
    Djinn.log_debug("Getting secure handlers for #{version_key}")
    project_id, service_id, version_id = version_key.split(
      Djinn::VERSION_PATH_SEPARATOR)

    secure_handlers = []

    begin
      version_details = ZKInterface.get_version_details(
        project_id, service_id, version_id)
    rescue VersionNotFound
      Djinn.log_warn("Skipping secure handlers for #{version_key} because " \
                     'version node does not exist')
      return secure_handlers
    end
    revision_key = [version_key, version_details['revision'].to_s].join(
      Djinn::VERSION_PATH_SEPARATOR)
    setup_revision(revision_key)
    untar_dir = "#{APPLICATIONS_DIR}/#{revision_key}/app"

    begin
      tree = YAML.load_file(File.join(untar_dir, 'app.yaml'))
    rescue Errno::ENOENT
      Djinn.log_debug('No YAML for static data. Looking for an XML file.')
      return secure_handlers
    end

    return secure_handlers unless tree['handlers']
    handlers = tree['handlers']

    handlers.map! do |handler|
      if !handler.key?("static_dir") && !handler.key?("static_files")
        handler['secure'] = 'non_secure' if !handler.key?('secure')
        secure_handlers.push(handler)
      end
    end
    secure_handlers
  end

  # Parses the expiration string provided in the app.yaml and returns its duration in seconds
  def self.expires_duration(input_string)
    return nil if input_string.nil? || input_string.empty?
    # Start with nil so we can distinguish between it not being set and 0
    duration = nil
    input_string.split.each do |token|
      match = token.match(DELTA_REGEX)
      next unless match
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

  # Searches through the key/value pairs given for items that may
  # be too sensitive to log in cleartext. If any of these items are
  # found, a sanitized version of the item is returned in its place.
  # Args:
  #   options: The item to sanitize. As we are expecting Hashes here,
  #     callers that pass in non-Hash items can expect no change to
  #     be performed on their argument.
  # Returns:
  #   A sanitized version of the given Hash, that can be safely
  #     logged via stdout or saved in log files. In the case of
  #     non-Hash items, the original item is returned.
  def self.obscure_options(options)
    return options if options.class != Hash

    obscured = {}
    options.each { |k, v|
      if CLOUDY_CREDS.include?(k)
        obscured[k] = obscure_string(v)
      else
        obscured[k] = v
      end
    }

    obscured
  end

  def self.does_image_have_location?(ip, location, key)
    retries_left = 10
    begin
      ret_val = shell("ssh -i #{key} -o NumberOfPasswordPrompts=0 -o StrictHostkeyChecking=no 2>&1 root@#{ip} 'ls #{location}'; echo $?").chomp[-1]
      return true if ret_val.chr == '0'

      retries_left -= 1
      return false if retries_left <= 0
      raise "Received non-zero exit code while checking for #{location}."
    rescue => error
      Djinn.log_debug("Saw #{error.inspect}. " +
        "Retrying in #{SLEEP_TIME} seconds.")
      Kernel.sleep(SLEEP_TIME)
      retry
    end
  end

  def self.ensure_image_is_appscale(ip, key)
    if does_image_have_location?(ip, "/etc/appscale", key)
      Djinn.log_debug("Image at #{ip} is an AppScale image.")
    else
      fail_msg = "The image at #{ip} is not an AppScale image. " \
                 'Please install AppScale on it and try again.'
      Djinn.log_debug(fail_msg)
      log_and_crash(fail_msg)
    end
  end

  # Checks to see if the virtual machine at the given IP address has
  # the same version of AppScale installed as these tools.
  # Args:
  #   ip: The IP address of the VM to check the version on.
  #   key: The SSH key that can be used to log into the machine at the
  #     given IP address.
  # Raises:
  #   AppScaleException: If the virtual machine at the given IP address
  #     does not have the same version of AppScale installed as these
  #     tools.
  def self.ensure_version_is_supported(ip, key)
    version = get_appscale_version
    return if does_image_have_location?(ip, "/etc/appscale/#{version}", key)
    raise AppScaleException.new("The image at #{ip} does not support " \
      "this version of AppScale (#{version}). Please install AppScale" \
      " #{version} on it and try again.")
  end

  def self.ensure_db_is_supported(ip, db, key)
    version = get_appscale_version
    if does_image_have_location?(ip, "/etc/appscale/#{version}/#{db}", key)
      Djinn.log_debug("Image at #{ip} supports #{db}.")
    else
      fail_msg = "The image at #{ip} does not have support for #{db}." \
        ' Please install support for this database and try again.'
      Djinn.log_debug(fail_msg)
      log_and_crash(fail_msg)
    end
  end

  def self.log_obscured_env
    env = `env`

    %w[EC2_ACCESS_KEY EC2_SECRET_KEY].each { |cred|
      if env =~ /#{cred}=(.*)/
        env.gsub!(/#{cred}=(.*)/, "#{cred}=#{obscure_string($1)}")
      end
    }

    Djinn.log_debug(env)
  end

  # Examines the configuration file for the given version to see if it is
  # thread safe.
  #
  # Args:
  #   version_key: A String that specifies the version key.
  # Returns:
  #   Boolean true if the app is thread safe. Boolean false if it is not.
  def self.get_version_thread_safe(version_key)
    project_id, service_id, version_id = version_key.split(
      Djinn::VERSION_PATH_SEPARATOR)
    begin
      version_details = ZKInterface.get_version_details(
        project_id, service_id, version_id)
    rescue VersionNotFound
      # If the version does not exist, assume it is not thread safe.
      return false
    end

    version_details.fetch('threadsafe', true)
  end

  # Logs the given message on the filesystem, where the AppScale Tools can
  # report it to the user. This method then crashes the caller, so that the
  # AppScale Tools knows that a fatal error has occurred and that it needs to be
  # reported.
  #
  # Args:
  #   message: A String that indicates why the AppController is crashing.
  # Raises:
  #   SystemExit: Always occurs, since this method crashes the AppController.
  def self.log_and_crash(message, sleep = nil)
    write_file(APPCONTROLLER_CRASHLOG_LOCATION, Time.new.to_s + ': ' +
      message)
    # Try to also log to the normal log file.
    Djinn.log_error("FATAL: #{message}")

    # If asked for, wait for a while before crashing. This will help the
    # tools to collect the status report or crashlog.
    Kernel.sleep(sleep) unless sleep.nil?
    abort(message)
  end

  # Contacts the Metadata Service running in Amazon Web Services, or
  # Google Compute Engine or any other supported public cloud,  to
  # determine the public FQDN associated with this virtual machine.
  #
  # This method should only be called when running in a cloud that
  # provides an AWS-compatible Metadata Service (e.g., EC2 or Eucalyptus).
  #
  # Returns:
  #   A String containing the public IP that traffic can be sent to that
  #   reaches this machine.
  def self.get_public_ip_from_metadata_service
    url = URI.parse("#{AWS_METADATA}/public-ipv4")
    request = Net::HTTP::Get.new(url.path)
    response = Net::HTTP.start(url.host) { |http| http.request(request) }
    if response.code == '200'
      Djinn.log_debug("Detected AWS public ip: #{response.body}.")
      return response.body
    end

    url = URI.parse(
      "#{GCE_METADATA}/network-interfaces/0/access-configs/0/external-ip")
    request = Net::HTTP::Get.new(url.path)
    # Google requires an extra header when requesting metadata.
    request.add_field('Metadata-Flavor', 'Google')
    response = Net::HTTP.start(url.host) { |http| http.request(request) }
    if response.code == '200'
      Djinn.log_debug("Detected GCE public ip: #{response.body}.")
      return response.body
    end
  end
end
