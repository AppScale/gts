#!/usr/bin/env ruby

#---
# Copyright 2003, 2004, 2005, 2006, 2007 by Jim Weirich (jim@weirichhouse.org).
# All rights reserved.

# Permission is granted for use, copying, modification, distribution,
# and distribution of modified versions of this work as long as the
# above copyright notice is included.
#+++

require 'flexmock/argument_types'

class FlexMock

  ####################################################################
  # Translate arbitrary method calls into expectations on the given
  # mock object.
  #
  class Recorder
    include FlexMock::ArgumentTypes

    # Create a method recorder for the mock +mock+.
    def initialize(mock)
      @mock = mock
      @strict = false
    end

    # Place the record in strict mode.  While recording expectations
    # in strict mode, the following will be true.
    #
    # * All expectations will be expected in the order they were
    #   recorded.
    # * All expectations will be expected once.
    # * All arguments will be placed in exact match mode,
    #   including regular expressions and class objects.
    #
    # Strict mode is usually used when giving the recorder to a known
    # good algorithm.  Strict mode captures the exact sequence of
    # calls and validate that the code under test performs the exact
    # same sequence of calls.
    #
    # The recorder may exit strict mode via a
    # <tt>should_be_strict(false)</tt> call.  Non-strict expectations
    # may be recorded at that point, or even explicit expectations
    # (using +should_receieve+) can be specified.
    #
    def should_be_strict(is_strict=true)
      @strict = is_strict
    end

    # Is the recorder in strict mode?
    def strict?
      @strict
    end

    # Record an expectation for receiving the method +sym+ with the
    # given arguments.
    def method_missing(sym, *args, &block)
      expectation = @mock.should_receive(sym).and_return(&block)
      if strict?
        args = args.collect { |arg| eq(arg) }
        expectation.with(*args).ordered.once
      else
        expectation.with(*args)
      end
      expectation
    end
  end

end
