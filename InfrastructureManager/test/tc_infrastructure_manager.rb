# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..")
require 'infrastructure_manager'


require 'rubygems'
require 'flexmock/test_unit'


class TestInfrastructureManager < Test::Unit::TestCase


  def setup
    flexmock(HelperFunctions).should_receive(:get_secret).and_return("secret")
  end

  
  def test_initialize
    i = InfrastructureManager.new()
    assert_equal("secret", i.secret)
  end


  def test_run_instances
    i = InfrastructureManager.new()

    # first, test out run_instances with a bad secret
    params1 = {}
    result1 = InfrastructureManager::BAD_SECRET_RESPONSE
    assert_equal(result1, i.run_instances(params1, "secret1"))

    # now try some tests where we don't have all the necessary parameters
    params2 = {}
    result2 = {"success" => false, "reason" => "no credentials"}
    assert_equal(result2, i.run_instances(params2, "secret"))

    params3 = {"credentials" => "boo"}
    result3 = {"success" => false, "reason" => "no group"}
    assert_equal(result3, i.run_instances(params3, "secret"))

    # now try a test where we've specified all the necessary parameters

    # mock out rand so that we generate a non-random reservation id
    flexmock(Kernel).should_receive(:rand).and_return("0")

    full_params = {"credentials" => {'a' => 'b'},
      "group" => "boogroup",
      "image_id" => "booid",
      "infrastructure" => "booinfrastructure",
      "instance_type" => "booinstance_type",
      "keyname" => "bookeyname",
      "num_vms" => "5"}
    full_result = {"success" => true, "reservation_id" => "0000000000", 
      "reason" => "none"}
    assert_equal(full_result, i.run_instances(full_params, "secret"))
  end


  def test_describe_instances
    i = InfrastructureManager.new()

    # first, test out describe_instances with a bad secret
    params1 = {}
    result1 = InfrastructureManager::BAD_SECRET_RESPONSE
    assert_equal(result1, i.describe_instances(params1, "secret1"))

    # test the scenario where we fail to give describe_instances a
    # reservation id
    params2 = {}
    result2 = {"success" => false, "reason" => "no reservation_id"}
    assert_equal(result2, i.describe_instances(params2, "secret"))

    # test what happens when a caller fails to give describe instances
    # a reservation id that's in the system
    params3 = {"reservation_id" => "boo"}
    result3 = InfrastructureManager::RESERVATION_NOT_FOUND_RESPONSE
    assert_equal(result3, i.describe_instances(params3, "secret"))

    # test what happens when a caller gives describe_instances a reservation
    # id that is in the system


  end


  def test_terminate_instances
    i = InfrastructureManager.new()

    # first, test out terminate_instances with a bad secret
    params1 = {}
    result1 = InfrastructureManager::BAD_SECRET_RESPONSE
    assert_equal(result1, i.terminate_instances(params1, "secret1"))
  end


end
