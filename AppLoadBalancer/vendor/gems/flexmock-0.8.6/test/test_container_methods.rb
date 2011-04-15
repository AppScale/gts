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

# These tests exercise the interface used to define mocks
class TestFlexmockContainerMethods < Test::Unit::TestCase
  include FlexMock::TestCase

  def test_simple_mock_creation
    mock = flexmock
    mock.should_receive(:hi).once.and_return(:lo)
    assert_equal :lo, mock.hi
  end
  
  def test_mock_with_name
    mock = flexmock("Danny")
    mock.should_receive(:xxx).with(1)
    ex = assert_raise(Test::Unit::AssertionFailedError) { mock.xxx }
    assert_match(/Danny/, ex.message)
  end
  
  def test_mock_with_symbol_name
    mock = flexmock(:Danny)
    mock.should_receive(:xxx).with(1)
    ex = assert_raise(Test::Unit::AssertionFailedError) { mock.xxx }
    assert_match(/Danny/, ex.message)
  end
  
  def test_mock_with_hash
    mock = flexmock(:hi => :lo, :good => :bye)
    assert_equal :lo, mock.hi
    assert_equal :bye, mock.good
  end
  
  def test_mock_with_name_and_hash
    mock = flexmock("Danny", :hi => :lo, :good => :bye)
    mock.should_receive(:xxx).with(1)
    assert_equal :lo, mock.hi
    assert_equal :bye, mock.good
    ex = assert_raise(Test::Unit::AssertionFailedError) { mock.xxx }
    assert_match(/Danny/, ex.message)
  end
  
  def test_mock_with_name_hash_and_block
    mock = flexmock("Danny", :hi => :lo, :good => :bye) do |m|
      m.should_receive(:one).and_return(1)
    end
    assert_equal 1, mock.one
    assert_equal :lo, mock.hi
  end
  
  def test_basic_stub
    fido = Object.new
    mock = flexmock(fido)
    mock.should_receive(:wag).and_return(:happy)
    assert_equal :happy, fido.wag
  end
  
  def test_basic_stub_with_name
    fido = Object.new
    mock = flexmock(fido, "Danny")
    mock.should_receive(:xxx).with(1).and_return(:happy)
    ex = assert_raise(Test::Unit::AssertionFailedError) { fido.xxx }
    assert_match(/Danny/, ex.message)
  end

  def test_stub_with_quick_definitions
    fido = Object.new
    mock = flexmock(fido, :wag => :happy)
    assert_equal :happy, fido.wag
  end

  def test_stub_with_name_quick_definitions
    fido = Object.new
    mock = flexmock(fido, "Danny", :wag => :happy)
    mock.should_receive(:xxx).with(1).and_return(:happy)
    ex = assert_raise(Test::Unit::AssertionFailedError) { fido.xxx }
    assert_match(/Danny/, ex.message)
    assert_equal :happy, fido.wag
  end
  
  def test_stubs_are_auto_verified
    fido = Object.new
    mock = flexmock(fido)
    mock.should_receive(:hi).once
    ex = assert_raise(Test::Unit::AssertionFailedError) { flexmock_verify }
  end
  
  def test_stubbing_a_string
    s = "hello"
    mock = flexmock(:base, s, :length => 2)
    assert_equal 2, s.length
  end
  
  def test_multiple_stubs_work_with_same_partial_mock_proxy
    obj = Object.new
    mock1 = flexmock(obj)
    mock2 = flexmock(obj)
    assert_equal mock1, mock2
  end
  
  def test_multiple_stubs_layer_behavior
    obj = Object.new
    flexmock(obj, :hi => :lo)
    flexmock(obj, :high => :low)
    assert_equal :lo, obj.hi
    assert_equal :low, obj.high
  end
end
