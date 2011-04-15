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

class TemperatureSampler
  def initialize(sensor)
    @sensor = sensor
  end

  def average_temp
    total = (0...3).collect { @sensor.read_temperature }.inject { |i, s| i + s }
    total / 3.0
  end
end

class TestTemperatureSampler < Test::Unit::TestCase
  include FlexMock::TestCase

  def test_tempurature_sampler
    readings = [10, 12, 14]
    mock_sensor = flexmock("sensor")
    mock_sensor.should_receive(:read_temperature).and_return { readings.shift }
    sampler = TemperatureSampler.new(mock_sensor)
    assert_equal 12, sampler.average_temp
  end
end

class TestExamplesFromReadme < Test::Unit::TestCase
  include FlexMock::TestCase

  def test_simple_return_values
    m = flexmock(:pi => 3.1416, :e => 2.71)
    assert_equal 3.1416, m.pi
    assert_equal 2.71, m.e
  end

  def test_returning_an_undefined_value
    m = flexmock("mock")
    m.should_receive(:foo).and_return_undefined
    m.foo.bar.baz
  end
  
  def test_db
    db = flexmock('db')
    db.should_receive(:query).and_return([1,2,3])
    db.should_receive(:update).with(5).and_return(nil).once
    # test code here
    assert_equal [1, 2, 3], db.query
    db.update(5)
  end

  def test_query_and_update
    db = flexmock('db')
    db.should_receive(:query).and_return([1,2,3]).ordered
    db.should_receive(:update).and_return(nil).ordered
    # test code here
    assert_equal [1,2,3], db.query
    assert_nil db.update
  end

  def test_ordered_queries
    db = flexmock('db')
    db.should_receive(:startup).once.ordered
    db.should_receive(:query).with("GOOG").and_return(12.3).
      once.ordered(:queries)
    db.should_receive(:query).with("APPL").and_return(10.0).
      once.ordered(:queries)
    db.should_receive(:query).with(/^....$/).and_return(3.3).
      at_least.once.ordered(:queries)
    db.should_receive(:finish).once.ordered
    # test code here
    db.startup
    assert_equal 3.3,  db.query("WXYZ")
    assert_equal 10.0, db.query("APPL")
    assert_equal 12.3, db.query("GOOG")
    db.finish
  end
  
  def test_ordered_queries_in_record_mode
    db = flexmock('db')
    db.should_expect do |rec|
      rec.startup.once.ordered
      rec.query("GOOG") { 12.3 }.once.ordered(:queries)
      rec.query("APPL") { 10.0 }.once.ordered(:queries)
      rec.query(/^....$/) { 3.3 }.at_least.once.ordered(:queries)
      rec.finish.once.ordered
    end
    # test code here using +db+.
    db.startup
    assert_equal 10.0, db.query("APPL")
    assert_equal 12.3, db.query("GOOG")
    assert_equal 3.3,  db.query("WXYZ")
    db.finish
  end

  def test_build_xml
    builder = flexmock('builder')
    builder.should_expect do |rec|
      rec.should_be_strict
      known_good_way_to_build_xml(rec)  # record the messages
    end
    new_way_to_build_xml(builder)       # compare to new way
  end

  def known_good_way_to_build_xml(rec)
    rec.one
    rec.two
  end

  def new_way_to_build_xml(rec)
    [:one, :two].each do |sym| rec.send(sym) end
  end

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
    m.an_important_message
    m.unknown_message.bar.baz
  end

  class QuoteService
  end
  class Portfolio
    def value
      QuoteService.new.quote
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
