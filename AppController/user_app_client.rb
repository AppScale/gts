#!/usr/bin/ruby -w
# Programmer: Chris Bunch

require 'base64'
require 'openssl'
require 'soap/rpc/driver'
require 'timeout'

class UserAppClient
  attr_reader :conn, :ip, :secret

  def initialize(ip, secret)
    @ip = ip
    @secret = secret
    
    @conn = SOAP::RPC::Driver.new("https://#{@ip}:4343")
    @conn.add_method("change_password", "user", "password", "secret")
    @conn.add_method("commit_new_user", "user", "passwd", "utype", "secret")
    @conn.add_method("commit_new_app", "user", "appname", "language", "secret")
    @conn.add_method("commit_tar", "app_name", "tar", "secret")
    @conn.add_method("delete_app", "appname", "secret")    
    @conn.add_method("is_app_enabled", "appname", "secret")
    @conn.add_method("does_user_exist", "username", "secret")
    @conn.add_method("get_user_data", "username", "secret")
    @conn.add_method("get_app_data", "appname", "secret")
    @conn.add_method("delete_instance", "appname", "host", "port", "secret")
    @conn.add_method("get_tar", "app_name", "secret")
    @conn.add_method("add_instance", "appname", "host", "port", "secret")
    @conn.add_method("get_all_apps", "secret")
  end

  def make_call(timeout, retry_on_except)
    result = ""
    begin
      Timeout::timeout(timeout) do
        begin
          yield if block_given?
        end
      end
    rescue OpenSSL::SSL::SSLError
      retry
    rescue Errno::ECONNREFUSED
      if retry_on_except
        sleep(1)
        retry
      else
        abort("We were unable to establish a connection with the UserAppServer at the designated location. Is AppScale currently running?")
      end 
   rescue Exception => except
      if except.class == Interrupt
        abort
      end

      puts "An exception of type #{except.class} was thrown."
      retry if retry_on_except
    end
  end
  
  def commit_new_user(user, encrypted_password, user_type, retry_on_except=true)
    result = ""
    make_call(10, retry_on_except) { 
      result = @conn.commit_new_user(user, encrypted_password, user_type, @secret)
    }

    if result == "true"
      puts "\nYour user account has been created successfully."
    elsif result == "false"
      abort("\nWe were unable to create your user account. Please contact your cloud administrator for further details.")
    else
      puts "\n[unexpected] Commit new user returned: [#{result}]"
    end
  end
  
  def commit_new_app(user, app_name, language, file_location)
    commit_new_app_name(user, app_name, language)
    commit_tar(app_name, file_location)
  end
  
  def commit_new_app_name(user, app_name, language, retry_on_except=true)
    result = ""
    make_call(10, retry_on_except) {
      result = @conn.commit_new_app(user, app_name, language, @secret)
    }

    if result == "true"
      puts "We have reserved the name #{app_name} for your application."
    elsif result == "Error: appname already exist"
      puts "We are uploading a new version of the application #{app_name}."
    elsif result == "Error: User not found"
      abort("We were unable to reserve the name of your application. Please contact your cloud administrator for more information.")
    else
      puts "[unexpected] Commit new app says: [#{result}]"
    end
  end
  
  def commit_tar(app_name, file_location, retry_on_except=true)
    file = File.open(file_location, "rb")
    tar_contents = Base64.encode64(file.read)
    
    result = ""
    make_call(300, retry_on_except) {
      result = @conn.commit_tar(app_name, tar_contents, @secret)
    }
 
    if result == "true"
      puts "#{app_name} was uploaded successfully."
    elsif result == "Error: app does not exist"
      abort("We were unable to upload your application. Please contact your cloud administrator for more information.")
    else
      puts "[unexpected] Commit new tar says: [#{result}]"
    end
  end
  
  def change_password(user, new_password, retry_on_except=true)
    result = ""
    make_call(10, retry_on_except) {
      result = @conn.change_password(user, new_password, @secret)
    }
        
    if result == "true"
      puts "We successfully changed the password for the given user."
    elsif result == "Error: user not found"
      puts "We were unable to locate a user with the given username."
    else
      puts "[unexpected] Got this message back: [#{result}]"
    end
  end

  def delete_app(app, retry_on_except=true)
    result = ""
    make_call(10, retry_on_except) {
      result = @conn.delete_app(app, @secret)
    }
    
    if result == "true"
      return true
    else
      return result
    end  
  end

  def does_app_exist?(app, retry_on_except=true)
    result = ""
    make_call(10, retry_on_except) {
      result = @conn.is_app_enabled(app, @secret)
    }
    
    return result
  end
  
  def does_user_exist?(user, retry_on_except=true)
    result = ""
    make_call(10, retry_on_except) {
      result = @conn.does_user_exist(user, @secret)
    }
    
    return result
  end

  def get_user_data(username, retry_on_except=true)
    result = ""
    make_call(10, retry_on_except) {
      result = @conn.get_user_data(username, @secret)
    }

    return result
  end

  def get_app_data(appname, retry_on_except=true)
    result = ""
    make_call(10, retry_on_except) {
      result = @conn.get_app_data(appname, @secret)
    }

    return result
  end

  def delete_instance(appname, host, port, retry_on_except=true)
    result = ""
    make_call(10, retry_on_except) {
      result = @conn.delete_instance(appname, host, port, @secret)
    }

    return result
  end

  def get_all_apps(retry_on_except=true)
    result = ""
    make_call(10, retry_on_except) {
      result = @conn.get_all_apps(@secret)
    }

    return result
  end

  def get_tar(appname, retry_on_except=true)
    result = ""
    make_call(300, retry_on_except) {
      result = @conn.get_tar(appname, @secret)
    }

    return result
  end

  def add_instance(appname, host, port, retry_on_except=true)
    result = ""
    make_call(10, retry_on_except) {
      result = @conn.add_instance(appname, host, port, @secret)
    }

    return result
  end
end
