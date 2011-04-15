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
  # Base class for all the count validators.
  #
  class CountValidator
    def initialize(expectation, limit)
      @exp = expectation
      @limit = limit
    end

    # If the expectation has been called +n+ times, is it still
    # eligible to be called again?  The default answer compares n to
    # the established limit.
    def eligible?(n)
      n < @limit
    end
  end

  ####################################################################
  # Validator for exact call counts.
  #
  class ExactCountValidator < CountValidator
    # Validate that the method expectation was called exactly +n+
    # times.
    def validate(n)
      FlexMock.framework_adapter.assert_equal @limit, n,
        "method '#{@exp}' called incorrect number of times"
    end
  end

  ####################################################################
  # Validator for call counts greater than or equal to a limit.
  #
  class AtLeastCountValidator < CountValidator
    # Validate the method expectation was called no more than +n+
    # times.
    def validate(n)
      FlexMock.framework_adapter.assert_block(
        "Method '#{@exp}' should be called at least #{@limit} times,\n" +
        "only called #{n} times") { n >= @limit }
    end

    # If the expectation has been called +n+ times, is it still
    # eligible to be called again?  Since this validator only
    # establishes a lower limit, not an upper limit, then the answer
    # is always true.
    def eligible?(n)
      true
    end
  end

  ####################################################################
  # Validator for call counts less than or equal to a limit.
  #
  class AtMostCountValidator < CountValidator
    # Validate the method expectation was called at least +n+ times.
    def validate(n)
      FlexMock.framework_adapter.assert_block(
        "Method '#{@exp}' should be called at most #{@limit} times,\n" +
        "only called #{n} times") { n <= @limit }
    end
  end  
end
