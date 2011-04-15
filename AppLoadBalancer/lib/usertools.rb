require 'digest/sha1'
require 'soap/rpc/driver'

APPSCALE_HOME=ENV['APPSCALE_HOME']

class UserTools
  def self.get_cookie_value(email, applist)
    nick = email.scan(/^(.*)@/).to_s
    database_location = self.get_database_location
    hsh = self.get_appengine_hash(email, nick, applist)
    "#{email}:#{nick}:#{applist}:#{hsh}"
  end

  def self.set_appserver_cookie(email, applist)
    begin
      cookie_value = self.get_cookie_value(email, applist)
    rescue SOAP::FaultError
      cookie_value = nil
    end
    begin
      public_ip = self.public_ip
    rescue Errno::ENOENT
      # TODO: What should be done here if the public_ip file doesn't exist ?
      public_ip = nil
    end

    cookies[:dev_appserver_login] = {
      :value => cookie_value,
      :domain => public_ip,
      :path => "/",
      :expires => 1.days.from_now
    }
  end

  def self.get_applist(email)
    secret = UserTools.get_secret_key
    user_data = conn.get_user_data(email, secret)
    apps = user_data.scan(/\napplications:(.*)\n/).flatten.to_s.split(":").join(",")
    apps
  end

  def self.get_token(ip)
    return nil if ip.nil?
    conn = DBFrontend.get_instance
    secret = UserTools.get_secret_key

    begin
      token_data = conn.get_token(ip, secret)
    rescue Errno::ECONNREFUSED
      return nil
    end

    return nil if token_data == "Error: user not found"

    # next release: enforce exp date here
    exp_date = token_data.scan(/token_exp:([0-9]+)/).to_s

    token = token_data.scan(/token:([0-9A-Za-z\.@]+)/).to_s
    return token
  end

  def self.is_user_admin?(user, app, database_location)
    secret = UserTools.get_secret_key
    conn = SOAP::RPC::Driver.new("https://#{database_location}:4343")
    conn.add_method("get_app_data", "appname", "secret")
    app_data = conn.get_app_data(app, secret)
    app_owner = app_data.scan(/\napp_owner:([a-zA-Z@.]+)\n/).flatten.to_s
    return user == app_owner
  end

  def self.is_user_cloud_admin?(user, database_location)
    secret = UserTools.get_secret_key
    conn = SOAP::RPC::Driver.new("https://#{database_location}:4343")
    conn.add_method("is_user_cloud_admin", "username", "secret")
    status = conn.is_user_cloud_admin(user, secret)
    return status == "true" 
  end

  def self.get_secret_key(path="#{APPSCALE_HOME}/.appscale/secret.key")
    cached_secret = CACHE.get('secret')
    return cached_secret unless cached_secret.nil?

    secret_key_path = File.expand_path(path)
    secret_key = (File.open(secret_key_path) { |file| file.read }).chomp
    CACHE.set('secret', secret_key, 30)

    return secret_key
  end

  def self.get_database_location(path="#{APPSCALE_HOME}/.appscale/masters")
    cached_master = CACHE.get('master_ip')
    return cached_master unless cached_master.nil?

    database_path = File.expand_path(path)
    database_location = (File.open(database_path) { |file| file.read }).chomp
    CACHE.set('master_ip', database_location, 30)

    return database_location
  end

  def self.public_ip
    cached_ip = CACHE.get('my_public_ip')
    return cached_ip unless cached_ip.nil?

    my_pub_ip_file = "#{APPSCALE_HOME}/.appscale/my_public_ip"
    my_pub_ip = (File.open(File.expand_path(my_pub_ip_file)) { |file| file.read }).chomp
    CACHE.set('my_public_ip', my_pub_ip, 30)

    return my_pub_ip
  end

  def self.login_ip
    cached_ip = CACHE.get('login_ip')
    return cached_ip unless cached_ip.nil?

    login_file = "#{APPSCALE_HOME}/.appscale/login_ip"
    login_ip = (File.open(File.expand_path(login_file)) { |file| file.read }).chomp
    CACHE.set('login_ip', login_ip, 30)

    return login_ip
  end
  
  def self.local_ip
    cached_ip = CACHE.get('my_local_ip')
    return cached_ip unless cached_ip.nil?

    # turn off reverse DNS resolution temporarily
    orig, Socket.do_not_reverse_lookup = Socket.do_not_reverse_lookup, true
    
    UDPSocket.open do |s|
      s.connect '64.233.187.99', 1 # google

      CACHE.set('my_local_ip', s.addr.last, 30)
      s.addr.last
    end
  ensure
    Socket.do_not_reverse_lookup = orig
  end

  def self.encrypt_password(user, pass)
    salted = user + pass
    Digest::SHA1.hexdigest(salted)
  end
  
  def self.get_appengine_hash(email, nick, admin)
    salted = email + nick + admin + self.get_secret_key
    Digest::SHA1.hexdigest(salted)
  end

  def self.generate_random_string(length)
    possible_vals = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    possible_length = possible_vals.length
    
    rand_str = ""
    length.times { |index|
      rand_str << possible_vals[rand(possible_length)]
    }
    
    return rand_str
  end
end
