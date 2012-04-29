# Programmer: Chris Bunch

require 'task_engine'

require 'rubygems'
require 'httparty'


class TaskEngineAppScale < TaskEngine
  attr_accessor :appid, :appcfg_cookies, :function


  NAME = "appscale-push-q"

  
  def initialize(credentials)
    if credentials.class != Hash
      raise BadConfigurationException.new("Credentials not a hash.")
    end
    
    if credentials['@appid'].nil?
      raise BadConfigurationException.new("No appid provided.")
    end
    @appid = credentials['@appid']
    
    if credentials['@function'].nil?
      raise BadConfigurationException.new("No function provided.")
    end
    @function = credentials['@function']
  end


  # To see if an app is running in AppScale, we just see if the app is 
  # already uploaded, returning the opposite of that to indicate if it
  # needs to be uploaded.
  def app_needs_uploading?(job_data)
    Djinn.log_debug("Seeing if app needs to be uploaded, with " +
      "job data #{job_data.inspect}")
    uac = UserAppClient.new(job_data['@uaserver_ip'], job_data['@secret'])
    needs_uploading = !uac.is_app_uploaded?(job_data['@appid'])
    Djinn.log_debug("Does app #{job_data['@appid']} need uploading? " +
      "#{needs_uploading}")
    return needs_uploading
  end


  # To upload an app to AppScale, just use the AppScale tools
  # TODO(cgb): use the tools as a RubyGem instead of invoking a shell,
  # so we can get better info on failure conditions
  def upload_app(job_data, app_location)
    # TODO(cgb): definitely check the return value of this
    # instead of assuming success
    upload_app_cmd = "/usr/local/appscale-tools/bin/appscale-upload-app"
    Djinn.log_run("#{upload_app_cmd} --file #{app_location} " +
      "--keyname #{job_data['@keyname']} --test")

    Djinn.log_debug("Waiting for the app to start serving")
    uac = UserAppClient.new(job_data['@uaserver_ip'], job_data['@secret'])
    loop {
      hosts = uac.get_hosts_for_app(job_data['@appid'])
      if hosts.length.zero?
        Djinn.log_debug("App is not yet serving")
        sleep(10)
      else
        break
      end
    }
    Djinn.log_debug("app is now serving!")
  end


  # To get the URL that an app can be reached with in AppScale, just find out
  # where the login node is. It provides a app-specific route that will
  # automatically route users to the app.
  def get_app_url(job_data)
    uac = UserAppClient.new(job_data['@uaserver_ip'], job_data['@secret'])
    hosts = uac.get_hosts_for_app(job_data['@appid'])
    Djinn.log_debug("hosts are [#{hosts.join(', ')}]")

    index = rand(hosts.length)
    host = "http://#{hosts[index]}"
    Djinn.log_debug("AppScale app is hosted at #{host}")
    return host
  end


  def engine_name()
    return "AppScale"
  end
end
