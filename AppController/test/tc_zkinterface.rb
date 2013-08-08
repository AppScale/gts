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


  def test_add_and_remove_app_entry
    app_path = ZKInterface::ROOT_APP_PATH + "/app"
    ip1_path = "#{app_path}/ip1"
    ip2_path = "#{app_path}/ip2"

    all_ok = {:rc => 0}
    file_does_exist = {:rc => 0, :stat => flexmock(:exists => true)}
    file_does_not_exist = {:rc => 0, :stat => flexmock(:exists => false)}

    # mocks for zookeeper
    zk = flexmock("zookeeper")

    # let's say the app directory structure already exists
    zk.should_receive(:get).with(:path => ZKInterface::ROOT_APP_PATH).
      and_return(file_does_exist)
    zk.should_receive(:set).with(:path => ZKInterface::ROOT_APP_PATH,
      :data => ZKInterface::DUMMY_DATA).and_return(all_ok)

    zk.should_receive(:get).with(:path => app_path).
      and_return(file_does_exist)
    zk.should_receive(:set).with(:path => app_path, 
      :data => ZKInterface::DUMMY_DATA).and_return(all_ok)

    # but let's say that there's no node (file) for each of our IPs
    zk.should_receive(:get).with(:path => ip1_path).
      and_return(file_does_not_exist)
    zk.should_receive(:get).with(:path => ip2_path).
      and_return(file_does_not_exist)

    # creating those files should be fine
    zk.should_receive(:create).with(:path => ip1_path, 
      :ephemeral => ZKInterface::EPHEMERAL, :data => "/boo/baz1").
      and_return(all_ok)
    zk.should_receive(:create).with(:path => ip2_path, 
      :ephemeral => ZKInterface::EPHEMERAL, :data => "/boo/baz2").
      and_return(all_ok)

    # getting a list of the IPs hosting the app should return both
    # IPs the first time around, and no IPs the second time around
    zk.should_receive(:get_children).with(:path => app_path).
      and_return({:children => ["ip1", "ip2"]}, {:children => []})

    ip1_data = {
      'public_ip' => 'ip1',
      'private_ip' => 'ip1',
      'jobs' => 'appengine',
      'instance_id' => 'i-id1',
      'disk' => nil
    }

    job_data1_path = "#{ZKInterface::APPCONTROLLER_NODE_PATH}/ip1/job_data"
    zk.should_receive(:get).with(:path => job_data1_path).
      and_return({:rc => 0, :data => JSON.dump(ip1_data)})

    ip2_data = {
      'public_ip' => 'ip2',
      'private_ip' => 'ip2',
      'jobs' => 'appengine',
      'instance_id' => 'i-id2',
      'disk' => nil
    }

    job_data2_path = "#{ZKInterface::APPCONTROLLER_NODE_PATH}/ip2/job_data"
    zk.should_receive(:get).with(:path => job_data2_path).
      and_return({:rc => 0, :data => JSON.dump(ip2_data)})

    # next, mock out when we try to delete app info
    zk.should_receive(:delete).with(:path => ip1_path).
      and_return(all_ok)
    zk.should_receive(:delete).with(:path => ip2_path).
      and_return(all_ok)

    # mocks for zookeeper initialization
    flexmock(HelperFunctions).should_receive(:sleep_until_port_is_open).
      and_return() 
    flexmock(Zookeeper).should_receive(:new).with("public_ip:2181",
      ZKInterface::TIMEOUT).and_return(zk)

    # first, make a connection to zookeeper 
    ZKInterface.init_to_ip("public_ip", "public_ip")

    # next, add two app entries
    ZKInterface.add_app_entry("app", "ip1", "/boo/baz1")
    ZKInterface.add_app_entry("app", "ip2", "/boo/baz2")

    # make sure they show up when we do a 'get'
    actual = ZKInterface.get_app_hosters("app", "key")
    assert_equal('ip1', actual[0].public_ip)
    assert_equal('ip2', actual[1].public_ip)

    # then remove the entries
    ZKInterface.remove_app_entry("app", "ip1")
    ZKInterface.remove_app_entry("app", "ip2")

    # make sure they no longer show up when we do a 'get'
    assert_equal([], ZKInterface.get_app_hosters("app", "key"))
  end


  def test_add_and_query_scale_up_requests
    # mocks for zookeeper
    zk = flexmock("zookeeper")

    # presume that initially, there are no scaling requests, then after we add
    # one below, it is present
    zk.should_receive(:get_children).with(:path =>
      "#{ZKInterface::SCALING_DECISION_PATH}/bazapp").and_return({
      :children => nil}, {:children => ["public_ip"]})

    # presume that this node hasn't asked for more AppServers yet, so there's no
    # data the first time around. After the first time, we'll add an entry in, so
    # there should be one there on subsequent attempts.
    path = "#{ZKInterface::SCALING_DECISION_PATH}/bazapp/public_ip"
    file_does_not_exist = {:rc => 0, :stat => flexmock(:exists => false)}
    file_contents = {:rc => 0, :stat => flexmock(:exists => true),
      :data => "scale_up"}
    zk.should_receive(:get).with(:path => ZKInterface::SCALING_DECISION_PATH).
      and_return(file_does_not_exist, file_contents)
    zk.should_receive(:get).with(:path =>
      "#{ZKInterface::SCALING_DECISION_PATH}/bazapp").and_return(
      file_does_not_exist, file_contents)
    zk.should_receive(:get).with(:path => path).and_return(file_does_not_exist,
      file_contents)

    all_ok = {:rc => 0}
    zk.should_receive(:create).with(:path => ZKInterface::SCALING_DECISION_PATH,
      :ephemeral => ZKInterface::NOT_EPHEMERAL, :data => "").
      and_return(all_ok)
    zk.should_receive(:create).with(:path =>
      "#{ZKInterface::SCALING_DECISION_PATH}/bazapp",
      :ephemeral => ZKInterface::NOT_EPHEMERAL, :data => "").
      and_return(all_ok)
    zk.should_receive(:create).with(:path => path,
      :ephemeral => ZKInterface::NOT_EPHEMERAL, :data => "scale_up").
      and_return(all_ok)

    # mocks for zookeeper initialization
    flexmock(HelperFunctions).should_receive(:sleep_until_port_is_open).
      and_return()
    flexmock(Zookeeper).should_receive(:new).with("public_ip:2181", ZKInterface::TIMEOUT).
      and_return(zk)

    # first, make a connection to zookeeper
    ZKInterface.init_to_ip("public_ip", "public_ip")

    # make sure the shadow gets back no information if nobody has requested
    # scaling yet
    assert_equal([], ZKInterface.get_scaling_requests_for_app("bazapp"))

    # next, make sure that appservers can request that we scale up
    assert_equal(true, ZKInterface.request_scale_up_for_app("bazapp", "public_ip"))

    # make sure that the shadow can see these requests
    assert_equal(["scale_up"], ZKInterface.get_scaling_requests_for_app("bazapp"))
  end


end
