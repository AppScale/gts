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

# Sample FlexMock Usage.

class TestSamples < Test::Unit::TestCase
  include FlexMock::TestCase

  # This is a basic example where we setup a mock object to mimic an
  # IO object.  We know that the +count_lines+ method uses gets, so we
  # tell the mock object to handle +gets+ by returning successive
  # elements of an array (just as the real +gets+ returns successive
  # elements of a file.
  def test_file_io
    mock_file = flexmock("file")
    mock_file.should_receive(:gets).and_return("line 1", "line 2", nil)
    assert_equal 2, count_lines(mock_file)
  end

  # Count the number of lines in a file.  Used in the test_file_io
  # test.
  def count_lines(file)
    n = 0
    while file.gets
      n += 1
    end
    n
  end
end


class TestUndefined < Test::Unit::TestCase
  include FlexMock::TestCase

  def test_undefined_values
    m = flexmock("mock")
    m.should_receive(:divide_by).with(0).
      and_return_undefined
    assert_equal FlexMock.undefined, m.divide_by(0)
  end
end


class TestSimple < Test::Unit::TestCase
  include FlexMock::TestCase

  def test_simple_mock
    m = flexmock(:pi => 3.1416, :e => 2.71)
    assert_equal 3.1416, m.pi
    assert_equal 2.71, m.e
  end
end

class TestDog < Test::Unit::TestCase
  include FlexMock::TestCase
  
  def test_dog_wags
    tail_mock = flexmock(:wag => :happy)
    assert_equal :happy, tail_mock.wag
  end
end

class Woofer
end

class Dog
  def initialize
    @woofer = Woofer.new
  end
  def bark
    @woofer.woof
  end
  def wag
    :happy
  end
end

class TestDogBarking < Test::Unit::TestCase
  include FlexMock::TestCase
  
  # Setup the tests by mocking the +new+ method of 
  # Woofer and return a mock woofer.
  def setup
    @dog = Dog.new
    flexmock(@dog, :bark => :grrr)
  end
  
  def test_dog
    assert_equal :grrr, @dog.bark   # Mocked Method
    assert_equal :happy, @dog.wag    # Normal Method
  end
end

class TestDogBarkingWithNewInstances < Test::Unit::TestCase
  include FlexMock::TestCase
  
  # Setup the tests by mocking Woofer to always
  # return partial mocks.
  def setup
    flexmock(Woofer).new_instances.should_receive(:woof => :grrr)
  end
  
  def test_dog
    assert_equal :grrr, Dog.new.bark  # All dog objects
    assert_equal :grrr, Dog.new.bark  # are mocked.
  end
end

class TestDefaults < Test::Unit::TestCase
  include FlexMock::TestCase

  def setup
    @mock_dog = flexmock("Fido")
    @mock_dog.should_receive(:tail => :a_tail, :bark => "woof").by_default
  end
  
  def test_something_where_bark_must_be_called_once
    @mock_dog.should_receive(:bark => "bow wow").once

    assert_equal "bow wow", @mock_dog.bark
    assert_equal :a_tail, @mock_dog.tail
  end 
end

class TestDemeter < Test::Unit::TestCase
  include FlexMock::TestCase
  def test_manual_mocking
    # Manually mocking a Law of Demeter violation
    cog = flexmock("cog")
    cog.should_receive(:turn).once.and_return(:ok)
    joint = flexmock("gear", :cog => cog)
    axle = flexmock("axle", :universal_joint => joint)
    chassis = flexmock("chassis", :axle => axle)
    car = flexmock("car", :chassis => chassis)

    # test code
    assert_equal :ok, car.chassis.axle.universal_joint.cog.turn
  end

  def test_demeter
    car = flexmock("car")
    car.should_receive( "chassis.axle.universal_joint.cog.turn" => :ok).once

    # Test code
    assert_equal :ok, car.chassis.axle.universal_joint.cog.turn
  end

end

class TestDb < Test::Unit::TestCase
  include FlexMock::TestCase

  def test_db
    db = flexmock('db')
    db.should_receive(:query).and_return([1,2,3])
    db.should_receive(:update).with(5).and_return(nil).once

    # test code
    assert_nil db.update(5)
  end
end


class TestDb < Test::Unit::TestCase
  include FlexMock::TestCase

  def test_query_and_update
    db = flexmock('db')
    db.should_receive(:query).and_return([1,2,3]).ordered
    db.should_receive(:update).and_return(nil).ordered
    # test code here
    assert_raises(Test::Unit::AssertionFailedError) do
      db.update
      db.query
    end
  end

  def test_ordered_queries
    db = flexmock('db')
    db.should_receive(:startup).once.ordered
    db.should_receive(:query).with("CPWR").and_return(12.3).
      once.ordered(:queries)
    db.should_receive(:query).with("MSFT").and_return(10.0).
      once.ordered(:queries)
    db.should_receive(:query).with(/^....$/).and_return(3.3).
      at_least.once.ordered(:queries)
    db.should_receive(:finish).once.ordered
    # test code here
    db.startup
    db.query("CPWR")
    db.query("MSFT")
    db.query("asdf")
    db.finish
  end

  def test_ordered_queries_in_record_mode
    db = flexmock('db')
    db.should_expect do |rec|
      rec.startup.once.ordered
      rec.query("CPWR") { 12.3 }.once.ordered(:queries)
      rec.query("MSFT") { 10.0 }.once.ordered(:queries)
      rec.query(/^....$/) { 3.3 }.at_least.once.ordered(:queries)
      rec.finish.once.ordered
    end
    # test code here using +db+.
    db.startup
    db.query("CPWR")
    db.query("MSFT")
    db.query("asdf")
    db.finish
  end
  
  def known_good_way_to_build_xml(builder)
    builder.html
  end

  def new_way_to_build_xml(builder)
    known_good_way_to_build_xml(builder)
  end

  def test_build_xml
    builder = flexmock('builder')
    builder.should_expect do |rec|
      rec.should_be_strict
      known_good_way_to_build_xml(rec)  # record the messages
    end
    new_way_to_build_xml(builder)       # compare to new way
  end
  
end

class TestMoreSamples < Test::Unit::TestCase
  include FlexMock::TestCase

  def test_multiple_gets
    file = flexmock('file')
    file.should_receive(:gets).with_no_args.
      and_return("line 1\n", "line 2\n")
    # test code here
    assert_equal "line 1\n", file.gets
    assert_equal "line 2\n", file.gets
  end

  def test_an_important_message
    m = flexmock('m')
    m.should_receive(:an_important_message).and_return(1).once
    m.should_ignore_missing
    # test code here
    assert_equal 1, m.an_important_message
    assert_equal FlexMock.undefined, m.other
  end

  class QuoteService
  end

  class Portfolio
    def initialize
      @quote_service = QuoteService.new
    end
    def value
      @quote_service.quote
    end
  end

  def test_portfolio_value
    flexmock(QuoteService).new_instances do |m|
      m.should_receive(:quote).and_return(100)
    end
    port = Portfolio.new
    value = port.value     # Portfolio calls QuoteService.quote
    assert_equal 100, value
  end

end
