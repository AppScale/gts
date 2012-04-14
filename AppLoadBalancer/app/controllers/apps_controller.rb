class AppsController < ApplicationController
  include AppsHelper
  before_filter :require_tools, :only => [:new, :upload, :delete, :remove]
  before_filter :require_login, :only => [:new, :upload, :delete, :remove]
  before_filter :require_authorization, :only => [:new, :upload, :delete, :remove]

  def redirect
    app_name = params[:name] || params[:id]
    suffix = params[:anything].join('/')

    result = get_application_path(app_name, suffix)

    if result[:exists]
      session[:app_name] = app_name
      redirect_to result[:path]
    else
      flash[:error] = result[:message]
      redirect_to :controller => :status, :action => :cloud
    end
  end

  def new
    @app = App.new
  end

  def upload
    @app = App.new(params[:app])

    if !@app.valid?
      flash.now[:error] = "There was an error with your submission"
      return render :action => :new
    end

    @app.filename = "#{Time.now.to_i.to_s}-#{user_email}-#{@app.file_data.original_filename}"

    if @app.save!
      Rails.logger.info "uploading new app with admin #{user_email} and name #{params[:app]}"
      result = @app.upload_app user_email
      if result[:success]
        flash[:notice] = "Your app has been successfully uploaded. Please wait a moment for it to start running."
        redirect_to :controller => :status, :action => :cloud
      else
        # TODO This needs to be :error, but right now non-errors show up here
        flash.now[:notice] = "Message about your submission:" << "<br/>" << result[:message]
        render :action => :new
      end
    else
      flash[:error] = "Unable to upload file. An error occured on the server."
      redirect_to :action => :new
    end
  end

  def delete
    @apps = get_application_information.keys
    return if is_user_cloud_admin
    db_location = UserTools.get_database_location
    @apps.delete_if {|a| a == "none" || !UserTools.is_user_admin?(user_email, a, db_location) }
    @apps.compact!
  end

  def destroy
    appname = params[:appname]
    
    if appname.nil?
      flash[:error] = "Invalid app name provided."
      return redirect_to :action => :delete
    end

    db_location = UserTools.get_database_location
    if !(UserTools.is_user_admin?(user_email, appname, db_location) or is_user_cloud_admin)
      flash[:error] = "Unable to delete #{appname}. You must be an administrator to delete an application."
      return redirect_to :action => :delete
    end

    # TODO: right now we aren't checking the result of removing the application
    # if we do it in the same thread, then the app redirects to /apps/destroy
    # even though we explicitly tell it to go to /status
    # should fix this when we get more time

    Thread.new { App.remove_app appname }
    #Rails.logger.info "remove app result is #{result.inspect}"
    #if result[:success]
      flash[:notice] = "Application #{appname} has been removed. It should disappear momentarily."
      redirect_to :controller => :status, :action => :cloud
    #else
    #  flash[:error] = "There was an error with your submission:" << "<br/>" << result[:message]
    #  redirect_to :action => :delete
    #end
  end

  private
  def require_tools
    if !valid_tools?
      flash.now[:error] = "This functionality has been disabled because valid appscale tools could not be found."
      return render :partial => "shared/tools_error", :layout => "main"
    end
  end

  def require_login
    if !logged_in?
      user_action = action_description
      flash[:error] = "You must be logged in to #{user_action}."
      return redirect_to :controller => :users, :action => :login
    end
  end

  def action_description
    case action_name
    when "new", "create"
      "upload an application"
    when "delete", "destroy"
      "delete an application"
    else
      "perform that action"
    end
  end

  def require_authorization
    if !i_can_has_upload?
      flash[:error] = "You are not authorized to upload or remove applications."
      return redirect_to :controller => :landing, :action => :index
    end
  end
end
