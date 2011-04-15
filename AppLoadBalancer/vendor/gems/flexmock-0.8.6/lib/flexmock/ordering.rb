#!/usr/bin/env ruby

#---
# Copyright 2003, 2004, 2005, 2006, 2007 by Jim Weirich (jim@weirichhouse.org).
# All rights reserved.

# Permission is granted for use, copying, modification, distribution,
# and distribution of modified versions of this work as long as the
# above copyright notice is included.
#+++

class FlexMock

  # #################################################################
  # The ordering module contains the methods and data structures used
  # to determine proper orderring of mocked calls.  By providing the
  # functionality in a module, a individual mock object can order its
  # own calls, and the container can provide ordering at a global
  # level.
  module Ordering

    # Allocate the next available order number.
    def flexmock_allocate_order
      @flexmock_allocated_order ||= 0
      @flexmock_allocated_order += 1
    end

    # Hash of groups defined in this ordering.
    def flexmock_groups
      @flexmock_groups ||= {}
    end

    # Current order number in this ordering.
    def flexmock_current_order
      @flexmock_current_order ||= 0
    end

    # Set the current order for this ordering.
    def flexmock_current_order=(value)
      @flexmock_current_order = value
    end

    def flexmock_validate_order(method_name, order_number)
      FlexMock.check("method #{method_name} called out of order " +
        "(expected order #{order_number}, was #{flexmock_current_order})") {
        order_number >= self.flexmock_current_order
      }
      self.flexmock_current_order = order_number
    end
  end
end
