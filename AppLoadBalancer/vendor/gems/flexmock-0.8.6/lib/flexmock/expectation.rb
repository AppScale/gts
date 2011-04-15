#!/usr/bin/env ruby

#---
# Copyright 2003, 2004, 2005, 2006, 2007 by Jim Weirich (jim@weirichhouse.org).
# All rights reserved.

# Permission is granted for use, copying, modification, distribution,
# and distribution of modified versions of this work as long as the
# above copyright notice is included.
#+++

require 'flexmock/noop'

class FlexMock
  
  ####################################################################
  # An Expectation is returned from each +should_receive+ message sent
  # to mock object.  Each expectation records how a message matching
  # the message name (argument to +should_receive+) and the argument
  # list (given by +with+) should behave.  Mock expectations can be
  # recorded by chaining the declaration methods defined in this
  # class.
  #
  # For example:
  #
  #   mock.should_receive(:meth).with(args).and_returns(result)
  #
  class Expectation

    attr_reader :expected_args, :order_number
    attr_accessor :mock

    # Create an expectation for a method named +sym+.
    def initialize(mock, sym)
      @mock = mock
      @sym = sym
      @expected_args = nil
      @count_validators = []
      @count_validator_class = ExactCountValidator
      @actual_count = 0
      @return_value = nil
      @return_queue = []
      @yield_queue = []
      @order_number = nil
      @global_order_number = nil
      @globally = nil
    end

    def to_s
      FlexMock.format_args(@sym, @expected_args)
    end

    # Verify the current call with the given arguments matches the
    # expectations recorded in this object.
    def verify_call(*args)
      validate_order
      @actual_count += 1
      perform_yielding(args)
      return_value(args)
    end

    # Public return value (odd name to avoid accidental use as a
    # constraint).
    def _return_value(args) # :nodoc:
      return_value(args)
    end

    # Find the return value for this expectation. (private version)
    def return_value(args)
      case @return_queue.size
      when 0
        block = lambda { |*args| @return_value }
      when 1
        block = @return_queue.first
      else
        block = @return_queue.shift
      end
      block.call(*args)
    end
    private :return_value

    # Yield stored values to any blocks given.
    def perform_yielding(args)
      @return_value = nil
      unless @yield_queue.empty?
        block = args.last
        values = (@yield_queue.size == 1) ? @yield_queue.first : @yield_queue.shift
        if block && block.respond_to?(:call) 
          @return_value = block.call(*values)
        else
          fail MockError, "No Block given to mock with 'and_yield' expectation"
        end
      end
    end
    private :perform_yielding

    # Is this expectation eligible to be called again?  It is eligible
    # only if all of its count validators agree that it is eligible.
    def eligible?
      @count_validators.all? { |v| v.eligible?(@actual_count) }
    end

    # Is this expectation constrained by any call counts?
    def call_count_constrained?
      ! @count_validators.empty?
    end      

    # Validate that the order
    def validate_order
      if @order_number
        @mock.flexmock_validate_order(to_s, @order_number)
      end
      if @global_order_number
        @mock.flexmock_container.flexmock_validate_order(to_s, @global_order_number)
      end
    end
    private :validate_order

    # Validate the correct number of calls have been made.  Called by
    # the teardown process.
    def flexmock_verify
      @count_validators.each do |v|
        v.validate(@actual_count)
      end
    end

    # Does the argument list match this expectation's argument
    # specification.
    def match_args(args)
      # TODO: Rethink this:
      # return false if @expected_args.nil?
      return true if @expected_args.nil?
      return false if args.size != @expected_args.size
      (0...args.size).all? { |i| match_arg(@expected_args[i], args[i]) }
    end

    # Does the expected argument match the corresponding actual value.
    def match_arg(expected, actual)
      expected === actual ||
      expected == actual ||
      ( Regexp === expected && expected === actual.to_s )
    end

    # Declare that the method should expect the given argument list.
    def with(*args)
      @expected_args = args
      self
    end

    # Declare that the method should be called with no arguments.
    def with_no_args
      with
    end

    # Declare that the method can be called with any number of
    # arguments of any type.
    def with_any_args
      @expected_args = nil
      self
    end

    # :call-seq:
    #   and_return(value)
    #   and_return(value, value, ...)
    #   and_return { |*args| code }
    #
    # Declare that the method returns a particular value (when the
    # argument list is matched).
    #
    # * If a single value is given, it will be returned for all matching
    #   calls.
    # * If multiple values are given, each value will be returned in turn for
    #   each successive call.  If the number of matching calls is greater
    #   than the number of values, the last value will be returned for
    #   the extra matching calls.
    # * If a block is given, it is evaluated on each call and its
    #   value is returned.
    #
    # For example:
    #
    #  mock.should_receive(:f).returns(12)   # returns 12
    #
    #  mock.should_receive(:f).with(String). # returns an
    #    returns { |str| str.upcase }        # upcased string
    #
    # +returns+ is an alias for +and_return+.
    #
    def and_return(*args, &block)
      if block_given? 
        @return_queue << block
      else
        args.each do |arg|
          @return_queue << lambda { |*a| arg }
        end
      end
      self
    end
    alias :returns :and_return  # :nodoc:

    # Declare that the method returns and undefined object
    # (FlexMock.undefined).  Since the undefined object will always
    # return itself for any message sent to it, it is a good "I don't
    # care" value to return for methods that are commonly used in
    # method chains.
    #
    # For example, if m.foo returns the undefined object, then:
    #
    #    m.foo.bar.baz
    #
    # returns the undefined object without throwing an exception.
    #
    def and_return_undefined
      and_return(FlexMock.undefined)
    end
    alias :returns_undefined :and_return_undefined

    # :call-seq:
    #   and_yield(value1, value2, ...)
    #
    # Declare that the mocked method is expected to be given a block
    # and that the block will be called with the values supplied to
    # yield.  If the mock is called multiple times, mulitple
    # <tt>and_yield</tt> declarations can be used to supply different
    # values on each call.
    #
    # An error is raised if the mocked method is not called with a
    # block.
    def and_yield(*yield_values)
      @yield_queue << yield_values
    end
    alias :yields :and_yield

    
    # :call-seq:
    #   and_raise(an_exception)
    #   and_raise(SomeException)
    #   and_raise(SomeException, args, ...)
    #
    # Declares that the method will raise the given exception (with
    # an optional message) when executed.
    #
    # * If an exception instance is given, then that instance will be
    #   raised.
    #   
    # * If an exception class is given, the exception raised with be
    #   an instance of that class constructed with +new+.  Any
    #   additional arguments in the argument list will be passed to
    #   the +new+ constructor when it is invoked.
    #   
    # +raises+ is an alias for +and_raise+.
    #
    def and_raise(exception, *args)
      and_return { raise exception, *args }
    end
    alias :raises :and_raise

    # :call-seq:
    #   and_throw(a_symbol)
    #   and_throw(a_symbol, value)
    #
    # Declares that the method will throw the given symbol (with an
    # optional value) when executed.
    #
    # +throws+ is an alias for +and_throw+.
    #
    def and_throw(sym, value=nil)
      and_return { throw sym, value }
    end
    alias :throws :and_throw

    # Declare that the method may be called any number of times.
    def zero_or_more_times
      at_least.never
    end

    # Declare that the method is called +limit+ times with the
    # declared argument list.  This may be modified by the +at_least+
    # and +at_most+ declarators.
    def times(limit)
      @count_validators << @count_validator_class.new(self, limit) unless limit.nil?
      @count_validator_class = ExactCountValidator
      self
    end

    # Declare that the method is never expected to be called with the
    # given argument list.  This may be modified by the +at_least+ and
    # +at_most+ declarators.
    def never
      times(0)
    end

    # Declare that the method is expected to be called exactly once
    # with the given argument list.  This may be modified by the
    # +at_least+ and +at_most+ declarators.
    def once
      times(1)
    end

    # Declare that the method is expected to be called exactly twice
    # with the given argument list.  This may be modified by the
    # +at_least+ and +at_most+ declarators.
    def twice
      times(2)
    end

    # Modifies the next call count declarator (+times+, +never+,
    # +once+ or +twice+) so that the declarator means the method is
    # called at least that many times.
    #
    # E.g. method f must be called at least twice:
    #
    #   mock.should_receive(:f).at_least.twice
    #
    def at_least
      @count_validator_class = AtLeastCountValidator
      self
    end

    # Modifies the next call count declarator (+times+, +never+,
    # +once+ or +twice+) so that the declarator means the method is
    # called at most that many times.
    #
    # E.g. method f must be called no more than twice
    #
    #   mock.should_receive(:f).at_most.twice
    #
    def at_most
      @count_validator_class = AtMostCountValidator
      self
    end

    # Declare that the given method must be called in order.  All
    # ordered method calls must be received in the order specified by
    # the ordering of the +should_receive+ messages.  Receiving a
    # methods out of the specified order will cause a test failure.
    #
    # If the user needs more fine control over ordering
    # (e.g. specifying that a group of messages may be received in any
    # order as long as they all come after another group of messages),
    # a _group_ _name_ may be specified in the +ordered+ calls.  All
    # messages within the same group may be received in any order.
    #
    # For example, in the following, messages +flip+ and +flop+ may be
    # received in any order (because they are in the same group), but
    # must occur strictly after +start+ but before +end+.  The message
    # +any_time+ may be received at any time because it is not
    # ordered.
    #
    #    m = FlexMock.new
    #    m.should_receive(:any_time)
    #    m.should_receive(:start).ordered
    #    m.should_receive(:flip).ordered(:flip_flop_group)
    #    m.should_receive(:flop).ordered(:flip_flop_group)
    #    m.should_receive(:end).ordered
    #
    def ordered(group_name=nil)
      if @globally
        @global_order_number = define_ordered(group_name, @mock.flexmock_container)
      else
        @order_number = define_ordered(group_name, @mock)
      end
      @globally = false
      self
    end

    # Modifier that changes the next ordered constraint to apply
    # globally across all mock objects in the container.
    def globally
      @globally = true
      self
    end

    # Helper method for defining ordered expectations.
    def define_ordered(group_name, ordering)
      fail UsageError, "Mock #{@mock.flexmock_name} is not in a container and cannot be globally ordered." if ordering.nil?
      if group_name.nil?
         result = ordering.flexmock_allocate_order
      elsif (num = ordering.flexmock_groups[group_name])
        result = num
      else
        result = ordering.flexmock_allocate_order
        ordering.flexmock_groups[group_name] = result
      end
      result
    end
    private :define_ordered

    def by_default
      expectations = mock.flexmock_expectations_for(@sym)
      expectations.defaultify_expectation(self) if expectations
    end

  end

  ##########################################################################
  # A composite expectation allows several expectations to be grouped into a
  # single composite and then apply the same constraints to  all expectations
  # in the group.
  class CompositeExpectation

    # Initialize the composite expectation.
    def initialize
      @expectations = []
    end

    # Add an expectation to the composite.
    def add(expectation)
      @expectations << expectation
    end

    # Apply the constraint method to all expectations in the composite.
    def method_missing(sym, *args, &block)
      @expectations.each do |expectation|
        expectation.send(sym, *args, &block)
      end
      self
    end

    # The following methods return a value, so we make an arbitrary choice
    # and return the value for the first expectation in the composite.
    
    # Return the order number of the first expectation in the list.
    def order_number
      @expectations.first.order_number
    end

    # Return the associated mock object.
    def mock
      @expectations.first.mock
    end
    
    # Start a new method expectation.  The following constraints will be
    # applied to the new expectation.
    def should_receive(*args, &block)
      @expectations.first.mock.should_receive(*args, &block)
    end

    # Return a string representations
    def to_s
      if @expectations.size > 1
        "[" + @expectations.collect { |e| e.to_s }.join(', ') + "]"
      else
        @expectations.first.to_s
      end
    end
  end

  ##########################################################################
  # An expectation recorder records any expectations received and plays them
  # back on demand.  This is used to collect the expectations in the blockless
  # version of the new_instances call.
  #
  class ExpectationRecorder

    # Initialize the recorder.
    def initialize
      @expectations = []
    end

    # Save any incoming messages to be played back later.
    def method_missing(sym, *args, &block)
      @expectations << [sym, args, block]
      self
    end
    
    # Apply the recorded messages to the given object in a chaining fashion
    # (i.e. the result of the previous call is used as the target of the next
    # call).
    def apply(mock)
      obj = mock
      @expectations.each do |sym, args, block|
        obj = obj.send(sym, *args, &block)
      end
    end
  end
end
