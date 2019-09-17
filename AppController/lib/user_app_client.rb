#!/usr/bin/ruby -w

# Imports within Ruby's standard libraries
require 'base64'
require 'openssl'
require 'soap/rpc/driver'
require 'timeout'

require 'helperfunctions'

# AppControllers and other services need to read or write data relating to users
# and applications hosted in AppScale. Since it has to be done in a
# database-agnostic fashion, we throw up a special server that responds to SOAP
# requests for this information, called the UserAppServer. This class provides
# convenience methods for interacting with the UserAppServer.
class UserAppClient
  attr_reader :conn, :ip, :secret

  # The default name for the server.
  NAME = 'UserAppServer'.freeze

  # The port that the UserAppServer binds to, by default.
  SSL_SERVER_PORT = 4343

  # The port the server is listening to.
  SERVER_PORT = 4342

  # The port used to have HAProxy in front of the UserAppServer.
  HAPROXY_SERVER_PORT = 4341

  # This is the minimum Timeout to use when talking to the datastore.
  DS_MIN_TIMEOUT = 20


  def initialize(ip, secret)
    @ip = ip
    @secret = secret

    @conn = SOAP::RPC::Driver.new("http://#{@ip}:#{HAPROXY_SERVER_PORT}")
    @conn.add_method('change_password', 'user', 'password', 'secret')
    @conn.add_method('commit_new_user', 'user', 'passwd', 'utype', 'secret')
    @conn.add_method('is_user_cloud_admin', 'username', 'secret')
    @conn.add_method('does_user_exist', 'username', 'secret')
    @conn.add_method('get_user_data', 'username', 'secret')
    @conn.add_method('get_all_users', 'secret')
    @conn.add_method('set_cloud_admin_status', 'username', 'is_cloud_admin', 'secret')
    @conn.add_method('set_capabilities', 'username', 'capabilities', 'secret')
  end


  # Check the comments in AppController/lib/app_controller_client.rb.
  def make_call(time, retry_on_except, callr)
    begin
      Timeout.timeout(time) {
        begin
          yield if block_given?
        rescue Errno::ECONNREFUSED, Errno::EHOSTUNREACH,
          OpenSSL::SSL::SSLError, NotImplementedError, Errno::EPIPE,
          Errno::ECONNRESET, SOAP::EmptyResponseError, StandardError => e
          if retry_on_except
            Kernel.sleep(1)
            Djinn.log_debug("[#{callr}] exception in make_call to " +
              "#{@ip}:#{SERVER_PORT}. Exception class: #{e.class}. Retrying...")
            retry
          else
            trace = e.backtrace.join("\n")
            Djinn.log_warn('Exception encountered while talking to ' \
              "#{@ip}:#{SERVER_PORT}.\n#{trace}")
            raise FailedNodeException.new("Exception #{e.class}:#{e.message} encountered " +
              "while talking to #{@ip}:#{SERVER_PORT}.")
          end
        end
      }
    rescue Timeout::Error
      Djinn.log_warn("[#{callr}] SOAP call to #{@ip} timed out")
      raise FailedNodeException.new("Time out talking to #{@ip}:#{SERVER_PORT}")
    end
  end

  def commit_new_user(user, encrypted_password, user_type,
                      retry_on_except = true)
    result = ''
    make_call(DS_MIN_TIMEOUT, retry_on_except, 'commit_new_user') {
      result = @conn.commit_new_user(user, encrypted_password, user_type, @secret)
    }

    if result == 'true'
      puts "\nYour user account has been created successfully."
    elsif result == 'false'
      raise InternalError.new('Unable to create user')
    elsif result == 'Error: user already exists'
      raise UserExists.new(result)
    else
      raise InternalError.new(result)
    end
    result
  end

  def change_password(user, new_password, retry_on_except = true)
    result = ''
    make_call(DS_MIN_TIMEOUT, retry_on_except, 'change_password') {
      result = @conn.change_password(user, new_password, @secret)
    }

    if result == 'true'
      puts 'We successfully changed the password for the given user.'
    elsif result == 'Error: user not found'
      puts 'We were unable to locate a user with the given username.'
    else
      puts "[unexpected] Got this message back: [#{result}]"
    end
    result
  end

  def does_user_exist?(user, retry_on_except = true)
    result = ''
    make_call(DS_MIN_TIMEOUT, retry_on_except, 'does_user_exist') {
      result = @conn.does_user_exist(user, @secret)
    }

    result
  end

  def get_user_data(username, retry_on_except = true)
    result = ''
    make_call(DS_MIN_TIMEOUT, retry_on_except, 'get_user_data') {
      result = @conn.get_user_data(username, @secret)
    }

    result
  end

  def get_all_users(retry_on_except = true)
    all_users = ''
    make_call(DS_MIN_TIMEOUT, retry_on_except, 'get_all_users') {
      all_users = @conn.get_all_users(@secret)
    }

    user_list = all_users.split(':')
    if user_list[0] == 'Error'
      raise FailedNodeException.new("get_all_users: got #{all_users}.")
    end
    # First item is a dummy value.
    user_list -= [user_list[0]]
    user_list
  end

  def is_user_cloud_admin?(user, retry_on_except = true)
    result = ''
    make_call(DS_MIN_TIMEOUT, retry_on_except, 'is_user_cloud_admin') {
      result = @conn.is_user_cloud_admin(user, @secret)
    }

    return true if result == 'true'
    false
  end

  # This method finds the first user who is a cloud administrator. Since the
  # UserAppServer doesn't provide a function that does this for us, we have
  # to get a list of all the users that exist and individually query the
  # UAServer to find out who the cloud admin is.
  # TODO: Maybe cache who the cloud admin is to speed up future queries?
  def get_cloud_admin
    user_list = get_all_users

    user_list.each { |user|
      return user if is_user_cloud_admin?(user)
    }

    raise Exception.new('Couldn\'t find a cloud administrator')
  end

  def set_admin_role(username, is_cloud_admin, capabilities,
                     retry_on_except = true)
    result_cloud_admin_status = set_cloud_admin_status(username, is_cloud_admin, retry_on_except)
    result_set_capabilities = set_capabilities(username, capabilities, retry_on_except)
    if result_cloud_admin_status && result_set_capabilities == 'true'
      puts 'We successfully set admin role for the given user.'
      return 'true'
    else
      puts 'Got this message back while setting cloud admin status and capabilities:' \
        "Set cloud admin status: [#{result_cloud_admin_status}]" \
        "Set capabilities: [#{result_set_capabilities}]"
    end
  end

  def set_cloud_admin_status(username, is_cloud_admin, retry_on_except)
    result = ''
    make_call(DS_MIN_TIMEOUT, retry_on_except, 'set_cloud_admin_status') {
      result = @conn.set_cloud_admin_status(username, is_cloud_admin, @secret)
    }
    if result == 'true'
      puts 'We successfully set cloud admin status for the given user.'
    elsif result == 'Error: user not found'
      puts 'We were unable to locate a user with the given username.'
    else
      puts "[unexpected] Got this message back: [#{result}]"
    end
    result
  end

  def set_capabilities(username, capabilities, retry_on_except)
    result = ''
    make_call(DS_MIN_TIMEOUT, retry_on_except, 'set_capabilities') {
      result = @conn.set_capabilities(username, capabilities, @secret)
    }
    if result == 'true'
      puts 'We successfully set admin capabilities for the given user.'
    elsif result == 'Error: user not found'
      puts 'We were unable to locate a user with the given username.'
    else
      puts "[unexpected] Got this message back: [#{result}]"
    end
    result
  end
end
