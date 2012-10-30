# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..", "lib")
require 'zkinterface'

$:.unshift File.join(File.dirname(__FILE__), "..")
require 'djinn'

require 'rubygems'
require 'flexmock/test_unit'


class TestZKInterface < Test::Unit::TestCase
  def setup
    kernel = flexmock(Kernel)
    kernel.should_receive(:puts).and_return()
    kernel.should_receive(:sleep).and_return()

    djinn_class = flexmock(Djinn)
    djinn_class.should_receive(:log_debug).and_return()
    djinn_class.should_receive(:log_run).and_return()
  end


  def test_add_and_get_app_instance
    instance1 = {'app_name' => "app1", 'ip' => 'ip1', 'port' => 'port1'}
    instance2 = {'app_name' => "app2", 'ip' => 'ip2', 'port' => 'port2'}

    all_ok = {:rc => 0}
    file_does_not_exist = {:rc => 0, :stat => flexmock(:exists => false)}

    file1_contents = {:rc => 0, :stat => flexmock(:exists => true),
      :data => JSON.dump([instance1])}
    file2_contents = {:rc => 0, :stat => flexmock(:exists => true), 
      :data => JSON.dump([instance2])}

    # mocks for zookeeper
    zk = flexmock("zookeeper")

    # mocks for file existance - they don't exist in this example
    zk.should_receive(:get).with(
      :path => "#{ZKInterface::APPCONTROLLER_NODE_PATH}/ip1/#{ZKInterface::APP_INSTANCE}").and_return(file_does_not_exist, file_does_not_exist, file1_contents)

    zk.should_receive(:get).with(
      :path => "#{ZKInterface::APPCONTROLLER_NODE_PATH}/ip2/#{ZKInterface::APP_INSTANCE}").and_return(file_does_not_exist, file_does_not_exist, file2_contents)

    # mocks for file creation
    zk.should_receive(:create).with(
      :path => "#{ZKInterface::APPCONTROLLER_NODE_PATH}/ip1/#{ZKInterface::APP_INSTANCE}",
      :ephemeral => ZKInterface::NOT_EPHEMERAL,
      :data => JSON.dump([instance1])).and_return(all_ok)

    zk.should_receive(:create).with(
      :path => "#{ZKInterface::APPCONTROLLER_NODE_PATH}/ip2/#{ZKInterface::APP_INSTANCE}",
      :ephemeral => ZKInterface::NOT_EPHEMERAL,
      :data => JSON.dump([instance2])).and_return(all_ok)

    # mocks for zookeeper initialization
    flexmock(HelperFunctions).should_receive(:sleep_until_port_is_open).
      and_return() 
    flexmock(Zookeeper).should_receive(:new).with("public_ip:2181", ZKInterface::TIMEOUT).
      and_return(zk)

    ZKInterface.init_to_ip("public_ip", "public_ip")
    ZKInterface.add_app_instance("app1", "ip1", "port1")
    ZKInterface.add_app_instance("app2", "ip2", "port2")
    assert_equal([instance1], ZKInterface.get_app_instances_for_ip("ip1"))
    assert_equal([instance2], ZKInterface.get_app_instances_for_ip("ip2"))
  end

end
