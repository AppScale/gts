#!/usr/bin/ruby -w
require 'test/unit'
require 'helperfunctions'
require 'djinn'

class TestDjinn < Test::Unit::TestCase
  def test_helper_local_ip
    ip_msg = "Local IP must match the regex format for IP addresses"
    local_ip_result = HelperFunctions.local_ip
assert(local_ip_result =~ /\d+\.\d+\.\d+\.\d+/, ip_msg)
  end
  
  def test_spawn_vms    
    begin
      spawn_vms_result = HelperFunctions.spawn_vms
    rescue => except
      spawn_vms_result = except
    end
    
    if spawn_vms_result.class == Hash
      assert(!spawn_vms_result.empty?, "Instance hash shouldn't be empty")
      terminate_result = HelperFunctions.terminate_vms(spawn_vms_result)
      assert_nil(terminate_result)
    elsif spawn_vms_result.class == VMException
      assert(spawn_vms_result.message == "No instance was able to get a public IP address", "An unexpected virtual machine exception was thrown, with the message: #{spawn_vms_result.message}")
    else
      HelperFunctions.terminate_all_vms
      flunk("Return value should be either a Hash or an Exception, not a #{spawn_vms_result.class}")
    end
    
  end
end