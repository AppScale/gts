# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..", "..", "Neptune")
require 'task_queue'


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
end
