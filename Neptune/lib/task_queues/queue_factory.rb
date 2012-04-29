# Programmer: Chris Bunch

$:.unshift File.join(File.dirname(__FILE__))
require 'task_queue_azure_queue'
require 'task_queue_google_app_engine'
require 'task_queue_rabbitmq'
require 'task_queue_sqs'


# QueueFactory provides users with a single way to get a TaskQueue that operates
# on any cloud. All TaskQueues that this factory supports conform to the
# interface that TaskQueue provides.
module QueueFactory
  def self.get_queue(name, job_data)
    case name
    when TaskQueueAzureQueue::NAME
      creds = {'AZURE_STORAGE_ACCOUNT_NAME' => job_data['@AZURE_STORAGE_ACCOUNT_NAME'],
        'AZURE_STORAGE_ACCESS_KEY' => job_data['@AZURE_STORAGE_ACCESS_KEY']}
      return TaskQueueAzureQueue.new(creds)
    when "executor-appengine-pull-q"
      # The App Engine pull queue may require an App Engine app to be uploaded,
      # which could require the storage parameters, so just pass in all the job
      # data to be safe.
      return TaskQueueGoogleAppEngine.new(job_data)
    when TaskQueueRabbitMQ::NAME
      creds = {}
      return TaskQueueRabbitMQ.new(creds)
    when TaskQueueSQS::NAME
      creds = {'EC2_ACCESS_KEY' => job_data['@EC2_ACCESS_KEY'],
        'EC2_SECRET_KEY' => job_data['@EC2_SECRET_KEY']}
      return TaskQueueSQS.new(creds)
    else
      raise NotImplementedError
    end
  end
end
