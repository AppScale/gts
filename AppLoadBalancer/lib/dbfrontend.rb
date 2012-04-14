require 'soap/rpc/driver'
#require 'monitor'

APPSCALE_HOME=ENV['APPSCALE_HOME']

class DBFrontend

  def initialize
    hypersoapfile = "#{APPSCALE_HOME}/.appscale/hypersoap"
    @@hsoaploc = (File.open(hypersoapfile) {|f| f.read}).chomp
    @@db_connection = SOAP::RPC::Driver.new("https://#{@@hsoaploc}:4343")
    @@secret = DBFrontend.get_secret("#{APPSCALE_HOME}/.appscale/secret.key")
    @@db_connection.add_method("does_user_exist", "username", "secret")
    @@db_connection.add_method("does_app_exist", "appname", "secret")
    @@db_connection.add_method("get_user_data", "username", "secret")
    @@db_connection.add_method("get_app_data", "appname", "secret")
    @@db_connection.add_method("commit_new_user", "user", "passwd", "utype","secret")
    @@db_connection.add_method("commit_new_app", "user", "appname", "secret")
    @@db_connection.add_method("commit_tar", "app_name", "tar", "secret")
    @@db_connection.add_method("get_tar", "app_name", "secret")
    @@db_connection.add_method("get_all_users", "secret")
    @@db_connection.add_method("delete_all_users", "secret")
    @@db_connection.add_method("delete_all_apps", "secret")
    @@db_connection.add_method("commit_new_token", "user", "token", "token_exp", "secret")
    @@db_connection.add_method("get_token", "user", "secret")
    @@db_connection.add_method("commit_ip", "ip", "email", "secret")
    @@db_connection.add_method("get_ip", "ip", "secret")
    @@db_connection.add_method("get_capabilities", "username", "secret")
    @@db_connection.add_method("set_capabilities", "username", "capabilities", "secret")
  end
  
  def self.get_app_data(app_name)
    conn = self.get_instance

    begin
      app_data = conn.get_app_data(app_name, @@secret)
    rescue Errno::ECONNREFUSED
      return nil
    end

    return app_data
  end

  def self.get_token(ip)
    return nil if ip.nil?

    conn = self.get_instance

    begin
      token_data = conn.get_token(ip, @@secret)
    rescue Errno::ECONNREFUSED
      return nil
    end

    return token_data
  end

  def self.get_all_users()
    conn = self.get_instance

    begin
      all_users = conn.get_all_users(@@secret)
    rescue Errno::ECONNREFUSED
      return nil
    end

    return all_users
  end

  def self.get_capabilities(username)
    conn = self.get_instance

    begin
      capabilities = conn.get_capabilities(username, @@secret)
    rescue Errno::ECONNREFUSED
      return []
    end

    return capabilities
  end

  def self.set_capabilities(username, capabilities)
    conn = self.get_instance

    begin
      response = conn.set_capabilities(username, capabilities, @@secret)
    rescue Errno::ECONNREFUSED
      return nil
    end

    return response
  end

  def self.get_secret(secret_location="#{APPSCALE_HOME}/.appscale/secret.key")
    return nil unless File.exists?(secret_location)

    secret = (File.open(secret_location) { |f| f.read }).chomp
    return secret
  end
  
  def self.acc_secret
    @@secret
  end

  def self.hsoaploc
    @@hsoaploc
  end
  
  def self.get_instance
    foo = DBFrontend.new
    @@db_connection
  end
end
