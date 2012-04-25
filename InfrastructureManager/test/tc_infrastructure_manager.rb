# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..")
require 'infrastructure_manager'


require 'rubygems'
require 'flexmock/test_unit'


class TestInfrastructureManager < Test::Unit::TestCase


  def setup
    # for now, let's mock out reading the secret
    flexmock(HelperFunctions).should_receive(:get_secret).and_return("secret")

    # make all puts to stdout not do anything, to not clutter up the terminal
    flexmock(Kernel).should_receive(:puts).and_return()

    # make all sleep statements return automatically
    flexmock(Kernel).should_receive(:sleep).and_return()
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

    # mock out calls to the cloud infrastructure

    # first, let's say that calls to add-keypair succeed
    flexmock(HelperFunctions).should_receive(:shell).
      with("booinfrastructure-add-keypair bookeyname 2>&1").
      and_return("BEGIN RSA PRIVATE KEY")

    # next, mock out file writing calls (for writing the SSH key)
    keypath = "/etc/appscale/keys/bookeyname.key"
    flexmock(File).should_receive(:open).with(keypath, "w", Proc).and_return()
    flexmock(FileUtils).should_receive(:chmod).with(Fixnum, keypath).
      and_return()

    # mock out group creation calls
    flexmock(HelperFunctions).should_receive(:shell).
      with("booinfrastructure-add-group boogroup -d appscale 2>&1").
      and_return()
    flexmock(HelperFunctions).should_receive(:shell).
      with("booinfrastructure-authorize boogroup -p 1-65535 -P udp 2>&1").
      and_return()
    flexmock(HelperFunctions).should_receive(:shell).
      with("booinfrastructure-authorize boogroup -p 1-65535 -P tcp 2>&1").
      and_return()
    flexmock(HelperFunctions).should_receive(:shell).
      with("booinfrastructure-authorize boogroup -s 0.0.0.0/0 -P icmp -t -1:-1 2>&1").and_return()

    # mock out the call to env
    flexmock(HelperFunctions).should_receive(:shell).with("env").
      and_return("environment")

    # mock out describe instances calls - the first time, there will be
    # no instances running, and the second time, the instance will have come
    # up
    first_time = ""
    second_time = "RESERVATION     r-55560977      admin   default\n" +
      "INSTANCE        i-id      emi-721D0EBA    public-ip " +
      "   private-ip  running  bookeyname   0       c1.medium    " +
      "   2010-05-07T07:17:48.23Z         myueccluster    eki-675412F5  " +
      "  eri-A1E113E0 "

    flexmock(HelperFunctions).should_receive(:shell).
      with("booinfrastructure-describe-instances 2>&1").
      and_return(first_time, second_time)

    # between the first describe-instances call and the second call, we
    # will actually run instances - mock that out too
    # TODO(cgb): run this command for ec2 sometime and put in some more
    # realistic output
    flexmock(HelperFunctions).should_receive(:shell).
      with("booinfrastructure-run-instances -k bookeyname -n 1 " +
        "--instance-type booinstance_type --group boogroup booid 2>&1").
      and_return("")

    # finally, make sure that we can resolve the private ip via dig
    # otherwise we'll end up failing to resolve it and just using the
    # public ip
    flexmock(HelperFunctions).should_receive(:shell).
      with("dig private-ip +short").and_return("private-ip\n")

    # first, validate that the run_instances call goes through successfully
    # and gives the user a reservation id
    full_params = {"credentials" => {'a' => 'b'},
      "group" => "boogroup",
      "image_id" => "booid",
      "infrastructure" => "booinfrastructure",
      "instance_type" => "booinstance_type",
      "keyname" => "bookeyname",
      "num_vms" => "1",
      "spot" => "false"}
    id = "0000000000"  # no longer randomly generated
    full_result = {"success" => true, "reservation_id" => id, 
      "reason" => "none"}
    assert_equal(full_result, i.run_instances(full_params, "secret"))

    # next, look at run_instances internally to make sure it actually is
    # updating its reservation info
    assert_equal("running", i.reservations[id]["state"])
    
    vm_info = i.reservations[id]["vm_info"]
    assert_equal(["public-ip"], vm_info["public_ips"])
    assert_equal(["private-ip"], vm_info["private_ips"])
    assert_equal(["i-id"], vm_info["instance_ids"])
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
    id = "0000000000"
    params4 = {"reservation_id" => id}
    vm_info = {
      "public_ips" => ["public-ip"],
      "private_ips" => ["private-ip"],
      "instance_ids" => ["i-id"]
    }
    i.reservations[id] = {"success" => true, 
      "reason" => "received run request",
      "state" => "running", "vm_info" => vm_info}
    result4 = i.reservations[id]
    assert_equal(result4, i.describe_instances(params4, "secret"))
  end


  def test_terminate_instances
    i = InfrastructureManager.new()

    # first, test out terminate_instances with a bad secret
    params1 = {}
    result1 = InfrastructureManager::BAD_SECRET_RESPONSE
    assert_equal(result1, i.terminate_instances(params1, "secret1"))

    # next, test out terminate_instances without any credentials
    params2 = {}
    result2 = {"success" => false, "reason" => "no credentials"}
    assert_equal(result2, i.terminate_instances(params2, "secret"))
  end


end
