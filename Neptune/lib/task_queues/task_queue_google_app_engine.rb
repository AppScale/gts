# Programmer: Chris Bunch

require 'helperfunctions'
require 'task_queue'

# The App Engine task engine has a function that uploads an app to Google
# App Engine, and since we need this to upload our pull queue frontend,
# we pull in support for it here.
require 'task_engine_google_app_engine'

require 'json'

require 'rubygems'
require 'httparty'


class GoogleAppEnginePullQueue
  include HTTParty

  # Our App Engine app responds to everything in JSON, so just
  # process it here - pretty cool!
  parser(
    Proc.new do |body, format|
      JSON.load(body)
    end
  )

end


class TaskQueueGoogleAppEngine < TaskQueue
  

  NAME = "executor-appengine-pull-q"


  # creates a new App Engine queue via the gtaskqueue executable
  def initialize(credentials)
    if credentials.class != Hash
      raise BadConfigurationException.new
    end
    @credentials = credentials

    if credentials['@appid'].nil?
      raise BadConfigurationException.new
    end
    @appid = credentials['@appid']
    
    if credentials['@appcfg_cookies'].nil?
      raise BadConfigurationException.new
    end
    @appcfg_cookies = credentials['@appcfg_cookies']

    # The App Engine pull queue interface we use is an App Engine app, so make
    # sure that the app is already in App Engine, and if not, upload it.
    if !is_pull_queue_app_running?
      app_location = '/root/appscale/AppServer/demos/pullqueueapp'
      TaskEngineGoogleAppEngine.upload_app(credentials, app_location)
      wait_for_app_to_start_serving
    end
  end


  # stores a hash in the queue for later processing, by converting it to JSON
  # and pushing it to our app engine app
  def push(item)
    if item.class != Hash
      raise BadConfigurationException.new
    end
    payload = JSON.dump(item)

    host = "http://#{@appid}.appspot.com"
    begin
      Djinn.log_debug("trying a PUT on /task")
      # PUT requests require a Content-Length header in App Engine, so
      # set an empty body and httparty will add that header in
      result = GoogleAppEnginePullQueue.put("#{host}/task", :body => '', :query => {:payload => payload})
      if result['ok']
        Djinn.log_debug("#{host} is up - push succeeded")
      else
        Djinn.log_debug("#{host} is up but push did not succeed, " +
          "returning #{result.inspect}")
      end
    rescue NoMethodError  # if the host is down
      Djinn.log_debug("#{host} is down, returning on push")
    end
  end


  def pop()
    host = "http://#{@appid}.appspot.com"

    begin
      Djinn.log_debug("trying a GET on /task")
      task = GoogleAppEnginePullQueue.get("#{host}/task")
      Djinn.log_debug("#{host} is up and returned a task with payload: #{task}")
      return task
    rescue NoMethodError  # if the host is down
      Djinn.log_debug("#{host} is down, returning nil")
      return nil
    end
  end


  # returns all the credentials needed to access this queue
  # for App Engine, it's all the job data, since we may have to
  # upload the app
  def get_creds()
    return @credentials
  end


  # returns the number of messages in the queue
  # Our App Engine app has a special route just for this, with
  # a counter that is associated with the size of the queue
  def size()
    host = "http://#{@appid}.appspot.com"

    begin
      Djinn.log_debug("trying a GET on /size")
      result = GoogleAppEnginePullQueue.get("#{host}/size")
      size = result['size']
      Djinn.log_debug("#{host} is up and returned a size of #{size}")
      return size
    rescue NoMethodError  # if the host is down
      Djinn.log_debug("#{host} is down, returning 0")
      return 0
    end
  end


  # returns a string representation of this queue, which is just the
  # queue name and the credentials
  # TODO(cgb): this seems generic enough to move into TaskQueue, so
  # do so
  def to_s()
    return "Queue type: Google App Engine, app id: #{@appid}, " +
      "appcfg_cookies: #{@appcfg_cookies}"
  end

  def is_pull_queue_app_running?()
    host = "http://#{@appid}.appspot.com"

    begin
      Djinn.log_debug("trying a GET on /supportspullqueue")
      result = GoogleAppEnginePullQueue.get("#{host}/supportspullqueue")
      Djinn.log_debug("#{host} returned [#{result}]")
      if result == true
        Djinn.log_debug("the currently running app supports pull queues")
        return true
      else
        Djinn.log_debug("the currently running app does not support pull queues")
        return false
      end
    rescue NoMethodError  # if the host is down or doesn't have the right route
      Djinn.log_debug("#{host} did not return a 200, so returning false")
      return false
    end
  end

  def wait_for_app_to_start_serving()
    host = "http://#{@appid}.appspot.com"
    Djinn.log_debug("waiting for app to start serving")
    loop {
      if is_pull_queue_app_running?
        Djinn.log_debug("app is now serving!")
        break
      else
        Djinn.log_debug("app is not yet serving")
        sleep(10)
      end
    }
  end
end
