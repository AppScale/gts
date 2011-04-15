#!/usr/bin/env ruby

#---
# Copyright 2003, 2004, 2005, 2006, 2007 by Jim Weirich (jim@weirichhouse.org).
# All rights reserved.

# Permission is granted for use, copying, modification, distribution,
# and distribution of modified versions of this work as long as the
# above copyright notice is included.
#+++

require 'flexmock/argument_matchers'

class FlexMock

  ####################################################################
  # Include this module in your test class if you wish to use the +eq+
  # and +any+ argument matching methods without a prefix.  (Otherwise
  # use <tt>FlexMock.any</tt> and <tt>FlexMock.eq(obj)</tt>.
  #
  module ArgumentTypes
    # Return an argument matcher that matches any argument.
    def any
      ANY
    end

    # Return an argument matcher that only matches things equal to
    # (==) the given object.
    def eq(obj)
      EqualMatcher.new(obj)
    end

    # Return an argument matcher that matches any object, that when
    # passed to the supplied block, will cause the block to return
    # true.
    def on(&block)
      ProcMatcher.new(&block)
    end

    # Return an argument matcher that matches a hash with the given
    # entries.
    def hsh(hash)
      HashMatcher.new(hash)
    end

    # Return an argument matcher that matches any object that
    # implementes (i.e. responds to) the given method list.
    def ducktype(*methods)
      DuckMatcher.new(methods)
    end
  end
  extend ArgumentTypes

end
