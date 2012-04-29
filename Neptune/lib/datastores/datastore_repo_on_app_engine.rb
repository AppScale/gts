# Programmer: Chris Bunch


require 'datastore_repo'


$:.unshift File.join(File.dirname(__FILE__), "..", "..", "Neptune")
require 'task_engine_google_app_engine'


# An implementation of the Repository app that assumes it is running
# within App Engine. Since App Engine is a remote service, we have to check
# to see if it's running or not, and upload it when it's not running.
class DatastoreRepoOnAppEngine < DatastoreRepo

  
  # The host (IP, colon, port) that the Repo app is hosted at.
  attr_accessor :host


  # The name of this datastore, which we call AppDB since Neptune jobs
  # basically use it as an interface to AppScale's database agnostic
  # layer.
  NAME = "repo-appengine"

  
  # Creates a new connection to the Repo running on Google App Engine.
  # Deployments take a non-trivial amount of time and can often be avoided, so
  # see if our app is running on App Engine before trying to re-upload it.
  def initialize(credentials)
    if credentials.class != Hash
      raise BadConfigurationException.new("Credentials was not a Hash")
    end

    if credentials['@appid'].nil?
      raise BadConfigurationException.new("No @appid was provided")
    end

    if credentials['@appcfg_cookies'].nil?
      raise BadConfigurationException.new("No @appcfg_cookies was provided")
    end

    appid = credentials['@appid']
    @host = "#{appid}.appspot.com"

    if !is_app_running?()
      app_location = "/root/appscale/AppServer/demos/therepo/"
      TaskEngineGoogleAppEngine.upload_app(credentials, app_location)
    end
  end


  # Sees if the Repo application is running at the @host we've set for it.
  def is_app_running?()
    result = do_http_get_for_get("/any-path", "any-type")
    if result
      NeptuneManager.log("App appears to be running")
      return true
    else
      NeptuneManager.log("App isn't running")
      return false
    end
  end


end
