# Methods added to this helper will be available to all templates in the application.
require 'rubygems'
require 'json'

require 'usertools'
require 'dbfrontend'

APPSCALE_HOME=ENV['APPSCALE_HOME']

module ApplicationHelper
  def is_user_cloud_admin
    return false unless logged_in?
    return UserTools.is_user_cloud_admin?(user_email, UserTools.get_database_location)
  end

  def i_can_has_upload?
    return false unless logged_in?
    capabilities = DBFrontend.get_capabilities(user_email)
    return false if capabilities.class != String # users with no capabilities have a SOAP object here
    Rails.logger.info "oi! capabilities is #{capabilities}"
    return capabilities.split(":").include?("upload_app")
  end

  def logged_in?
    session[:logged_in]
  end

  def user_email
    return "" unless logged_in?
    session[:appengine_user]
  end

  def display_flash_messages
    return if flash.empty?
    # if the only flash message is a notice, display a green flash instead of red
    display_id = ((flash.has_key?(:notice) && flash.one?) ? "noticeExplanation" : "errorExplanation")
    content_tag :ul, :id => display_id do
      [:error, :warning, :notice].map do |level|
        content_tag :li, flash[level], :class => "flash #{level}" if flash[level]
      end
    end
  end

  def display_error_messages obj, field
    return "" if obj.errors.nil? || obj.errors.on(field).nil?
    message = ""
    obj.errors.on(field).each do |error|
      message << error.capitalize << ". "
    end
    content_tag :div, message, :class => :red
  end

  def highlight_active tab_name
    id = [tab_name, controller_name, action_name]
    case
      when id == ["home", "landing", "index"]
      "active"
      when id == ["upload", "apps", "new"]
      "active"
      when id == ["delete", "apps", "delete"]
      "active"
      when id == ["status", "status", "cloud"]
      "active"
    else
      ""
    end
  end

  def set_onload
    if controller_name == "users"
      "onload=setFocus()"
    elsif controller_name == "status" && action_name == "cloud"
      "onload=\"setInterval('window.location.reload(true)',10000)\""
    else
      ""
    end
  end

  def get_status_files
    @status_files ||= Dir.glob(File.expand_path("/etc/appscale/status-*")).sort
  end

  def get_application_information
    status_files = get_status_files

    apps = {}

    status_files.each { |filename|
      raw_contents = (File.open(filename) { |f| f.read })

      begin
        # see which apps are registered in the system
        # apps have a name (k) and a state (v), which
        # is either true if is is running and false if
        # it is not (e.g., still starting up or shutting down)

        # we're polling multiple appservers, who may each
        # be reporting true or false - if any of them report
        # true we want to report true

        stats = JSON.load(raw_contents)
        stats['apps'].each { |k, v|
          next if k == "none"
          if apps[k].nil?
            apps[k] = v
          else
            apps[k] = v if v
          end
        }
      rescue Exception => e
      end
    }

    apps
  end

  def get_head_node_ip
    filename = "#{APPSCALE_HOME}/.appscale/login_ip"
    unless File.exists?(filename)
      abort("The file #{filename} did not exist, could not get login IP.")
    end

    head_node_ip = File.open(filename) { |f| f.read }.chomp
    return head_node_ip
  end

  def get_my_ip
    return UserTools.public_ip
  end

  def monitoring_url
    head_node_ip = get_head_node_ip

    "http://#{head_node_ip}:8050"
  end

  def sisyphus_url
    head_node_ip = get_head_node_ip

    "http://#{head_node_ip}/apps/sisyphus"
  end
end
