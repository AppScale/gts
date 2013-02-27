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

class UndefinedTest < Test::Unit::TestCase
  def test_undefined_method_calls_return_undefined
    assert_undefined undefined.some_random_undefined_method
  end

  def test_equals
    assert undefined == undefined
    assert ! (undefined == Object.new)
  end

  def test_math_operators
    assert_undefined undefined + 1
    assert_undefined undefined - 1
    assert_undefined undefined * 1
    assert_undefined undefined / 1
    assert_undefined undefined ** 1
  end

  def test_math_operators_reversed
    assert_undefined 1 + undefined
    assert_undefined 1 - undefined
    assert_undefined 1 * undefined
    assert_undefined 1 / undefined
    assert_undefined 2 ** undefined
  end

  def test_comparisons
    assert_undefined undefined < 1
    assert_undefined undefined <= 1
    assert_undefined undefined > 1
    assert_undefined undefined >= 1
    assert_undefined undefined <=> 1
  end

  def test_comparisons_reversed
    assert_undefined 1 < undefined
    assert_undefined 1 <= undefined
    assert_undefined 1 > undefined
    assert_undefined 1 >= undefined
    assert_undefined 1 <=> undefined
  end

  def test_base_level_methods
    assert_kind_of FlexMock::Undefined, undefined
  end

  def test_cant_create_a_new_undefined
    assert_raises(NoMethodError) do FlexMock::Undefined.new end
  end

  def test_cant_clone_undefined
    assert_undefined undefined.clone
    assert_equal undefined.__id__, undefined.clone.__id__
  end

  def test_string_representations
    assert_equal "-UNDEFINED-", undefined.to_s
    assert_equal "-UNDEFINED-", undefined.inspect
  end

  def test_undefined_is_not_nil
    assert ! undefined.nil?
  end

  private

  def assert_undefined(obj)
    assert undefined == obj
  end

  def undefined
    FlexMock.undefined
  end
end
