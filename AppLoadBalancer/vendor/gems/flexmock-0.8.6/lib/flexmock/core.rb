#!/usr/bin/env ruby

#---
# Copyright 2003, 2004, 2005, 2006, 2007 by Jim Weirich (jim@weirichhouse.org).
# All rights reserved.
#
# Permission is granted for use, copying, modification, distribution,
# and distribution of modified versions of this work as long as the
# above copyright notice is included.
#+++

require 'flexmock/errors'
require 'flexmock/composite'
require 'flexmock/ordering'

######################################################################
# FlexMock is a flexible mock object framework for supporting testing.
#
# FlexMock has a simple interface that's easy to remember, and leaves 
# the hard stuff to all those other mock object implementations.
#
# Basic Usage:
#
#   m = flexmock("name")
#   m.should_receive(:upcase).with("stuff").
#     and_return("STUFF")
#   m.should_receive(:downcase).with(String).
#     and_return { |s| s.downcase }.once
#
# With Test::Unit Integration:
#
#   class TestSomething < Test::Unit::TestCase
#     include FlexMock::TestCase
#
#     def test_something
#       m = flexmock("name")
#       m.should_receive(:hi).and_return("Hello")
#       m.hi
#     end
#   end
#
# Note: When using Test::Unit integeration, don't forget to include
# FlexMock::TestCase.  Also, if you override +teardown+, make sure you
# call +super+.
#
class FlexMock
  include Ordering

  attr_reader :flexmock_name
  attr_accessor :flexmock_container

  # Create a FlexMock object with the given name.  The name is used in
  # error messages.  If no container is given, create a new, one-off
  # container for this mock.
  def initialize(name="unknown", container=nil)
    @flexmock_name = name
    @expectations = Hash.new
    @ignore_missing = false
    @verified = false
    container = UseContainer.new if container.nil?
    container.flexmock_remember(self)
  end

  # Return the inspection string for a mock.
  def inspect
    "<FlexMock:#{flexmock_name}>"
  end

  # Verify that each method that had an explicit expected count was
  # actually called that many times.
  def flexmock_verify
    return if @verified
    @verified = true
    flexmock_wrap do
      @expectations.each do |sym, handler|
        handler.flexmock_verify
      end
    end
  end

  # Teardown and infrastructure setup for this mock.
  def flexmock_teardown
  end

  # Ignore all undefined (missing) method calls.
  def should_ignore_missing
    @ignore_missing = true
  end
  alias mock_ignore_missing should_ignore_missing

  def by_default
    @last_expectation.by_default
    self
  end

  # Handle missing methods by attempting to look up a handler.
  def method_missing(sym, *args, &block)
    flexmock_wrap do
      if handler = @expectations[sym]
        args << block  if block_given?
        handler.call(*args)
      elsif @ignore_missing
        FlexMock.undefined
      else
        super(sym, *args, &block)
      end
    end
  end

  # Save the original definition of respond_to? for use a bit later.
  alias flexmock_respond_to? respond_to?

  # Override the built-in respond_to? to include the mocked methods.
  def respond_to?(sym, *args)
    super || (@expectations[sym] ? true : @ignore_missing)
  end

  # Find the mock expectation for method sym and arguments.
  def flexmock_find_expectation(method_name, *args) # :nodoc:
    exp = @expectations[method_name]
    exp ? exp.find_expectation(*args) : nil
  end

  # Return the expectation director for a method name.
  def flexmock_expectations_for(method_name) # :nodoc:
    @expectations[method_name]
  end

  # Override the built-in +method+ to include the mocked methods.
  def method(sym)
    @expectations[sym] || super
  rescue NameError => ex
    if @ignore_missing
      proc { FlexMock.undefined }
    else
      raise ex
    end
  end

  # :call-seq:
  #    mock.should_receive(:method_name)
  #    mock.should_receive(:method1, method2, ...)
  #    mock.should_receive(:meth1 => result1, :meth2 => result2, ...)
  #
  # Declare that the mock object should receive a message with the given name.
  #
  # If more than one method name is given, then the mock object should expect
  # to receive all the listed melthods.  If a hash of method name/value pairs
  # is given, then the each method will return the associated result.  Any
  # expectations applied to the result of +should_receive+ will be applied to
  # all the methods defined in the argument list.
  #
  # An expectation object for the method name is returned as the result of
  # this method.  Further expectation constraints can be added by chaining to
  # the result.
  #
  # See Expectation for a list of declarators that can be used.
  #
  def should_receive(*args)
    @last_expectation = ContainerHelper.parse_should_args(self, args) do |sym|
      @expectations[sym] ||= ExpectationDirector.new(sym)
      result = Expectation.new(self, sym)
      @expectations[sym] << result
      override_existing_method(sym) if flexmock_respond_to?(sym)
      result
    end
    @last_expectation
  end
  
  # Declare that the mock object should expect methods by providing a
  # recorder for the methods and having the user invoke the expected
  # methods in a block.  Further expectations may be applied the
  # result of the recording call.
  #
  # Example Usage:
  #
  #   mock.should_expect do |record|
  #     record.add(Integer, 4) { |a, b|
  #       a + b
  #     }.at_least.once
  #
  def should_expect
    yield Recorder.new(self)
  end

  private

  # Wrap a block of code so the any assertion errors are wrapped so
  # that the mock name is added to the error message .
  def flexmock_wrap(&block)
    yield
  rescue FlexMock.framework_adapter.assertion_failed_error => ex
    raise FlexMock.framework_adapter.assertion_failed_error,
    "in mock '#{@flexmock_name}': #{ex.message}",
    ex.backtrace
  end
  
  
  # Override the existing definition of method +sym+ in the mock.
  # Most methods depend on the method_missing trick to be invoked.
  # However, if the method already exists, it will not call
  # method_missing.  This method defines a singleton method on the
  # mock to explicitly invoke the method_missing logic.
  def override_existing_method(sym)
    sclass.class_eval <<-EOS
      def #{sym}(*args, &block)
        method_missing(:#{sym}, *args, &block)
      end
    EOS
  end

  # Return the singleton class of the mock object.
  def sclass
    class << self; self; end
  end
end

require 'flexmock/core_class_methods'
