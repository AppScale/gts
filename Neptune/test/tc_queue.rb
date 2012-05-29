# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..", "..", "Neptune")
require 'task_queue'
require 'task_queue_sqs'


require 'rubygems'
require 'flexmock/test_unit'


class TestTaskQueue < Test::Unit::TestCase
  def setup
    flexmock(Kernel).should_receive(:puts).and_return()
  end
  
  def test_generic_queue_methods_are_abstract
    credentials = {}
    assert_raises(NotImplementedError) { TaskQueue.new(credentials) }
  end

  def test_task_queue_sqs
    string_creds = ""
    assert_raises(BadConfigurationException) {
      TaskQueueSQS.new(string_creds)
    }

    empty_credentials = {}
    assert_raises(BadConfigurationException) { 
      TaskQueueSQS.new(empty_credentials)
    }

    incomplete_creds = {'EC2_ACCESS_KEY' => 'baz'}
    assert_raises(BadConfigurationException) { 
      TaskQueueSQS.new(incomplete_creds) 
    }

    item = {'a' => 'b'}
    str_item = '{"a":"b"}'

    flexmock(AWS::SQS::QueueCollection).new_instances { |instance|
      instance.should_receive(:create).and_return(flexmock(:send_message => nil, 
        :receive_message => flexmock(:body => str_item, :delete => nil)))
    }

    full_credentials = {'EC2_ACCESS_KEY' => 'boo', 'EC2_SECRET_KEY' => 'baz'}
    q = TaskQueueSQS.new(full_credentials)
    assert_equal('boo', q.EC2_ACCESS_KEY)
    assert_equal('baz', q.EC2_SECRET_KEY)

    q.push(item)
    item2 = q.pop()
    assert_equal(item, item2)
  end

  def test_task_queue_sqs_gives_bad_info
    # Don't assume that we can always trust what SQS gives us - it may not
    # always JSON-able.

    item1 = "abcd"  # not JSON-able
    item2 = "true"  # is JSON-able

    a = flexmock("baz")
    a.should_receive(:body).times(2).and_return(item1, item2)
    a.should_receive(:delete).and_return()

    flexmock(AWS::SQS::QueueCollection).new_instances { |instance|
      instance.should_receive(:create).and_return(flexmock(:send_message => nil, 
        :receive_message => a))
    }

    full_credentials = {'EC2_ACCESS_KEY' => 'boo', 'EC2_SECRET_KEY' => 'baz'}
    q = TaskQueueSQS.new(full_credentials)

    q.pop()
  end

end
