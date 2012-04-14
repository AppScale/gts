# Programmer: Chris Bunch


# TaskQueue provides an single interface that Babel uses for its queueing
# system. The interface is intentionally minimalistic, so ensure that the
# widest assortment of queues can be used with Babel.
class TaskQueue


  # Creates a new TaskQueue from the given credentials (a Hash).
  def initialize(credentials)
    raise NotImplementedError.new("TaskQueue initialize is abstract")
  end

  
  # Adds a new item (a Hash) onto the distributed queue.
  def push(item)
    raise NotImplementedError.new("TaskQueue push is abstract")
  end


  # Removes an item off the distributed queue.
  # If there is an item on the queue, pop returns it as a Hash.
  # If the queue is empty, pop returns nil.
  def pop()
    raise NotImplementedError.new("TaskQueue pop is abstract")
  end


  # Returns a human-readable representation of this queue's name and
  # credentials, typically used for logging purposes.
  def to_s()
    raise NotImplementedError.new("TaskQueue to_s is abstract")
  end
end
