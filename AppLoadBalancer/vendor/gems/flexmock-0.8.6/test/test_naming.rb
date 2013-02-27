#!/usr/bin/env ruby

#---
# Copyright 2003, 2004, 2005, 2006, 2007 by Jim Weirich (jim@weirichhouse.org).
# All rights reserved.

# Permission is granted for use, copying, modification, distribution,
# and distribution of modified versions of this work as long as the
# above copyright notice is included.
#+++

require 'test/unit'
require 'flexmock'

class TestNaming < Test::Unit::TestCase
  include FlexMock::TestCase
  
  def test_name
    m = flexmock("m")
    assert_equal "m", m.flexmock_name
  end

  def test_name_in_no_handler_found_error
    m = flexmock("mmm")
    ex = assert_raises(Test::Unit::AssertionFailedError) {
      m.should_receive(:xx).with(1)
      m.xx(2)
    }
    assert_match(/'mmm'/, ex.message)
  end

  def test_name_in_received_count_error
    m = flexmock("mmm")
    ex = assert_raises(Test::Unit::AssertionFailedError) {
      m.should_receive(:xx).once
      m.flexmock_verify
    }
   assert_match(/'mmm'/, ex.message)
  end

  def test_naming_with_use
    FlexMock.use("blah") do |m|
      assert_equal "blah", m.flexmock_name
    end
  end

  def test_naming_with_multiple_mocks_in_use
    FlexMock.use("blah", "yuk") do |a, b|
      assert_equal "blah", a.flexmock_name
      assert_equal "yuk",  b.flexmock_name
    end
  end

  def test_inspect_returns_reasonable_name
    FlexMock.use("XYZZY") do |m|
      assert_equal "XYZZY", m.flexmock_name
      assert_equal "<FlexMock:XYZZY>", m.inspect
    end
  end

  def test_mock_can_override_inspect
    FlexMock.use("XYZZY") do |m|
      m.should_receive(:inspect).with_no_args.and_return("MOCK-INSPECT")
      assert_equal "MOCK-INSPECT", m.inspect
    end
  end

  class Dummy
    def inspect
      "DUMMY-INSPECT"
    end
  end

  def test_partial_mocks_use_original_inspect
    dummy = Dummy.new
    flexmock(dummy).should_receive(:msg)
    assert_equal "DUMMY-INSPECT", dummy.inspect
  end

  def test_partial_mocks_can_override_inspect
    dummy = Dummy.new
    flexmock(dummy).should_receive(:inspect).and_return("MOCK-INSPECT")
    assert_equal "MOCK-INSPECT", dummy.inspect
  end
end

