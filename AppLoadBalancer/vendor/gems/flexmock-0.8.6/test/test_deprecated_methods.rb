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
require 'flexmock/deprecated_methods'
require 'test/redirect_error'

class TestFlexMock < Test::Unit::TestCase
  include FlexMock::TestCase
  include FlexMock::RedirectError

  def s(&block)
    redirect_error(&block)
  end

  def setup
    @mock = flexmock('mock')
  end

  def test_handle
    args = nil
    s { @mock.mock_handle(:hi) { |a, b| args = [a,b] } }
    @mock.hi(1,2)
    assert_equal [1,2], args
  end

  def test_handle_no_block
    s { @mock.mock_handle(:blip) }
    @mock.blip
    assert true, "just checking for failures"
  end

  def test_called_with_block
    called = false
    s { @mock.mock_handle(:blip) { |block| block.call } }
    @mock.blip { called = true }
    assert called, "Block to blip should be called"
  end

  def test_return_value
    s { @mock.mock_handle(:blip) { 10 } }
    assert_equal 10, @mock.blip
  end

  def test_handle_missing_method
    expected_error = (RUBY_VERSION >= "1.8.0") ? NoMethodError : NameError
    ex = assert_raises(expected_error) {
      @mock.not_defined
    }
    assert_match(/not_defined/, ex.message)
  end

  def test_ignore_missing_method
    @mock.mock_ignore_missing
    @mock.blip
    assert true, "just checking for failures"
  end

  def test_good_counts
    s { @mock.mock_handle(:blip, 3) }
    @mock.blip
    @mock.blip
    @mock.blip
    @mock.flexmock_verify
  end

  def test_bad_counts
    s { @mock.mock_handle(:blip, 3) }
    @mock.blip
    @mock.blip
    begin
      @mock.flexmock_verify
    rescue Test::Unit::AssertionFailedError => err
    end
    assert_not_nil err
  end

  def test_undetermined_counts
    FlexMock.use('fs') { |m|
      s { m.mock_handle(:blip) }
      m.blip
      m.blip
      m.blip
    }
  end

  def test_zero_counts
    assert_raises(Test::Unit::AssertionFailedError) do
      FlexMock.use { |m|
        s { m.mock_handle(:blip, 0) }
        m.blip
      }
    end
  end

  def test_file_io_with_use
    file = FlexMock.use do |m|
      filedata = ["line 1", "line 2"]
      s { m.mock_handle(:gets, 3) { filedata.shift } }
      assert_equal 2, count_lines(m)
    end
  end

  def count_lines(stream)
    result = 0
    while line = stream.gets
      result += 1
    end
    result    
  end

  def test_use
    assert_raises(Test::Unit::AssertionFailedError) {
      FlexMock.use do |m|
	s { m.mock_handle(:blip, 2) }
	m.blip
      end
    }
  end

  def test_failures_during_use
    ex = assert_raises(NameError) {
      FlexMock.use do |m|
	s { m.mock_handle(:blip, 2) }
	xyz
      end
    }
    assert_match(/undefined local variable or method/, ex.message)
  end

  def test_sequential_values
    values = [1,4,9,16]
    s { @mock.mock_handle(:get) { values.shift } }
    assert_equal 1, @mock.get
    assert_equal 4, @mock.get
    assert_equal 9, @mock.get
    assert_equal 16, @mock.get
  end
  
  def test_respond_to_returns_false_for_non_handled_methods
    assert(!@mock.respond_to?(:blah), "should not respond to blah")
  end

  def test_respond_to_returns_true_for_explicit_methods
    s { @mock.mock_handle(:xyz) }
    assert(@mock.respond_to?(:xyz), "should respond to test")
  end

  def test_respond_to_returns_true_for_missing_methods_when_ignoring_missing
    @mock.mock_ignore_missing
    assert(@mock.respond_to?(:yada), "should respond to yada now")
  end

  def test_respond_to_returns_true_for_missing_methods_when_ignoring_missing_using_should
    @mock.should_ignore_missing
    assert(@mock.respond_to?(:yada), "should respond to yada now")
  end

  def test_method_proc_raises_error_on_unknown
    assert_raises(NameError) {
      @mock.method(:xyzzy)
    }
  end

  def test_method_returns_callable_proc
    got_it = false
    s { @mock.mock_handle(:xyzzy) { got_it = true } }
    method_proc = @mock.method(:xyzzy)
    assert_not_nil method_proc
    method_proc.call
    assert(got_it, "method proc should run")
  end

  def test_method_returns_do_nothing_proc_for_missing_methods
    @mock.mock_ignore_missing
    method_proc = @mock.method(:plugh)
    assert_not_nil method_proc
    assert_equal FlexMock.undefined, method_proc.call
  end
end

class TestDeprecatedOrderingMethods < Test::Unit::TestCase
  include FlexMock::TestCase
  include FlexMock::RedirectError

  def test_deprecated_ordering_methods
    flexmock(:x).should_receive(:msg).globally.ordered(:testgroup)
    assert_equal({ :testgroup => 1 }, flexmock_groups)
    message = redirect_error do
      assert_equal({ :testgroup => 1 }, mock_groups)
    end
    assert_match(/deprecated/i, message)
    assert_match(/\bmock_groups/, message)
    assert_match(/\bflexmock_groups/, message)
  end
end

class TestAnyInstance < Test::Unit::TestCase
  include FlexMock::TestCase
  include FlexMock::RedirectError

  class Dog
    def bark
      :woof
    end
  end

  def test_any_instance_still_works_for_backwards_compatibility
    message = redirect_error do
      flexstub(Dog).any_instance do |obj|
        obj.should_receive(:bark).and_return(:whimper)
        assert_match(/deprecated/, message)
      end
    end
    m = Dog.new
    assert_equal :whimper,  m.bark   
  end
end  
