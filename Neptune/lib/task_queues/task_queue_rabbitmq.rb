# Programmer: Chris Bunch

require 'helperfunctions'
require 'task_queue'

require 'rubygems'
require 'json'


class TaskQueueRabbitMQ < TaskQueue


  NAME = "executor-rabbitmq"


  # creates a new RabbitMQ queue via the Bunny RubyGem
  # code mostly adapted from https://github.com/ruby-amqp/bunny
  def initialize(credentials)
    if credentials.class != Hash
      raise BadConfigurationException.new("credentials not a Hash")
    end

    @bunny = Bunny.new(:logging => true)
    @bunny.start

    @queue = @bunny.queue(TASK_QUEUE_NAME)
    @exchange = @bunny.exchange("")
  end


  # stores a hash in the queue for later processing, by converting it to JSON
  def push(item)
    if item.class != Hash
      raise BadConfigurationException.new
    end

    json_item = JSON.dump(item)
    @exchange.publish(json_item, :key => TASK_QUEUE_NAME)
  end


  def pop()
    json_item = @queue.pop()[:payload]
    return nil if json_item == :queue_empty  # occurs when the queue is empty

    item = JSON.load(json_item)
    return item
  end


  # returns all the credentials needed to access this queue
  # TODO(cgb): decide what credentials are necessary
  def get_creds()
    return {}
  end


  # returns the number of messages in the queue
  def size()
    return @queue.message_count
  end


  # returns a string representation of this queue, which is just the
  # queue name and the credentials
  # TODO(cgb): this seems generic enough to move into TaskQueue, so
  # do so
  def to_s()
    return "Queue type: RabbitMQ"
  end
end
