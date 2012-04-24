# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..")
require 'infrastructure_manager'


require 'rubygems'
require 'flexmock/test_unit'


class TestInfrastructureManager < Test::Unit::TestCase


  def setup

  end

  
  def test_run_instances
    flexmock(HelperFunctions).should_receive(:get_secret).and_return("secret")

    i = InfrastructureManager.new()

    assert_equal("secret", i.secret)
  end


end
