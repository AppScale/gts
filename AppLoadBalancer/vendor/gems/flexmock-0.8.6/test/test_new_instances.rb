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
require 'test/redirect_error'

class TestNewInstances < Test::Unit::TestCase
  include FlexMock::TestCase
  include FlexMock::RedirectError
  
  class Dog
    def bark
      :woof
    end
    def wag
      :tail
    end
    def self.make
      new
    end
  end

  class Cat
    attr_reader :name
    def initialize(name, &block)
      @name = name
      block.call(self) if block_given?
    end
  end
  
  class Connection
    def initialize(*args)
      yield(self) if block_given?
    end
    def send(args)
      post(args)
    end
    def post(args)
      :unstubbed
    end
  end

  def test_new_instances_allows_stubbing_of_existing_methods
    flexstub(Dog).new_instances do |obj|
      obj.should_receive(:bark).and_return(:whimper)
    end
    m = Dog.new
    assert_equal :whimper,  m.bark
  end
  
  def test_new_instances_stubs_still_have_existing_methods
    flexstub(Dog).new_instances do |obj|
      obj.should_receive(:bark).and_return(:whimper)
    end
    m = Dog.new
    assert_equal :tail,  m.wag
  end

  def test_new_instances_will_pass_args_to_new
    flexstub(Cat).new_instances do |obj|
      obj.should_receive(:meow).and_return(:scratch)
    end
    x = :not_called
    m = Cat.new("Fido") { x = :called }
    assert_equal :scratch,  m.meow
    assert_equal "Fido", m.name
    assert_equal :called, x
  end

  # Some versions of the software had problems invoking the block after a
  # second stubbing.
  def test_new_gets_block_after_restubbing
    flexstub(Cat).new_instances { }
    x = :not_called
    m = Cat.new("Fido") { x = :called }
    assert_equal :called, x
    flexmock_teardown
    
    flexstub(Cat).new_instances { }
    x = :not_called
    m = Cat.new("Fido") { x = :called }
    assert_equal :called, x
  end

  def test_new_instances_stub_verification_happens_on_teardown
    flexstub(Dog).new_instances do |obj|
      obj.should_receive(:bark).once.and_return(nil)
    end
    
    fido = Dog.new    
    ex = assert_raise(Test::Unit::AssertionFailedError) { flexmock_teardown }
    assert_match(/method 'bark\(.*\)' called incorrect number of times/, ex.message)
  end

  def test_new_instances_reports_error_on_non_classes
    ex = assert_raise(ArgumentError) { 
      flexstub(Dog.new).new_instances do |obj|
        obj.should_receive(:hi)
      end
    }
    assert_match(/Class/, ex.message)
    assert_match(/new_instances/, ex.message)
  end
  
  def test_does_not_by_default_stub_objects_created_with_allocate
    flexstub(Dog).new_instances do |obj|
      obj.should_receive(:bark).and_return(:whimper)
    end
    m = Dog.allocate
    assert_equal :woof,  m.bark
  end
  
  def test_can_explicitly_stub_objects_created_with_allocate
    flexstub(Dog).new_instances(:allocate) do |obj|
      obj.should_receive(:bark).and_return(:whimper)
    end
    m = Dog.allocate
    assert_equal :whimper,  m.bark
  end
  
  def test_can_stub_objects_created_with_arbitrary_class_methods
    flexstub(Dog).new_instances(:make) do |obj|
      obj.should_receive(:bark).and_return(:whimper)
    end
    assert_equal :whimper,  Dog.make.bark
  end
  
  def test_stubbing_arbitrary_class_methods_leaves_new_alone
    flexstub(Dog).new_instances(:make) do |obj|
      obj.should_receive(:bark).and_return(:whimper)
    end
    assert_equal :woof,  Dog.new.bark
  end

  def test_stubbing_new_and_allocate_doesnt_double_stub_objects_on_new
    counter = 0
    flexstub(Dog).new_instances do |obj|
      counter += 1
    end
    Dog.new
    assert_equal 1, counter
  end

  # Current behavior does not install stubs into the block passed to new. 
  # This is rather difficult to achieve, although it would be nice.  For the
  # moment, we assure that they are not stubbed, but I am willing to change 
  # this in the future.
  def test_blocks_on_new_do_not_have_stubs_installed
    flexstub(Connection).new_instances do |new_con|
      new_con.should_receive(:post).and_return {
        :stubbed
      }
    end
    block_run = false
    Connection.new do |c|
      assert_equal :unstubbed, c.send("hi")
      block_run = true
    end
    assert block_run
  end
  
  def test_new_instances_accept_chained_expectations
    flexmock(Dog).new_instances.
      should_receive(:growl).and_return(:grr).
      should_receive(:roll_over).and_return(:flip)
    assert_equal :grr, Dog.new.growl
    assert_equal :flip, Dog.new.roll_over
  end
  
  def test_fancy_use_of_chained_should_received
    flexmock(Dog).new_instances.should_receive(:woof => :grrr)
    assert_equal :grrr, Dog.new.woof
  end
  
  def test_writable_accessors
    flexmock(Dog).new_instances.should_receive(:name=).with("fido")
    dog = Dog.new
    dog.name = 'fido'
  end
  
  def test_ordering_can_be_specified
    dog = Dog.new
    flexmock(dog).should_receive(:bark).once.ordered
    flexmock(dog).should_receive(:bite).once.ordered
    dog.bark
    dog.bite
  end
  
  def test_ordering_can_be_specified_in_groups
    dog = Dog.new
    flexmock(dog).should_receive(:wag).once.ordered(:safe)
    flexmock(dog).should_receive(:bark).once.ordered(:danger)
    flexmock(dog).should_receive(:bite).once.ordered(:danger)
    dog.wag
    dog.bite
    dog.bark
  end
end


