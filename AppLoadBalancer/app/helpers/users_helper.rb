module UsersHelper

  def get_cookie_value(email, app)
    nick = email.scan(/^(.*)@/).to_s
    database_location = UserTools.get_database_location
    admin = "#{UserTools.is_user_admin?(email, app, database_location)}"
    hsh = UserTools.get_appengine_hash(email, nick, admin)
    "#{email}:#{nick}:#{admin}:#{hsh}"
  end

  def get_destination_url
    session[:dest_url]
  end

  def get_redirect_url
    if session[:dest_url]
      session[:dest_url]
    else
      nil
    end
  end

  IP_REGEX = /\d+\.\d+\.\d+\.\d+/
  FQDN_REGEX = /[\w\d\.\-]+/
  IP_OR_FQDN = /#{IP_REGEX}|#{FQDN_REGEX}/

  def check_for_continue
    if params[:continue]
      destination_url = params[:continue].scan(/continue=(http?.*)/).flatten.to_s
    end

    session[:dest_url] = destination_url if destination_url && destination_url.any?
    Rails.logger.info "oi! dest url is #{session[:dest_url]}"
  end


  def should_be_redirected?   
    !get_destination_url.nil? && !cookies[:dev_appserver_login].nil?
  end

  def has_valid_token?(ip)
    return false if ip.nil? || !cookies[:dev_appserver_login].nil?

    token_data = DBFrontend.get_token(ip)

    return false if token_data.nil? 
    return false if token_data == "Error: user not found"

    # next release: enforce exp date here
    exp_date, server_token = parse_token_data(ip, token_data)

    client_token = session[:appengine_token]
    
    if server_token == client_token
      return true
    else
      return false
    end
  end

  def parse_token_data(ip, token_data)
    exp_date = token_data.scan(/token_exp:([0-9]+)/).to_s
    server = token_data.scan(/token:([0-9A-Z]+)/).to_s
    return [exp_date, server]
  end
end
