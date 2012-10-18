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


  VER_NUM = "1.5"

  
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


  PUBLIC_IP_FILE = "/etc/appscale/my_public_ip"


  CLOUD_INFO_FILE = "/etc/appscale/cloud_info.json"


  def self.shell(cmd)
    Kernel.puts(cmd)
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
    data = self.read_file(location, chomp=false)
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


  def self.get_my_public_ip()
    return self.read_file(PUBLIC_IP_FILE, chomp=true)
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
  

  # Code for local_ip taken from 
  # http://coderrr.wordpress.com/2008/05/28/get-your-local-ip-address/
  def self.local_ip
    UDPSocket.open {|s| s.connect("64.233.187.99", 1); s.addr.last }
  end


  def self.get_random_alphanumeric(length=10)
    random = ""
    possible = "0123456789abcdefghijklmnopqrstuvxwyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    possibleLength = possible.length

    length.times { |index|
      random << possible[rand(possibleLength)]
    }

    random
  end


  def self.get_cloud_info()
    return self.read_json_file(CLOUD_INFO_FILE)
  end


  def self.get_num_cpus()
    return Integer(`cat /proc/cpuinfo | grep 'processor' | wc -l`.chomp)
  end


  def self.obscure_string(string)
    return string if string.nil? or string.length < 4
    last_four = string[string.length-4, string.length]
    obscured = "*" * (string.length-4)
    return obscured + last_four
  end


end
