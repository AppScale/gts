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
require 'test/asserts'

class TestShouldIgnoreMissing < Test::Unit::TestCase
  include FlexMock::TestCase

  def setup
    @mock = flexmock("mock")
  end
  
  def test_mocks_do_not_respond_to_undefined_methods
    assert !@mock.respond_to?(:unknown_foo)
  end

  def test_mocks_do_respond_to_defined_methods
    @mock.should_receive(:known_foo => :bar)
    assert @mock.respond_to?(:known_foo)
  end

  def test_mocks_do_respond_to_any_method_when_ignoring_missing
    @mock.should_ignore_missing
    assert @mock.respond_to?(:unknown_foo)
  end

  def test_ignored_methods_return_undefined
    @mock.should_ignore_missing
    assert_equal FlexMock.undefined, @mock.unknown_foo
    @mock.unknown_foo.bar.baz.bleep
  end

  def test_undefined_mocking_with_arguments
    @mock.should_ignore_missing
    assert_equal FlexMock.undefined, @mock.xyzzy(1,:two,"three")
  end

  def test_method_chains_with_undefined_are_self_preserving
    @mock.should_ignore_missing
    assert_equal FlexMock.undefined, @mock.a.b.c.d.e.f(1).g.h.i.j
  end

  def test_method_proc_raises_error_on_unknown
    assert_raises(NameError) {
      @mock.method(:unknown_foo)
    }
  end

  def test_method_returns_callable_proc
    @mock.should_receive(:known_foo).once
    method_proc = @mock.method(:known_foo)
    assert_not_nil method_proc
    method_proc.call
  end

  def test_not_calling_method_proc_will_fail_count_constraints
    @mock.should_receive(:known_foo).once
    method_proc = @mock.method(:known_foo)
    assert_not_nil method_proc
    assert_raises Test::Unit::AssertionFailedError do
      flexmock_teardown
    end
  end

  def test_method_returns_do_nothing_proc_for_missing_methods
    @mock.should_ignore_missing
    method_proc = @mock.method(:plugh)
    assert_not_nil method_proc
    assert_equal FlexMock.undefined, method_proc.call
  end
end

