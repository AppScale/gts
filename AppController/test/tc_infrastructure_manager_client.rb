# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..", "lib")
require 'infrastructure_manager_client'


require 'rubygems'
require 'flexmock/test_unit'


class TestInfrastructureManagerClient < Test::Unit::TestCase


  def setup
    # make all logging calls not log
    flexmock(Djinn).should_receive(:log_debug).and_return()

    # make all sleep calls return immediately
    flexmock(Kernel).should_receive(:sleep).and_return()
  end


  def test_spawn_one_vm
    flexmock(InfrastructureManagerClient).new_instances { |instance|
      # Let's say that the run_instance request goes through fine
      # on the first attempt here
      instance.should_receive(:run_instances).with({
        'credentials' => {
          'EC2_ACCESS_KEY' => 'booaccess',
          'EC2_SECRET_KEY' => 'boosecret',
          'EC2_URL' => 'booec2url'
        },
        'group' => 'boogroup',
        'image_id' => 'booid',
        'infrastructure' => 'booinfrastructure',
        'instance_type' => 'booinstancetype',
        'keyname' => 'bookeyname',
        'num_vms' => '1',
        'spot' => 'false'
      }).and_return({
        'success' => true,
        'reservation_id' => "0000000000",
        'reason' => 'none'
      })

      # Let's say that the describe_instances request shows the machines
      # not ready the first time, and then ready on all other times
      first_result = {
        'success' => true,
        'reason' => 'received run request',
        'state' => 'pending',
        'vm_info' => nil
      }

      second_result = {
        'success' => true,
        'reason' => 'received run request',
        'state' => 'running',
        'vm_info' => {
          'public_ips' => ['public-ip'],
          'private_ips' => ['private-ip'],
          'instance_ids' => ['i-id']
        }
      }

      instance.should_receive(:describe_instances).with({
        'reservation_id' => "0000000000"
      }).and_return(first_result, second_result)
    }


    imc = InfrastructureManagerClient.new("secret")
    creds = {
      'group' => 'boogroup',
      'machine' => 'booid',
      'infrastructure' => 'booinfrastructure',
      'instance_type' => 'booinstancetype',
      'keyname' => 'bookeyname',
      'ec2_access_key' => 'booaccess',
      'ec2_secret_key' => 'boosecret',
      'ec2_url' => 'booec2url'
    }
  
    expected = ["public-ip:private-ip:open:i-id:cloud1"]
    actual = imc.spawn_vms(1, creds, "open", "cloud1")
    assert_equal(expected, actual)
  end


  def test_spawn_three_vms
    flexmock(InfrastructureManagerClient).new_instances { |instance|
      # Let's say that the run_instance request goes through fine
      # on the first attempt here
      instance.should_receive(:run_instances).with({
        'credentials' => {
          'EC2_ACCESS_KEY' => 'booaccess',
          'EC2_SECRET_KEY' => 'boosecret',
          'EC2_URL' => 'booec2url'
        },
        'group' => 'boogroup',
        'image_id' => 'booid',
        'infrastructure' => 'booinfrastructure',
        'instance_type' => 'booinstancetype',
        'keyname' => 'bookeyname',
        'num_vms' => '3',
        'spot' => 'false'
      }).and_return({
        'success' => true,
        'reservation_id' => "0000000000",
        'reason' => 'none'
      })

      # Let's say that the describe_instances request shows the machines
      # not ready the first time, and then ready on all other times
      first_result = {
        'success' => true,
        'reason' => 'received run request',
        'state' => 'pending',
        'vm_info' => nil
      }

      second_result = {
        'success' => true,
        'reason' => 'received run request',
        'state' => 'running',
        'vm_info' => {
          'public_ips' => ['public-ip1', 'public-ip2', 'public-ip3'],
          'private_ips' => ['private-ip1', 'private-ip2', 'private-ip3'],
          'instance_ids' => ['i-id1', 'i-id2', 'i-id3']
        }
      }

      instance.should_receive(:describe_instances).with({
        'reservation_id' => "0000000000"
      }).and_return(first_result, second_result)
    }


    imc = InfrastructureManagerClient.new("secret")
    creds = {
      'group' => 'boogroup',
      'machine' => 'booid',
      'infrastructure' => 'booinfrastructure',
      'instance_type' => 'booinstancetype',
      'keyname' => 'bookeyname',
      'ec2_access_key' => 'booaccess',
      'ec2_secret_key' => 'boosecret',
      'ec2_url' => 'booec2url'
    }
  
    expected = [
      "public-ip1:private-ip1:a:i-id1:cloud1",
      "public-ip2:private-ip2:b:i-id2:cloud1",
      "public-ip3:private-ip3:c:i-id3:cloud1",
    ]
    actual = imc.spawn_vms(3, creds, ["a", "b", "c"], "cloud1")
    assert_equal(expected, actual)
  end


end
