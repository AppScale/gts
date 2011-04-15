#!/usr/bin/env ruby

#---
# Copyright 2003, 2004, 2005, 2006, 2007 by Jim Weirich (jim@weirichhouse.org).
# All rights reserved.

# Permission is granted for use, copying, modification, distribution,
# and distribution of modified versions of this work as long as the
# above copyright notice is included.
#+++

require 'flexmock/test_unit_integration'

module Test
  module Unit
    class TestCase
      include FlexMock::ArgumentTypes
      include FlexMock::MockContainer

      # Alias the original teardown behavior for later use.
      alias :flexmock_original_teardown :teardown

      # Teardown the test case, verifying any mocks that might have been
      # defined in this test case.
      def teardown
        flexmock_teardown
        flexmock_original_teardown
      end

    end
  end
end