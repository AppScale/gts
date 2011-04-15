#!/usr/bin/env ruby

#---
# Copyright 2003, 2004, 2005, 2006, 2007 by Jim Weirich (jim@weirichhouse.org).
# All rights reserved.

# Permission is granted for use, copying, modification, distribution,
# and distribution of modified versions of this work as long as the
# above copyright notice is included.
#+++

require 'flexmock/noop'
require 'flexmock/argument_types'
require 'flexmock/ordering'

class FlexMock
  
  # ######################################################################
  # Mock container methods
  #
  # Include this module in to get integration with FlexMock.  When this module
  # is included, mocks may be created with a simple call to the +flexmock+
  # method.  Mocks created with via the method call will automatically be
  # verified in the teardown of the test case.
  #   
  module MockContainer
    include Ordering

    # Do the flexmock specific teardown stuff.  If you need finer control,
    # you can use either +flexmock_verify+ or +flexmock_close+.
    def flexmock_teardown
      flexmock_verify if passed?
    ensure
      flexmock_close
    end

    # Perform verification on all mocks in the container.
    def flexmock_verify
      @flexmock_created_mocks ||= []
      @flexmock_created_mocks.each do |m|
        m.flexmock_verify
      end
    end
    
    # Close all the mock objects in the container.  Closing a mock object
    # restores any original behavior that was displaced by the mock.
    def flexmock_close
      @flexmock_created_mocks ||= []
      @flexmock_created_mocks.each do |m|
        m.flexmock_teardown
      end
      @flexmock_created_mocks = []
    end
    
    # Create a mocking object in the FlexMock framework.  The +flexmock+
    # method has a number of options available, depending on just what kind of
    # mocking object your require.  Mocks created via +flexmock+ will be
    # automatically verify during the teardown phase of your test framework.
    #
    # :call-seq:
    #   flexmock() { |mock| ... }
    #   flexmock(name) { |mock| ... }
    #   flexmock(expect_hash) { |mock| ... }
    #   flexmock(name, expect_hash) { |mock| ... }
    #   flexmock(real_object) { |mock| ... }
    #   flexmock(real_object, name) { |mock| ... }
    #   flexmock(real_object, name, expect_hash) { |mock| ... }
    #   flexmock(:base, string, name, expect_hash) { |mock| ... }
    #
    # <b>Note:</b> A plain flexmock() call without a block will return the
    # mock object (the object that interprets <tt>should_receive</tt> and its
    # brethern). A flexmock() call that _includes_ a block will return the
    # domain objects (the object that will interpret domain messages) since
    # the mock will be passed to the block for configuration. With regular
    # mocks, this distinction is unimportant because the mock object and the
    # domain object are the same object.  However, with partial mocks, the
    # mock object is separation from the domain object.  Keep that distinciton
    # in mind.
    #
    # name ::
    #   Name of the mock object.  If no name is given, "unknown" is used for
    #   full mocks and "flexmock(<em>real_object</em>)" is used for partial
    #   mocks.
    #
    # expect_hash ::
    #   Hash table of method names and values.  Each method/value pair is 
    #   used to setup a simple expectation so that if the mock object
    #   receives a message matching an entry in the table, it returns 
    #   the associated value.  No argument our call count constraints are
    #   added.  Using an expect_hash is identical to calling:
    #
    #       mock.should_receive(method_name).and_return(value)
    #
    #   for each of the method/value pairs in the hash.
    #
    # real_object ::
    #   If a real object is given, then a partial mock is constructed 
    #   using the real_object as a base. Partial mocks (formally referred 
    #   to as stubs) behave as a mock object when an expectation is matched, 
    #   and otherwise will behave like the original object.  This is useful 
    #   when you want to use a real object for testing, but need to mock out 
    #   just one or two methods.  
    #
    # :base ::
    #   Forces the following argument to be used as the base of a
    #   partial mock object.  This explicit tag is only needed if you 
    #   want to use a string or a symbol as the mock base (string and
    #   symbols would normally be interpretted as the mock name).
    #       
    # &block ::
    #   If a block is given, then the mock object is passed to the block and
    #   expectations may be configured within the block.  When a block is given
    #   for a partial mock, flexmock will return the domain object rather than 
    #   the mock object.  
    #
    def flexmock(*args)
      name = nil
      quick_defs = {}
      domain_obj = nil
      safe_mode = false
      model_class = nil
      while ! args.empty?
        case args.first
        when :base, :safe
          safe_mode = (args.shift == :safe)
          domain_obj = args.shift
        when :model
          args.shift
          model_class = args.shift
        when String, Symbol
          name = args.shift.to_s
        when Hash
          quick_defs = args.shift
        else
          domain_obj = args.shift
        end
      end
      raise UsageError, "a block is required in safe mode" if safe_mode && ! block_given?

      if domain_obj
        mock = ContainerHelper.make_partial_proxy(self, domain_obj, name, safe_mode)
        result = domain_obj
      elsif model_class
        id = ContainerHelper.next_id
        result = mock = FlexMock.new("#{model_class}_#{id}", self)
      else
        result = mock = FlexMock.new(name || "unknown", self)
      end
      mock.should_receive(quick_defs)
      yield(mock) if block_given?
      flexmock_remember(mock)
      ContainerHelper.add_model_methods(mock, model_class, id) if model_class
      result
    end
    alias flexstub flexmock
    
    # Remember the mock object / stub in the mock container.
    def flexmock_remember(mocking_object)
      @flexmock_created_mocks ||= []
      @flexmock_created_mocks << mocking_object
      mocking_object.flexmock_container = self
      mocking_object
    end
  end

  # #################################################################
  # Helper methods for mock containers.  MockContainer is a module
  # that is designed to be mixed into other classes, particularly
  # testing framework test cases.  Since we don't want to pollute the
  # method namespace of the class that mixes in MockContainer, a
  # number of MockContainer methods were moved into ContainerHelper to
  # to isoloate the names.
  #
  class MockContainerHelper
    include FlexMock::ArgumentTypes

    # Return the next id for mocked models.
    def next_id
      @id_counter ||= 10000
      @id_counter += 1
    end

    # :call-seq:
    #   parse_should_args(args) { |symbol| ... }
    #
    # This method provides common handling for the various should_receive
    # argument lists. It sorts out the differences between symbols, arrays and
    # hashes, and identifies the method names specified by each.  As each
    # method name is identified, create a mock expectation for it using the
    # supplied block.
    def parse_should_args(mock, args, &block)  # :nodoc:
      result = CompositeExpectation.new
      args.each do |arg|
        case arg
        when Hash
          arg.each do |k,v|
            exp = build_demeter_chain(mock, k, &block).and_return(v)
            result.add(exp)
          end
        when Symbol, String
          result.add(build_demeter_chain(mock, arg, &block))
        end
      end
      result
    end

    # Automatically add mocks for some common methods in ActiveRecord
    # models.
    def add_model_methods(mock, model_class, id)
      container = mock.flexmock_container

      mock_errors = container.flexmock("errors")
      mock_errors.should_receive(:count).and_return(0).by_default
      mock_errors.should_receive(:full_messages).and_return([]).by_default

      mock.should_receive(:id).and_return(id).by_default
      mock.should_receive(:to_params).and_return(id.to_s).by_default
      mock.should_receive(:new_record?).and_return(false).by_default
      mock.should_receive(:class).and_return(model_class).by_default
      mock.should_receive(:errors).and_return(mock_errors).by_default

      # HACK: Ruby 1.9 needs the following lambda so that model_class
      # is correctly bound below.
      lambda { }
      mock.should_receive(:is_a?).with(any).and_return { |other|
        other == model_class
      }.by_default
      mock.should_receive(:instance_of?).with(any).and_return { |other|
        other == model_class
      }.by_default
      mock.should_receive(:kind_of?).with(any).and_return { |other|
        model_class.ancestors.include?(other)
      }.by_default
    end

    # Create a PartialMockProxy for the given object.  Use +name+ as
    # the name of the mock object.
    def make_partial_proxy(container, obj, name, safe_mode)
      name ||= "flexmock(#{obj.class.to_s})"
      obj.instance_eval {
        mock = FlexMock.new(name, container)
        @flexmock_proxy ||= PartialMockProxy.new(obj, mock, safe_mode)
      }
      obj.instance_variable_get("@flexmock_proxy")
    end

    private
    
    # Build the chain of mocks for demeter style mocking.
    #
    # Warning: Nasty code ahead.
    #
    # This method builds a chain of mocks to support demeter style
    # mocking.  Given a mock chain of "first.second.third.last", we
    # must build a chain of mock methods that return the next mock in
    # the chain.  The expectation for the last method of the chain is
    # returned as the result of the method.
    #
    # Things to consider:
    #
    # (1) The expectation for the "first" method must be created by
    # the proper mechanism, which is supplied by the block parameter
    # "block".  In other words, first expectation is created by
    # calling the block.  (This allows us to create expectations on
    # both pure mocks and partial mocks, with the block handling the
    # details).
    #
    # (2) Although the first mock is arbitrary, the remaining mocks in
    # the chain will always be pure mocks created specifically for
    # this purpose.
    #
    # (3) The expectations for all methods but the last in the chain
    # will be setup to expect no parameters and to return the next
    # mock in the chain.
    #
    # (4) It could very well be the case that several demeter chains
    # will be defined on a single mock object, and those chains could
    # share some of the same methods (e.g. "mock.one.two.read" and
    # "mock.one.two.write" both share the methods "one" and "two").
    # It is important that the shared methods return the same mocks in
    # both chains.
    #
    def build_demeter_chain(mock, arg, &block)
      container = mock.flexmock_container
      names = arg.to_s.split('.')
      check_method_names(names)
      exp = nil
      next_exp = lambda { |n| block.call(n) }
      loop do
        method_name = names.shift.to_sym
        exp = mock.flexmock_find_expectation(method_name)
        need_new_exp = exp.nil? || names.empty?
        exp = next_exp.call(method_name) if need_new_exp
        break if names.empty?
        if need_new_exp
          mock = container.flexmock("demeter_#{method_name}")
          exp.with_no_args.and_return(mock)
        else
          mock = exp._return_value([])
        end
        check_proper_mock(mock, method_name)
        next_exp = lambda { |n| mock.should_receive(n) }
      end
      exp
    end
    
    # Check that the given mock is a real FlexMock mock.
    def check_proper_mock(mock, method_name)
      unless mock.kind_of?(FlexMock)
        fail FlexMock::UsageError,
          "Conflicting mock declaration for '#{method_name}' in demeter style mock"
      end
    end
    
    METHOD_NAME_RE = /^([A-Za-z_][A-Za-z0-9_]*[=!?]?|\[\]=?||\*\*|<<|>>|<=>|[<>=]=|=~|===|[-+]@|[-+\*\/%&^|<>~])$/

    # Check that all the names in the list are valid method names.
    def check_method_names(names)
      names.each do |name|
        fail FlexMock::UsageError, "Ill-formed method name '#{name}'" if
          name !~ METHOD_NAME_RE
      end
    end
  end

  ContainerHelper = MockContainerHelper.new
end
