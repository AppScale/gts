# Programmer: Chris Bunch

require 'helperfunctions'
require 'task_queue'

require 'rubygems'
require 'json'


class TaskQueueAzureQueue < TaskQueue
  attr_accessor :AZURE_STORAGE_ACCOUNT_NAME, :AZURE_STORAGE_ACCESS_KEY


  NAME = "executor-azureq"


  # creates a new Azure queue via the WAZ-Queue RubyGem
  def initialize(credentials)
    if credentials.class != Hash
      raise BadConfigurationException.new
    end

    if credentials['AZURE_STORAGE_ACCOUNT_NAME'].nil?
      raise BadConfigurationException.new
    end
    @AZURE_STORAGE_ACCOUNT_NAME = credentials['AZURE_STORAGE_ACCOUNT_NAME']

    if credentials['AZURE_STORAGE_ACCESS_KEY'].nil?
      raise BadConfigurationException.new
    end
    @AZURE_STORAGE_ACCESS_KEY = credentials['AZURE_STORAGE_ACCESS_KEY']

    WAZ::Storage::Base.establish_connection!(:account_name => @AZURE_STORAGE_ACCOUNT_NAME,
      :access_key => @AZURE_STORAGE_ACCESS_KEY, :use_ssl => false)
    @queue = WAZ::Queues::Queue.ensure(TASK_QUEUE_NAME)
  end


  # stores a hash in the queue for later processing, by converting it to JSON
  def push(item)
    if item.class != Hash
      raise BadConfigurationException.new
    end

    json_item = JSON.dump(item)
    @queue.enqueue!(json_item)
  end


  def pop()
    json_item = @queue.lock
    return nil if json_item.nil?  # occurs when the queue is empty
    json_item.destroy!  # TODO(cgb) - maybe delete messages after the task is done

    item = JSON.load(json_item.message_text)
    return item
  end


  # returns all the credentials needed to access this queue
  # for Azure, it's just the account name and access key
  def get_creds()
    return {'@AZURE_STORAGE_ACCOUNT_NAME' => @AZURE_STORAGE_ACCOUNT_NAME,
      '@AZURE_STORAGE_ACCESS_KEY' => @AZURE_STORAGE_ACCESS_KEY}
  end


  # returns the number of messages in the queue
  def size()
    return @queue.size
  end


  # returns a string representation of this queue, which is just the
  # queue name and the credentials
  # TODO(cgb): this seems generic enough to move into TaskQueue, so
  # do so
  def to_s()
    account_name = HelperFunctions.obscure_string(@AZURE_STORAGE_ACCOUNT_NAME)
    access_key = HelperFunctions.obscure_string(@AZURE_STORAGE_ACCESS_KEY)
    return "Queue type: Azure Queue, AZURE_STORAGE_ACCOUNT_NAME: " +
      "#{account_name}, AZURE_STORAGE_ACCESS_KEY: #{access_key}"
  end
end
