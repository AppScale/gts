#!/usr/bin/env ruby

#---
# Copyright 2003, 2004, 2005, 2006, 2007 by Jim Weirich (jim@weirichhouse.org).
# All rights reserved.

# Permission is granted for use, copying, modification, distribution,
# and distribution of modified versions of this work as long as the
# above copyright notice is included.
#+++

class FlexMock

  # Provide a common failure assertion.
  module FailureAssertion
    private

    # Assertion helper used to assert validation failure.  If a 
    # message is given, then the error message should match the 
    # expected error message.
    def assert_failure(message=nil)
      ex = assert_raises(Test::Unit::AssertionFailedError) { yield }
      if message
        case message
        when Regexp
          assert_match message, ex.message
        when String
          assert ex.message.index(message), "Error message '#{ex.message}' should contain '#{message}'"
        end
      end
      ex
    end
  end
end
