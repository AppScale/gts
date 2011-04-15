#!/usr/bin/env ruby

require 'test/unit'
require 'flexmock'

class FlexMock
  module StubsAndExpects
    def expects(*args)
      result = should_receive(*args)
      result.at_least.once unless result.call_count_constrained?
      result
    end
    def stubs(*args)
      should_receive(*args)
    end
  end

  module MockContainer
    alias :mock :flexmock
    alias :stub :flexmock
  end

  include StubsAndExpects

  class PartialMockProxy
    include StubsAndExpects
    MOCK_METHODS << :stubs << :expects
  end
end

class AliasingTest < Test::Unit::TestCase
  include FlexMock::TestCase

  def test_mocking
    m = mock("a cute dog").expects(:pat).twice.and_return(:woof!).mock
    assert_equal :woof!, m.pat
    assert_equal :woof!, m.pat
  end
  
  def test_once_mocking
    m = mock("a cute dog").expects(:pat).and_return(:woof!).mock
  end
  
  def test_twice_mocking
    m = mock("a cute dog").expects(:pat).and_return(:woof!).twice.mock
    assert_raises(Test::Unit::AssertionFailedError) { m.flexmock_verify }
  end
  
  def test_stubbing
    m = stub("a cute dog").expects(:pat).and_return(:woof!).mock
    assert_equal :woof!, m.pat
  end
  
  def test_partial
    obj = Object.new
    stub(obj).stubs(:wag).and_return(:tail)
    assert_equal :tail, obj.wag
  end
end

