#!/usr/bin/env ruby

#---
# Copyright 2003, 2004, 2005, 2006, 2007 by Jim Weirich (jim@weirichhouse.org).
# All rights reserved.
#
# Permission is granted for use, copying, modification, distribution,
# and distribution of modified versions of this work as long as the
# above copyright notice is included.
#+++


class Module
  def flexmock_deprecate(*method_names)
    method_names.each do |method_name|
      eval_line = __LINE__ + 1
      module_eval %{
        def #{method_name}(*args)
          $stderr.puts "#{method_name} is deprecated, use flex#{method_name} instead"
          flex#{method_name}(*args)
        end
      }, __FILE__, eval_line
    end
  end
end

# Deprecated Methods
# ==================
#
# The following methods are no longer supported in FlexMock.  Include
# this file for legacy applications.
#
class FlexMock

  # Handle all messages denoted by +sym+ by calling the given block
  # and passing any parameters to the block.  If we know exactly how
  # many calls are to be made to a particular method, we may check
  # that by passing in the number of expected calls as a second
  # paramter.
  def mock_handle(sym, expected_count=nil, &block) # :nodoc:
    $stderr.puts "mock_handle is deprecated, use the new should_receive interface instead."
    self.should_receive(sym).times(expected_count).returns(&block)
  end

  flexmock_deprecate :mock_verify, :mock_teardown, :mock_wrap

  class PartialMockProxy

    MOCK_METHODS << :any_instance

    # any_instance is present for backwards compatibility with version 0.5.0.
    # @deprecated
    def any_instance(&block)
      $stderr.puts "any_instance is deprecated, use new_instances instead."
      new_instances(&block)
    end
  end

  module Ordering
    flexmock_deprecate :mock_allocate_order, :mock_groups, :mock_current_order, :mock_validate_order
  end
end
