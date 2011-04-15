#!/usr/bin/env ruby

#---
# Copyright 2003, 2004, 2005, 2006, 2007 by Jim Weirich (jim@weirichhouse.org).
# All rights reserved.
#
# Permission is granted for use, copying, modification, distribution,
# and distribution of modified versions of this work as long as the
# above copyright notice is included.
#+++

require 'flexmock/noop'

class FlexMock
  ####################################################################
  # Match any object
  class AnyMatcher
    def ===(target)
      true
    end
    def inspect
      "ANY"
    end
  end

  ####################################################################
  # Match only things that are equal.
  class EqualMatcher
    def initialize(obj)
      @obj = obj
    end
    def ===(target)
      @obj == target
    end
    def inspect
      "==(#{@obj.inspect})"
    end
  end

  ANY = AnyMatcher.new

  ####################################################################
  # Match only things where the block evaluates to true.
  class ProcMatcher
    def initialize(&block)
      @block = block
    end
    def ===(target)
      @block.call(target)
    end
    def inspect
      "on{...}"
    end
  end
  
  ####################################################################
  # Match only things where the block evaluates to true.
  class HashMatcher
    def initialize(hash)
      @hash = hash
    end
    def ===(target)
      @hash.all? { |k, v| target[k] == v }
    end
    def inspect
      "hsh(#{@hash.inspect})"
    end
  end
  
  ####################################################################
  # Match only things where the block evaluates to true.
  class DuckMatcher
    def initialize(methods)
      @methods = methods
    end
    def ===(target)
      @methods.all? { |m| target.respond_to?(m) }
    end
    def inspect
      "ducktype(#{@methods.map{|m| m.inspect}.join(',')})"
    end
  end
  
  
end
