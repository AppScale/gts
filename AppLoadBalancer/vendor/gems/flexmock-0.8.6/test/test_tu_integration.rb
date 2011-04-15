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

class TestTuIntegrationFlexMockMethod < Test::Unit::TestCase
  include FlexMock::TestCase
  
  def test_can_construct_flexmock
    mock = flexmock("x")
    mock.should_receive(:hi).and_return(:hello)
    assert_equal :hello, mock.hi
  end
  
  def test_can_construct_flexmock_with_block
    mock = flexmock("x") do |m|
      m.should_receive(:hi).and_return(:hello)
    end
    assert_equal :hello, mock.hi
  end
end

class TestTuIntegrationMockVerificationInTeardown < Test::Unit::TestCase
  include FlexMock::TestCase

  def teardown
    assert_raise(Test::Unit::AssertionFailedError) do
      super
    end
  end

  def test_mock_verification_occurs_during_teardown
    flexmock("xyz").should_receive(:hi).with(any).once
  end
end

class TestTuIntegrationMockVerificationWithoutSetup < Test::Unit::TestCase
  include FlexMock::TestCase

  def teardown
    assert_raise(Test::Unit::AssertionFailedError) do
      super
    end
  end

  def test_mock_verification_occurs_during_teardown
    flexmock("xyz").should_receive(:hi).with(any).once
  end
end

class TestTuIntegrationMockVerificationForgetfulSetup < Test::Unit::TestCase
  include FlexMock::TestCase

  def teardown
    assert_raise(Test::Unit::AssertionFailedError) do
      super
    end
  end

  def test_mock_verification_occurs_during_teardown
    flexmock("xyz").should_receive(:hi).with(any).once
  end
end

class TestTuIntegrationSetupOverridenAndNoMocksOk < Test::Unit::TestCase
  include FlexMock::TestCase

  def test_mock_verification_occurs_during_teardown
  end
end

class TestTuIntegrationFailurePreventsVerification < Test::Unit::TestCase
  include FlexMock::TestCase

  def test_mock_verification_occurs_during_teardown
    flexmock('m').should_receive(:hi).once
    simulate_failure
  end

  private

  def simulate_failure
    @test_passed = false
  end
end
