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
  class DefaultFrameworkAdapter
    def assert_block(msg, &block)
      unless yield
        fail assertion_failed_error, msg
      end
    end

    def assert_equal(a, b, msg=nil)
      assert_block(msg || "Expected equal") { a == b }
    end

    class AssertionFailedError < StandardError; end
    def assertion_failed_error
      AssertionFailedError
    end
  end
end