# Filters added to this controller apply to all controllers in the application.
# Likewise, all the methods added will be available for all controllers.

class ApplicationController < ActionController::Base
  helper :all # include all helpers, all the time
  protect_from_forgery # See ActionController::RequestForgeryProtection for details
  layout 'main'
  before_filter :check_for_valid_session
  before_filter :check_for_remote_session

  # Catch-all for any uncaught exceptions, display flash error message
  rescue_from Exception, :with => :rescue_all_exceptions if RAILS_ENV == 'production'
  
  def rescue_all_exceptions(exception)
    error_message = [ "Exception Type: #{exception.class.to_s}",
                      "Requested URI: #{request.request_uri}",
                      "Request Paramaters: #{request.parameters.inspect.to_s}",
                      "Error Backtrace: ", exception.clean_backtrace.join("\n") ].join("\n")
    logger.error error_message
    flash[:error] = "An error has occured and your request was unable to be completed." +
      " This was most likely because a previous instance of AppScale was running. If this " +
      "error continues contact your cloud adminstrator." 
    redirect_to :controller => :landing, :action => :index
  end

  def valid_tools?
    @@valid_tools ||= check_tools
  end

  def get_remote_ip
    # request.env['HTTP_REMOTE_ADDR'] will return the user's IP address
    # but since NAT'ed users have the same IP, returning it would let
    # one user log in as another, so for now just use the session id,
    # which is unique
    return session[:session_id]
    # request.env['HTTP_REMOTE_ADDR']
  end

  def check_for_valid_session
    cookie_val = cookies[:dev_appserver_login]
    return if cookie_val.nil?
    tokens = cookie_val.split(":")
    if tokens.length != 4
      # guard against user-crafted cookies
      Rails.logger.info "saw a malformed cookie: [#{cookie_val}] - clearing it out"
      cookies[:dev_appserver_login] = { :value => nil, :domain => UserTools.public_ip, :expires => Time.at(0) }
      return
    end
    email, nick, admin, hash = tokens

    my_hash = UserTools.get_appengine_hash(email, nick, admin)
    if my_hash != hash
      reset_session
      cookies[:dev_appserver_login] = { :value => nil, :domain => UserTools.public_ip, :expires => Time.at(0) }
      return
    end
  end

  def set_appserver_cookie(email)
    begin
      conn = DBFrontend.get_instance
      secret = UserTools.get_secret_key
      user_data = conn.get_user_data(email, secret)
      apps = user_data.scan(/\napplications:(.*)\n/).flatten.to_s.split(":").join(",")
      cookie_value = UserTools.get_cookie_value(email, apps)
    rescue SOAP::FaultError
      cookie_value = nil
    end
    begin
      public_ip = UserTools.public_ip
    rescue Errno::ENOENT
      # TODO: What should be done here if the public_ip file doesn't exist ?
      public_ip = nil
    end
    logger.info "setting cookie for ip #{public_ip} with value #{cookie_value}"
    cookies[:dev_appserver_login] = {
      :value => cookie_value,
      :domain => public_ip,
      :path => "/",
      :expires => 1.days.from_now
    }
  end

  # Contacts the UserAppServer to store a 'token' on behalf of a user. The original
  # idea of the token was to enable users to be automatically logged in on
  # AppLoadBalancers with different IPs, but who share the same database instance.
  # Users then would be uniquely identified (by their IP or Rails session ID) and
  # this identifier would be used to retrieve the previously stored token.
  # TODO(cgb): Now that we don't use a unique identifier, we should consider
  # eliminating the use of tokens and just revert back to checking for a valid
  # cookie.
  # Args:
  #   email: A String that uniquely identifies the currently logged-in user.
  # Returns:
  #   If the token was created successfully, this returns a String that contains
  #   user-specific information. If the token was not created successfully (e.g.,
  #   if the UserAppServer is down), this returns nil.
  def create_token(email)
    conn = DBFrontend.get_instance
    secret = UserTools.get_secret_key

    # next release: use / enforce token_exp
    # token for now contains just email address
    # will later need to contain a list of apps the user is admin on
    token = "#{email}"
    #token_exp = User.get_token_expiration_date
    begin
      token_inserted = conn.commit_ip(email, token, secret)
      logger.info "just created token for email [#{email}] with contents [#{token}], returning [#{token_inserted}]"
    rescue Errno::ECONNREFUSED
      return nil
    end

    #TODO: we should probably be checking that the token was inserted before returning it --jkupferman

    return token
  end

  # TODO: There is a similar method in UserTools, should probably merge the two
  def get_token(email)
    logger.info "email is [#{email}], which is of class [#{email.class}]"
    conn = DBFrontend.get_instance
    secret = UserTools.get_secret_key

    begin
      if email.nil?
        logger.info "not trying to get token, email is nil"
	return nil
      else
        token_data = conn.get_ip(email, secret)
        logger.info "get token for email [#{email}] returned [#{token_data}]"
      end
    rescue Errno::ECONNREFUSED
      return nil
    end

    return nil if token_data =~ /false:.._ERROR:/ or token_data == "invalid"
    logger.info "found a token with info [#{token_data}]"
    # next release: enforce exp date here
    # exp_date = token_data.scan(/token_exp:([09]+)/).to_s

    token = token_data
    logger.info "returning token with info [#{token}]"
    return token
  end

  def check_for_remote_session
    email = session[:appengine_user]
    if email.nil? || email.empty?
      session[:logged_in] = false
      return
    end

    token = get_token(email)
    logger.info "token for email [#{email}] is [#{token}]"
    if token.nil? || token.empty?
      session[:logged_in] = false
      return
    end
    user = token
    set_appserver_cookie(user) # need to rework this later
    session[:appengine_token] = token
    session[:appengine_user] = user
    session[:logged_in] = true
  end

  private
  def check_tools
    if TOOLS_PATH.nil? || !File.exist?(TOOLS_PATH)
      return false
    end

    bin_dir = File.join(TOOLS_PATH,"bin")
    if !File.exist?(bin_dir)
      return false 
    end

    upload_script = File.join(bin_dir,"appscale-upload-app")
    if !File.exist?(upload_script) || !File.executable?(upload_script)
      return false 
    end

    remove_script = File.join(bin_dir,"appscale-remove-app")
    if !File.exist?(remove_script) || !File.executable?(remove_script)
      return false 
    end

    readme = File.join(TOOLS_PATH,"README")
    return false if !File.exist?(readme)

    # Tools must be version 1.3 or greater
    valid_version = File.open(readme) { |f| f.grep(/Version (1.[3-9]|[2-9]+.[0-9])/).any? }
    return false if !valid_version

    true
  end
end
