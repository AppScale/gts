
$:.unshift File.join(File.dirname(__FILE__), "..")
require 'djinn'

require 'rubygems'
require 'flexmock/test_unit'


class TestDjinn < Test::Unit::TestCase
  def setup
    kernel = flexmock(Kernel)
    kernel.should_receive(:puts).and_return()
    kernel.should_receive(:shell).with("").and_return()
    kernel.should_receive(:sleep).and_return()
    kernel.should_receive(:system).with("").and_return()

    flexmock(Logger).new_instances { |instance|
      instance.should_receive(:debug).and_return()
      instance.should_receive(:info).and_return()
      instance.should_receive(:warn).and_return()
      instance.should_receive(:error).and_return()
      instance.should_receive(:fatal).and_return()
    }

    djinn = flexmock(Djinn)
    djinn.should_receive(:log_run).with("").and_return()

    flexmock(HelperFunctions).should_receive(:shell).with("").and_return()
    flexmock(HelperFunctions).should_receive(:log_and_crash).and_raise(
      Exception)

    @secret = "baz"
    flexmock(HelperFunctions).should_receive(:read_file).
      with("/etc/appscale/secret.key").and_return(@secret)
    flexmock(HelperFunctions).should_receive(:shell).
      with("").and_return()
    @app = "app"
  end

  # Every function that is accessible via SOAP should check for the secret
  # and return a certain message if a bad secret is given.
  def test_functions_w_bad_secret
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(false)
    }
    djinn = Djinn.new

    assert_equal(BAD_SECRET_MSG, djinn.is_done_initializing(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_role_info(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_app_info_map(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.set_parameters("", "", @secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_node_stats_json(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_cluster_stats_json(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_all_public_ips(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_all_private_ips(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.job_start(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_online_users_list(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.start_roles_on_nodes({}, @secret))
    assert_equal(BAD_SECRET_MSG, djinn.run_groomer(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_property('baz', @secret))
    assert_equal(BAD_SECRET_MSG, djinn.set_property('baz', 'qux', @secret))
  end


  def test_get_role_info
    role1 = {
      "public_ip" => "public_ip",
      "private_ip" => "private_ip",
      "roles" => ["shadow"],
      "instance_id" => "instance_id"
    }

    role2 = {
      "public_ip" => "public_ip2",
      "private_ip" => "private_ip2",
      "roles" => ["compute"],
      "instance_id" => "instance_id2"
    }

    keyname = "appscale"

    node1 = NodeInfo.new(role1, keyname)
    node2 = NodeInfo.new(role2, keyname)

    # Instead of mocking out "valid_secret?" like we do elsewhere, let's
    # mock out the read_file function, which provides the same effect but
    # tests out a little bit more of the codebase.
    @secret = "baz"
    flexmock(HelperFunctions).should_receive(:read_file).
      with("/etc/appscale/secret.key", true).and_return(@secret)

    djinn = Djinn.new
    djinn.nodes = [node1, node2]

    role1_to_hash, role2_to_hash = JSON.load(djinn.get_role_info(@secret))

    # make sure role1 got hashed fine
    assert_equal("public_ip", role1_to_hash['public_ip'])
    assert_equal("private_ip", role1_to_hash['private_ip'])
    assert_equal(["shadow"], role1_to_hash['roles'])
    assert_equal("instance_id", role1_to_hash['instance_id'])
    assert_equal("cloud1", role1_to_hash['cloud'])

    # and make sure role2 got hashed fine
    assert_equal("public_ip2", role2_to_hash['public_ip'])
    assert_equal("private_ip2", role2_to_hash['private_ip'])
    assert_equal(["compute"], role2_to_hash['roles'])
    assert_equal("instance_id2", role2_to_hash['instance_id'])
    assert_equal("cloud1", role2_to_hash['cloud'])
  end


  def test_set_params_w_bad_params
    flexmock(HelperFunctions).should_receive(:get_all_local_ips).
      and_return(["127.0.0.1"])

    djinn = Djinn.new
    flexmock(djinn).should_receive(:valid_secret?).and_return(true)
    flexmock(djinn).should_receive(:find_me_in_locations)

    one_node_info = JSON.dump([{
      'public_ip' => 'public_ip',
      'private_ip' => 'private_ip',
      'roles' => ['some_role'],
      'instance_id' => 'instance_id'
    }])

    # Try passing in params that aren't the required type
    result_1 = djinn.set_parameters([], [], @secret)
    assert_equal(true, result_1.include?("Error: options wasn't a String"))

    better_credentials = JSON.dump({'keyname' => '0123', 'login' =>
      '1.1.1.1', 'table' => 'cassandra'})
    assert_raises(AppScaleException) {
      result_2 = djinn.set_parameters("", better_credentials,  @secret)
    }

    # Now try credentials with an even number of items, but not all the
    # required parameters
    better_credentials = JSON.dump({'a' => 'b'})
    result_5 = djinn.set_parameters(one_node_info, better_credentials, @secret)
    assert_equal(true, result_5.include?("Error: cannot find"))

    # Now try good credentials, but with bad node info
    credentials = JSON.dump({
      'table' => 'cassandra',
      'login' => '127.0.0.1',
      'keyname' => 'appscale'
    })
    bad_node_info = "[1]"
    assert_raises(AppScaleException) {
      result_6 = djinn.set_parameters(bad_node_info, credentials, @secret)
    }

    # Finally, try credentials with info in the right format, but where it
    # refers to nodes that aren't in our deployment
    one_node_info = JSON.dump([{
      'public_ip' => 'public_ip',
      'private_ip' => 'private_ip',
      'roles' => ['compute', 'shadow', 'taskqueue_master', 'db_master',
                  'load_balancer', 'zookeeper', 'memcache'],
      'instance_id' => 'instance_id',
      'instance_type' => 'instance_type'
    }])

    djinn = Djinn.new
    flexmock(djinn).should_receive(:find_me_in_locations).and_raise(Exception)
    flexmock(djinn).should_receive(:enforce_options).and_return()
    assert_raises(Exception) {
      djinn.set_parameters(one_node_info, credentials, @secret)
    }
  end

  def test_set_params_w_good_params
    flexmock(Djinn).should_receive(:log_run).with(
      "mkdir -p /opt/appscale/apps")

    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
      instance.should_receive("enforce_options").and_return()
    }
    djinn = Djinn.new

    credentials = JSON.dump({
      'table' => 'cassandra',
      'login' => 'public_ip',
      'keyname' => 'appscale',
      'verbose' => 'False'
    })
    one_node_info = JSON.dump([{
      'public_ip' => 'public_ip',
      'private_ip' => '1.2.3.4',
      'roles' => ['compute', 'shadow', 'taskqueue_master', 'db_master',
                  'load_balancer', 'zookeeper', 'memcache'],
      'instance_id' => 'instance_id',
      'instance_type' => 'instance_type'
    }])

    flexmock(HelperFunctions).should_receive(:shell).with("ifconfig").
      and_return("inet addr:1.2.3.4 ")
    flexmock(djinn).should_receive("get_db_master").and_return
    flexmock(djinn).should_receive("get_shadow").and_return

    expected = "OK"
    actual = djinn.set_parameters(one_node_info, credentials, @secret)
    assert_equal(expected, actual)
  end

  def test_taskqueue_master
    # TaskQueue master nodes should configure and deploy RabbitMQ/celery on their node

    # Set up some dummy data that points to our master role as the
    # taskqueue_master
    master_role = {
      "public_ip" => "public_ip",
      "private_ip" => "private_ip",
      "roles" => ["taskqueue_master"],
      "instance_id" => "instance_id"
    }

    djinn = Djinn.new
    djinn.my_index = 0
    djinn.nodes = [NodeInfo.new(master_role, "appscale")]

    # Set the clear_datastore option.
    djinn.options = {'clear_datastore' => 'false',
                     'verbose' => 'false'}

    # make sure we write the secret to the cookie file
    # throw in Proc as the last arg to the mock since we don't care about what
    # the block actually contains
    helperfunctions = flexmock(HelperFunctions)
    helperfunctions.should_receive(:get_secret).and_return(@secret)
    flexmock(ServiceHelper).should_receive(:start).and_return()
    flexmock(ServiceHelper).should_receive(:start).and_return()

    file = flexmock(File)
    file.should_receive(:open).and_return()
    file.should_receive(:log_run).and_return()
    flexmock(Djinn).should_receive(:log_run).and_return()
    flexmock(HelperFunctions).should_receive(:shell).and_return()
    flexmock(HelperFunctions).should_receive(:sleep_until_port_is_open).
      and_return()
    assert_equal(true, djinn.start_taskqueue_master())
  end

  def test_taskqueue_slave
    # Taskqueue slave nodes should wait for RabbitMQ/celery to come up on the master
    # node, and then start RabbitMQ on their own node
    master_role = {
      "public_ip" => "public_ip1",
      "private_ip" => "private_ip1",
      "roles" => ["taskqueue_master"],
      "instance_id" => "instance_id1"
    }

    slave_role = {
      "public_ip" => "public_ip2",
      "private_ip" => "private_ip2",
      "roles" => ["taskqueue_slave"],
      "instance_id" => "instance_id2"
    }

    djinn = Djinn.new
    djinn.my_index = 1
    djinn.nodes = [NodeInfo.new(master_role, "appscale"), NodeInfo.new(slave_role, "appscale")]

    # Set the clear_datastore option.
    djinn.options = {'clear_datastore' => 'false',
                     'verbose' => 'false'}

    # make sure we write the secret to the cookie file
    # throw in Proc as the last arg to the mock since we don't care about what
    # the block actually contains
    helperfunctions = flexmock(HelperFunctions)
    helperfunctions.should_receive(:get_secret).and_return(@secret)
    helperfunctions.should_receive(:is_port_open?).
      with("private_ip1", TaskQueue::SERVER_PORT, HelperFunctions::DONT_USE_SSL).
      and_return(true)
    helperfunctions.should_receive(:is_port_open?).
      with("localhost", TaskQueue::SERVER_PORT, HelperFunctions::DONT_USE_SSL).
      and_return(true)

    file = flexmock(File)
    file.should_receive(:open).with(TaskQueue::COOKIE_FILE, "w+", Proc).and_return()
    file.should_receive(:open).with('/run/appscale/appscale-taskqueue.env', "w+", Proc).and_return()

    # mock out and commands
    flexmock(Djinn).should_receive(:log_run).and_return()
    flexmock(ServiceHelper).should_receive(:start).and_return()
    flexmock(ServiceHelper).should_receive(:start).and_return()
    flexmock(Addrinfo).should_receive('ip.getnameinfo').and_return(["hostname-ip1"])

    flexmock(HelperFunctions).should_receive(:sleep_until_port_is_open).and_return()

    flexmock(Djinn).should_receive(:log_run).and_return()

    assert_equal(true, djinn.start_taskqueue_slave())
  end


  def test_set_done_status
    role = {
      "public_ip" => "public_ip",
      "private_ip" => "private_ip",
      "roles" => ["shadow"],
      "instance_id" => "instance_id"
    }

    djinn = Djinn.new
    djinn.my_index = 0
    djinn.done_loading = true
    my_node = NodeInfo.new(role, "appscale")
    djinn.nodes = [my_node]

    baz = flexmock("baz")
    baz.should_receive(:connected?).and_return(false)
    baz.should_receive(:close!)
    all_ok = {:rc => 0}

    # Mocks for lock acquire / release
    baz.should_receive(:create).and_return(all_ok)
    baz.should_receive(:delete).and_return(all_ok)

    # Mocks for the AppController root node
    baz.should_receive(:get).
      with(:path => ZKInterface::APPCONTROLLER_PATH).
      and_return({:rc => 0, :data => ZKInterface::DUMMY_DATA,
                  :stat => flexmock(:exists => true)})

    # Mocks for writing node information
    baz.should_receive(:get).
      with(:path => ZKInterface::APPCONTROLLER_NODE_PATH).
      and_return({:stat => flexmock(:exists => false)})
    baz.should_receive(:create).with(
      :path => ZKInterface::APPCONTROLLER_NODE_PATH,
      :ephemeral => ZKInterface::NOT_EPHEMERAL,
      :data => ZKInterface::DUMMY_DATA).and_return(all_ok)

    node_path = "#{ZKInterface::APPCONTROLLER_NODE_PATH}/private_ip"
    baz.should_receive(:create).with(
      :path => node_path,
      :ephemeral => ZKInterface::NOT_EPHEMERAL,
      :data => ZKInterface::DUMMY_DATA).and_return(all_ok)

    baz.should_receive(:create).with(
      :path => node_path + "/live",
      :ephemeral => ZKInterface::EPHEMERAL,
      :data => ZKInterface::DUMMY_DATA).and_return(all_ok)

    baz.should_receive(:get).
      with(:path => node_path + "/job_data").
      and_return({:rc => 0, :stat => flexmock(:exists => false)})

    baz.should_receive(:set).with(
      :path => node_path + "/job_data",
      :data => JSON.dump(my_node.to_hash())).and_return(all_ok)

    baz.should_receive(:get).
      with(:path => node_path + "/done_loading").
      and_return({:rc => 0, :stat => flexmock(:exists => true)})

    baz.should_receive(:set).
      with(:path => node_path + "/done_loading", :data => 'true',
           :version => nil).
      and_return(all_ok)

    flexmock(HelperFunctions).should_receive(:sleep_until_port_is_open).
      and_return()
    flexmock(Zookeeper).should_receive(:new).with("private_ip:2181",
      ZKInterface::TIMEOUT).and_return(baz)
    ZKInterface.init_to_ip("private_ip", "private_ip")
    assert_equal(nil, djinn.set_done_status)
  end


  def test_start_roles_on_nodes_bad_input
    # Calling start_roles_on_nodes with something other than a Hash
    # isn't acceptable
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }

    djinn = get_djinn_mock
    expected = Djinn::BAD_INPUT_MSG
    actual = djinn.start_roles_on_nodes("", @secret)
    assert_equal(expected, actual)
  end


  def test_relocate_app_but_port_in_use_by_nginx
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    role = {
      "public_ip" => "1.2.3.4",
      "private_ip" => "1.2.3.4",
      "roles" => ["shadow"],
      "instance_id" => "instance_id"
    }

    djinn = Djinn.new
    djinn.my_index = 0
    djinn.done_loading = true
    my_node = NodeInfo.new(role, "appscale")
    djinn.nodes = [my_node]
    djinn.app_info_map = {
      'myapp' => {
        'compute' => ["1.2.3.4:20001"]
      },
      'another-app' => {
        'compute' => ["1.2.3.4:20000"]
      }
    }

    admin_server_error = 'httpPort not available'
    flexmock(ZKInterface).should_receive(:get_version_details).
      and_return(djinn.app_info_map['myapp'])
    flexmock(Net::HTTP).should_receive(:start).and_return(
      flexmock(:request => nil, :code => 400, :body => admin_server_error))

    assert_equal("false: #{admin_server_error}",
                 djinn.relocate_version('myapp_default_v1', 80, 4380, @secret))
  end


  def test_relocate_version_but_port_in_use_by_nginx_https
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    role = {
      "public_ip" => "1.2.3.4",
      "private_ip" => "1.2.3.4",
      "roles" => ["shadow"],
      "instance_id" => "instance_id"
    }

    djinn = Djinn.new
    djinn.my_index = 0
    djinn.done_loading = true
    my_node = NodeInfo.new(role, "appscale")
    djinn.nodes = [my_node]
    djinn.app_info_map = {
      'myapp' => {
        'compute' => ["1.2.3.4:20001"]
      },
      'another-app' => {
        'compute' => ["1.2.3.4:20000"]
      }
    }

    admin_server_error = 'httpPort not available'
    flexmock(ZKInterface).should_receive(:get_version_details).
      and_return(djinn.app_info_map['myapp'])
    flexmock(Net::HTTP).should_receive(:start).and_return(
      flexmock(:request => nil, :code => 400, :body => admin_server_error))

    assert_equal(
      "false: #{admin_server_error}",
      djinn.relocate_version('myapp_default_v1', 8080, 443, @secret))
  end


  def test_relocate_version_but_port_in_use_by_haproxy
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    role = {
      "public_ip" => "1.2.3.4",
      "private_ip" => "1.2.3.4",
      "roles" => ["shadow"],
      "instance_id" => "instance_id"
    }

    djinn = Djinn.new
    djinn.my_index = 0
    djinn.done_loading = true
    my_node = NodeInfo.new(role, "appscale")
    djinn.nodes = [my_node]
    djinn.app_info_map = {
      'myapp' => {
        'compute' => ["1.2.3.4:20001"]
      },
      'another-app' => {
        'compute' => ["1.2.3.4:20000"]
      }
    }

    admin_server_error = 'httpPort not available'
    flexmock(ZKInterface).should_receive(:get_version_details).
      and_return(djinn.app_info_map['myapp'])
    flexmock(Net::HTTP).should_receive(:start).and_return(
      flexmock(:request => nil, :code => 400, :body => admin_server_error))

    assert_equal(
      "false: #{admin_server_error}",
      djinn.relocate_version('myapp_default_v1', 8080, 4380, @secret))
  end


  def test_relocate_version_but_port_in_use_by_appserver
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    role = {
      "public_ip" => "1.2.3.4",
      "private_ip" => "1.2.3.4",
      "roles" => ["shadow"],
      "instance_id" => "instance_id"
    }

    djinn = Djinn.new
    djinn.my_index = 0
    djinn.done_loading = true
    my_node = NodeInfo.new(role, "appscale")
    djinn.nodes = [my_node]
    djinn.app_info_map = {
      'myapp' => {
        'compute' => ["1.2.3.4:20000"]
      },
      'another-app' => {
        'compute' => ["1.2.3.4:8080"]
      }
    }

    admin_server_error = 'httpPort not available'
    flexmock(ZKInterface).should_receive(:get_version_details).
      and_return(djinn.app_info_map['myapp'])
    flexmock(Net::HTTP).should_receive(:start).and_return(
      flexmock(:request => nil, :code => 400, :body => admin_server_error))

    assert_equal(
      "false: #{admin_server_error}",
      djinn.relocate_version('myapp_default_v1', 8080, 4380, @secret))
  end


  def test_get_property
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
      instance.should_receive("enforce_options").and_return()
    }
    djinn = Djinn.new()

    # Let's populate the djinn first with some property.
    credentials = JSON.dump({
      'table' => 'cassandra',
      'login' => 'public_ip',
      'keyname' => 'appscale',
      'verbose' => 'True'
    })
    one_node_info = JSON.dump([{
      'public_ip' => 'public_ip',
      'private_ip' => '1.2.3.4',
      'roles' => ['compute', 'shadow', 'taskqueue_master', 'db_master',
                  'load_balancer', 'zookeeper', 'memcache'],
      'instance_id' => 'instance_id',
      'instance_type' => 'instance_type'
    }])
    flexmock(Djinn).should_receive(:log_run).with(
      "mkdir -p /opt/appscale/apps")
    flexmock(HelperFunctions).should_receive(:shell).with("ifconfig").
      and_return("inet addr:1.2.3.4 ")
    flexmock(djinn).should_receive("get_db_master").and_return
    flexmock(djinn).should_receive("get_shadow").and_return
    djinn.set_parameters(one_node_info, credentials, @secret)

    # First, make sure that using a regex that matches nothing returns an empty
    # Hash, then test with a good property.
    empty_hash = JSON.dump({})
    assert_equal(empty_hash, djinn.get_property("not-a-variable-name", @secret))
    expected_result = JSON.dump({'verbose' => 'True'})
    assert_equal(expected_result, djinn.get_property('verbose', @secret))
  end


  def test_set_property
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
      instance.should_receive("enforce_options").and_return()
    }
    djinn = Djinn.new()

    # Let's populate the djinn first with some property.
    credentials = JSON.dump({
      'table' => 'cassandra',
      'login' => 'public_ip',
      'keyname' => 'appscale',
      'verbose' => 'False'
    })
    one_node_info = JSON.dump([{
      'public_ip' => 'public_ip',
      'private_ip' => '1.2.3.4',
      'roles' => ['compute', 'shadow', 'taskqueue_master', 'db_master',
                  'load_balancer', 'zookeeper', 'memcache'],
      'instance_id' => 'instance_id',
      'instance_type' => 'instance_type'
    }])
    flexmock(Djinn).should_receive(:log_run).with(
      "mkdir -p /opt/appscale/apps")
    flexmock(HelperFunctions).should_receive(:shell).with("ifconfig").
      and_return("inet addr:1.2.3.4 ")
    flexmock(djinn).should_receive("get_db_master").and_return
    flexmock(djinn).should_receive("get_shadow").and_return
    djinn.set_parameters(one_node_info, credentials, @secret)

    # Verify that setting a property that doesn't exist returns an error.
    assert_equal(Djinn::KEY_NOT_FOUND, djinn.set_property('not-a-real-key',
      'value', @secret))

    # Verify that setting a property that we allow users to set
    # results in subsequent get calls seeing the correct value.
    assert_equal('OK', djinn.set_property('verbose', 'True', @secret))
    expected_result = JSON.dump({'verbose' => 'True'})
    assert_equal(expected_result, djinn.get_property('verbose', @secret))
  end


  def test_deployment_id_exists
    deployment_id_exists = true
    bad_secret = 'boo'
    good_secret = 'blarg'
    djinn = get_djinn_mock
    flexmock(ZKInterface).should_receive(:exists?).
      and_return(deployment_id_exists)

    # If the secret is invalid, djinn should return BAD_SECRET_MSG.
    djinn.should_receive(:valid_secret?).with(bad_secret).and_return(false)
    assert_equal(BAD_SECRET_MSG, djinn.deployment_id_exists(bad_secret))

    # If the secret is valid, djinn should return the deployment ID.
    djinn.should_receive(:valid_secret?).with(good_secret).and_return(true)
    assert_equal(deployment_id_exists, djinn.deployment_id_exists(good_secret))
  end


  def test_get_deployment_id
    good_secret = 'boo'
    bad_secret = 'blarg'
    deployment_id = 'baz'
    djinn = get_djinn_mock
    flexmock(ZKInterface).should_receive(:get).
        and_return(deployment_id)

    # If the secret is invalid, djinn should return BAD_SECRET_MSG.
    djinn.should_receive(:valid_secret?).with(bad_secret).and_return(false)
    assert_equal(BAD_SECRET_MSG, djinn.get_deployment_id(bad_secret))

    # If the secret is valid, djinn should return the deployment ID.
    djinn.should_receive(:valid_secret?).with(good_secret).and_return(true)
    assert_equal(deployment_id, djinn.get_deployment_id(good_secret))
  end


  def test_set_deployment_id
    good_secret = 'boo'
    bad_secret = 'blarg'
    deployment_id = 'baz'
    djinn = flexmock(Djinn.new())
    flexmock(ZKInterface).should_receive(:set).and_return()

    # If the secret is invalid, djinn should return BAD_SECRET_MSG.
    djinn.should_receive(:valid_secret?).with(bad_secret).and_return(false)
    assert_equal(BAD_SECRET_MSG,
      djinn.set_deployment_id(bad_secret, deployment_id))

    # If the secret is valid, djinn should return successfully.
    djinn.should_receive(:valid_secret?).with(good_secret).and_return(true)
    djinn.set_deployment_id(good_secret, deployment_id)
  end


  def get_djinn_mock
    role = {
        "public_ip" => "my public ip",
        "private_ip" => "my private ip",
        "roles" => ["load_balancer"]
    }
    djinn = flexmock(Djinn.new())
    djinn.my_index = 0
    djinn.nodes = [NodeInfo.new(role, "appscale")]
    djinn.done_loading = true
    djinn
  end


  def test_reset_password
    good_secret = 'good_secret'
    bad_secret = 'bad_secret'
    username = 'user'
    password = 'password'
    change_pwd_success = true

    flexmock(UserAppClient).new_instances.should_receive(:change_password => true)

    djinn = get_djinn_mock
    djinn.should_receive(:valid_secret?).with(bad_secret).and_return(false)
    assert_equal(BAD_SECRET_MSG, djinn.reset_password(username, password, bad_secret))

    djinn.should_receive(:valid_secret?).with(good_secret).and_return(true)
    assert_equal(change_pwd_success, djinn.reset_password(username, password, good_secret))
  end


  def test_does_user_exist
    good_secret = 'good_secret'
    bad_secret = 'bad_secret'
    username = 'user'
    user_exists = true

    flexmock(UserAppClient).new_instances.should_receive(:does_user_exist? => true)

    djinn = get_djinn_mock
    djinn.should_receive(:valid_secret?).with(bad_secret).and_return(false)
    assert_equal(BAD_SECRET_MSG, djinn.does_user_exist(username, bad_secret))

    djinn.should_receive(:valid_secret?).with(good_secret).and_return(true)
    assert_equal(user_exists, djinn.does_user_exist(username, good_secret))
  end


  def test_create_user
    good_secret = 'good_secret'
    bad_secret = 'bad_secret'
    username = 'user'
    password = 'password'
    account_type = 'account_type'
    create_user_success = true

    flexmock(UserAppClient).new_instances.should_receive(:commit_new_user => true)

    djinn = get_djinn_mock
    djinn.should_receive(:valid_secret?).with(bad_secret).and_return(false)
    assert_equal(BAD_SECRET_MSG, djinn.create_user(username, password, account_type, bad_secret))

    djinn.should_receive(:valid_secret?).with(good_secret).and_return(true)
    assert_equal(create_user_success, djinn.create_user(username, password, account_type, good_secret))
  end


  def test_set_admin_role
    good_secret = 'good_secret'
    bad_secret = 'bad_secret'
    username = 'user'
    is_cloud_admin = 'true'
    capabilities = 'admin_capabilties'
    set_admin_role_success = true

    flexmock(UserAppClient).new_instances.should_receive(:set_admin_role => true)

    djinn = get_djinn_mock
    djinn.should_receive(:valid_secret?).with(bad_secret).and_return(false)
    assert_equal(BAD_SECRET_MSG, djinn.set_admin_role(username, is_cloud_admin, capabilities, bad_secret))

    djinn.should_receive(:valid_secret?).with(good_secret).and_return(true)
    assert_equal(set_admin_role_success, djinn.set_admin_role(username, is_cloud_admin, capabilities, good_secret))
  end
end
