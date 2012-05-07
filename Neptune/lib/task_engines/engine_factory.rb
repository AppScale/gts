# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..", "..")
require 'neptune_manager'


$:.unshift File.join(File.dirname(__FILE__))
require 'task_engine_google_app_engine'
require 'task_engine_appscale'


# The EngineFactory follows the Factory design pattern (more or less) to
# provide callers with one way to get access to different task engines.
# These engines always provide access to remote systems - that is, where
# tasks themselves are not run by our Executor.
module EngineFactory
  def self.get_engine(engine, job_data)
    case engine
    when TaskEngineGoogleAppEngine::NAME
      creds = {'appid' => job_data['@appid'], 
        'appcfg_cookies' => job_data['@appcfg_cookies'],
        'function' => job_data['@function']}
      return TaskEngineGoogleAppEngine.new(creds)
    when TaskEngineAppScale::NAME
      # Since using the AppScale push queue requires a Cicero
      # job to be dispatched, it will need all the job data
      # we have
      return TaskEngineAppScale.new(job_data)
    else
      NeptuneManager.log("#{engine} is not a supported engine")
      raise NotImplementedError
    end
  end
end
