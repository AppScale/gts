#!/usr/bin/env ruby

#---
# Copyright 2003, 2004, 2005, 2006, 2007 by Jim Weirich (jim@weirichhouse.org).
# All rights reserved.

# Permission is granted for use, copying, modification, distribution,
# and distribution of modified versions of this work as long as the
# above copyright notice is included.
#+++

require "test/unit"
require "flexmock"

module ExtendedShouldReceiveTests
  def test_accepts_expectation_hash
    @mock.should_receive( :foo => :bar, :baz => :froz )
    assert_equal :bar, @obj.foo
    assert_equal :froz, @obj.baz
  end
  
  def test_accepts_list_of_methods
    @mock.should_receive(:foo, :bar, "baz")
    assert_nil @obj.foo
    assert_nil @obj.bar
    assert_nil @obj.baz
  end
  
  def test_contraints_apply_to_all_expectations
    @mock.should_receive(:foo, :bar => :baz).with(1)
    ex = assert_raise(Test::Unit::AssertionFailedError) { @obj.foo(2) }
    ex = assert_raise(Test::Unit::AssertionFailedError) { @obj.bar(2) }
    assert_equal :baz, @obj.bar(1)
  end
  
  def test_count_contraints_apply_to_all_expectations
    @mock.should_receive(:foo, :bar => :baz).once
    @obj.foo
    assert_raise(Test::Unit::AssertionFailedError) { @mock.flexmock_verify }
  end
  
  def test_multiple_should_receives_are_allowed
    @mock.should_receive(:hi).and_return(:bye).
      should_receive(:hello => :goodbye)
    assert_equal :bye, @obj.hi
    assert_equal :goodbye, @obj.hello
  end
end

class TestExtendedShouldReceiveOnFullMocks < Test::Unit::TestCase
  include FlexMock::TestCase
  include ExtendedShouldReceiveTests
  
  def setup
    @mock = flexmock("mock")
    @obj = @mock
  end

end

class TestExtendedShouldReceiveOnPartialMockProxies < Test::Unit::TestCase
  include FlexMock::TestCase
  include ExtendedShouldReceiveTests
  
  def setup
    @obj = Object.new
    @mock = flexmock(@obj, "mock")
  end

end
