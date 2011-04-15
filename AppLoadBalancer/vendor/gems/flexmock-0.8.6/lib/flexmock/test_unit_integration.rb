#!/usr/bin/env ruby

#---
# Copyright 2003, 2004, 2005, 2006, 2007 by Jim Weirich (jim@weirichhouse.org).
# All rights reserved.

# Permission is granted for use, copying, modification, distribution,
# and distribution of modified versions of this work as long as the
# above copyright notice is included.
#+++

require 'test/unit'
require 'flexmock/base'

class FlexMock
  
  ####################################################################
  # Test::Unit::TestCase Integration.
  #
  # Include this module in any TestCase class in a Test::Unit test
  # suite to get integration with FlexMock.  When this module is
  # included, the mock container methods (e.g. flexmock(), flexstub()) 
  # will be available.
  #
  # <b>Note:</b> If you define a +teardown+ method in the test case,
  # <em>dont' forget to invoke the +super+ method!</em> Failure to
  # invoke super will cause all mocks to not be verified.
  #
  module TestCase
    include ArgumentTypes
    include MockContainer

    # Teardown the test case, verifying any mocks that might have been
    # defined in this test case.
    def teardown
      super
      flexmock_teardown
    end

  end
  
  ####################################################################
  # Adapter for adapting FlexMock to the Test::Unit framework.
  #
  class TestUnitFrameworkAdapter
    include Test::Unit::Assertions
    def assertion_failed_error
      Test::Unit::AssertionFailedError
    end
  end

  @framework_adapter = TestUnitFrameworkAdapter.new
end
