require 'dbfrontend'
require 'usertools'

class UsersController < ApplicationController
  include UsersHelper
  filter_parameter_logging :password, :password_confirmation

  def new
    @user = User.new
  end

  def create
    @user = User.new(params[:user])
        
    if !@user.valid?
      flash.now[:error] = "There was an error with your submission"
      return render :action => :new
    end

    result = @user.create_account

    if result[:success]
      flash[:notice] = "Your account has been successfully created"
      token = create_token(session[:session_id], @user.email)

      if token.nil?
        flash[:error] = "The database appears to be down right now. Please contact your cloud administrator."
        redirect_to :action => :login
      else
        session[:appengine_token] = token
        session[:appengine_user] = @user.email
        session[:logged_in] = true
        email = session[:appengine_user]
        set_appserver_cookie(email)

        check_for_continue

        if should_be_redirected?
          redirect_to :action => :confirm
        else
          redirect_to :controller => :landing, :action => :index
        end
      end
    else
      flash.now[:error] = result[:message]
      render :action => :new
    end
  end

  def login
    @user = User.new
    
    check_for_continue

    if should_be_redirected?
      redirect_to get_redirect_url
    end

    if has_valid_token?(session[:session_id])
      render :action => :confirm
    end
  end

  def authenticate
    @user = User.new(params[:user] || {})

    # A hack to set the confirmation since the main login page doesn't have a confirmation box.
    # Otherwise it fails validation.
    @user.password_confirmation = @user.password

    if !@user.valid?
      flash.now[:error] = "There was an error with your submission"
      return render :action => :login
    end
    
    result = @user.authenticate!

    if result[:success]
      token = create_token(session[:session_id], @user.email)

      if token.nil?
        flash.now[:error] = "The database appears to be down right now. Please contact your cloud administrator."
        render :action => :login
      else
        session[:appengine_token] = token
        session[:appengine_user] = @user.email
        session[:logged_in] = true
        email = session[:appengine_user]
        set_appserver_cookie(email)

        check_for_continue

        if should_be_redirected?
          redirect_to :action => :confirm
        else
          redirect_to :controller => :landing, :action => :index
        end
      end
    else
      flash.now[:error] = result[:message]
      render :action => :login
    end
  end

  def logout
    create_token(session[:session_id], "invalid") # clear the token out
    reset_session
    cookies[:dev_appserver_login] = { :value => nil, :domain => UserTools.local_ip, :expires => Time.at(0) }
    flash[:notice] = "You have been logged out."
    redirect_to url_for(:controller => :landing, :action => :index)
  end

  def confirm
  end

  def verify
    verified = (params[:commit] == "Yes")

    dest_url = get_destination_url
    
    if verified && dest_url
      redirect_to dest_url
    else
      flash[:error] = "Destination URL not set. Unable to redirect." if verified && dest_url.nil?
      redirect_to :controller => :landing, :action => :index
    end
  end
end
