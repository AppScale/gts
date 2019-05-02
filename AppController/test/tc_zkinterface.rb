
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


  def test_add_and_remove_revision_entry
    revision_path = ZKInterface::ROOT_APP_PATH + "/app_default_v1_1"
    ip1_path = "#{revision_path}/ip1"
    ip2_path = "#{revision_path}/ip2"

    all_ok = {:rc => 0}
    file_does_exist = {:rc => 0, :stat => flexmock(:exists => true)}
    file_does_not_exist = {:rc => 0, :stat => flexmock(:exists => false)}

    # mocks for zookeeper
    zk = flexmock("zookeeper")
    zk.should_receive(:connected?).and_return(false)
    zk.should_receive(:close!)

    # let's say the app directory structure already exists
    zk.should_receive(:get).with(:path => ZKInterface::ROOT_APP_PATH).
      and_return(file_does_exist)
    zk.should_receive(:set).with(:path => ZKInterface::ROOT_APP_PATH,
      :data => ZKInterface::DUMMY_DATA).and_return(all_ok)

    zk.should_receive(:get).with(:path => revision_path).
      and_return(file_does_exist)

    # but let's say that there's no node (file) for each of our IPs
    zk.should_receive(:get).with(:path => ip1_path).
      and_return(file_does_not_exist)
    zk.should_receive(:get).with(:path => ip2_path).
      and_return(file_does_not_exist)

    # creating those files should be fine
    zk.should_receive(:create).with(:path => ip1_path,
      :ephemeral => ZKInterface::NOT_EPHEMERAL, :data => "md5-1").
      and_return(all_ok)
    zk.should_receive(:create).with(:path => ip2_path,
      :ephemeral => ZKInterface::NOT_EPHEMERAL, :data => "md5-1").
      and_return(all_ok)

    # getting a list of the IPs hosting the app should return both
    # IPs the first time around, and no IPs the second time around
    zk.should_receive(:get_children).with(:path => revision_path).
      and_return({:children => ["ip1", "ip2"], :rc => 0},
                 {:children => [], :rc => 0})

    ip1_data = {
      'public_ip' => 'ip1',
      'private_ip' => 'ip1',
      'roles' => 'compute',
      'instance_id' => 'i-id1',
      'disk' => nil
    }

    job_data1_path = "#{ZKInterface::APPCONTROLLER_NODE_PATH}/ip1/job_data"
    zk.should_receive(:get).with(:path => job_data1_path).
      and_return({:rc => 0, :data => JSON.dump(ip1_data)})

    ip2_data = {
      'public_ip' => 'ip2',
      'private_ip' => 'ip2',
      'roles' => 'compute',
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
    ZKInterface.add_revision_entry("app_default_v1_1", "ip1", "md5-1")
    ZKInterface.add_revision_entry("app_default_v1_1", "ip2", "md5-1")

    # make sure they show up when we do a 'get'
    actual = ZKInterface.get_revision_hosters('app_default_v1_1', 'key')
    assert_equal('ip1', actual[0].public_ip)
    assert_equal('ip2', actual[1].public_ip)

    # then remove the entries
    ZKInterface.remove_revision_entry("app_default_v1_1", "ip1")
    ZKInterface.remove_revision_entry("app_default_v1_1", "ip2")

    # make sure they no longer show up when we do a 'get'
    assert_equal([], ZKInterface.get_revision_hosters(
      'app_default_v1_1', 'key'))
  end


  def test_add_and_query_scale_up_requests
    # mocks for zookeeper
    zk = flexmock("zookeeper")
    zk.should_receive(:connected?).and_return(false)
    zk.should_receive(:close!)

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
  end


end
