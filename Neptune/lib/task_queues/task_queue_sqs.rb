# Programmer: Chris Bunch

require 'helperfunctions'
require 'task_queue'

require 'rubygems'
require 'aws-sdk'
require 'json'


# TaskQueueSQS provides a simple interface (implementing TaskQueue) to Amazon's
# Simple Queue Service (SQS). SQS is externally managed and hosted by Amazon,
# so we don't have to worry about deploying it.
# TODO(cgb): SQS is eventually consistent, so it is possible that we could
# receive the same message twice, and thus execute the same task twice.
class TaskQueueSQS < TaskQueue


  # The access key, provided by AWS, that is required to access SQS.
  attr_accessor :EC2_ACCESS_KEY
  
  
  # The secret key, provided by AWS, that is required to access SQS.
  attr_accessor :EC2_SECRET_KEY


  # The name of this queue. Since we always use our Executor to run tasks,
  # and store task info in SQS, we call it 'executor-sqs'.
  NAME = "executor-sqs"


  # Creates a new SQS queue connection and queue to store / retrieve tasks
  # with, via the AWS RubyGem. We pull in the AWS RubyGem instead of the
  # RightScale AWS RubyGem since the RightScale gem doesn't work with
  # the current version of SQS.
  def initialize(credentials)
    if credentials.class != Hash
      raise BadConfigurationException.new
    end

    if credentials['EC2_ACCESS_KEY'].nil?
      raise BadConfigurationException.new
    end
    @EC2_ACCESS_KEY = credentials['EC2_ACCESS_KEY']

    if credentials['EC2_SECRET_KEY'].nil?
      raise BadConfigurationException.new
    end
    @EC2_SECRET_KEY = credentials['EC2_SECRET_KEY']

    @sqs = AWS::SQS.new(:access_key_id => @EC2_ACCESS_KEY,
      :secret_access_key => @EC2_SECRET_KEY)
    @queue = @sqs.queues.create(TASK_QUEUE_NAME)
  end


  # Stores a Hash in the queue for later processing. Since SQS can't store items
  # in Hash format, we use the JSON library to dump it to a string, which SQS
  # can store.
  def push(item)
    if item.class != Hash
      raise BadConfigurationException.new
    end

    json_item = JSON.dump(item)
    @queue.send_message(json_item)
  end


  # Retrieves an item from the queue, returning the Hash version of the
  # JSON-dumped data. We should be the only ones writing to the queue, but
  # just in case we aren't, we need to validate that the data we're receiving
  # from the queue is data that we can load via JSON.
  # TODO(cgb): Receiving and deleting the message isn't an atomic operation,
  # and since SQS is eventually consistent, could this result in two readers
  # getting the same item? If so, would using a lock on the queue (making the
  # operation atomic) solve the problem?
  def pop()
    json_item = @queue.receive_message()
    return nil if json_item.nil?  # occurs when the queue is empty
    json_item.delete()

    begin
      return JSON.load(json_item.body())
    rescue JSON::ParserError  # if somebody else wrote a non-JSON item
      return pop()
    end
  end


  # Returns all the credentials needed to access this queue. For SQS, it's 
  # just the access key and secret key
  def get_creds()
    return {'@EC2_ACCESS_KEY' => @EC2_ACCESS_KEY,
      '@EC2_SECRET_KEY' => @EC2_SECRET_KEY}
  end


  # Returns the number of messages in the queue, which in SQS is the number
  # of visible messages (there should be no invisible messages since we
  # always immediately delete messages upon receiving them).
  def size()
    return @queue.visible_messages
  end


  # returns a string representation of this queue, which is just the
  # queue name and the credentials
  # TODO(cgb): this seems generic enough to move into TaskQueue, so
  # do so
  def to_s()
    access_key = HelperFunctions.obscure_string(@EC2_ACCESS_KEY)
    secret_key = HelperFunctions.obscure_string(@EC2_SECRET_KEY)
    return "Queue type: SQS, EC2_ACCESS_KEY: #{access_key}, " +
      "EC2_SECRET_KEY: #{secret_key}"
  end
end
