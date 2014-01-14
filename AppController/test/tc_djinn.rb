# Programmer: Chris Bunch


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
      with("/etc/appscale/secret.key", true).and_return(@secret)
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
    assert_equal(BAD_SECRET_MSG, djinn.is_done_loading(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_role_info(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_app_info_map(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.kill(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.set_parameters("", "", "", @secret))
    assert_equal(BAD_SECRET_MSG, djinn.set_apps([], @secret))
    assert_equal(BAD_SECRET_MSG, djinn.status(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_stats(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.stop_app(@app, @secret))
    assert_equal(BAD_SECRET_MSG, djinn.update([@app], @secret))
    assert_equal(BAD_SECRET_MSG, djinn.set_apps_to_restart([@app], @secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_all_public_ips(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.job_start(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_online_users_list(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.done_uploading(@app, "/tmp/app", 
      @secret))
    assert_equal(BAD_SECRET_MSG, djinn.is_app_running(@app, @secret))
    assert_equal(BAD_SECRET_MSG, djinn.add_role("baz", @secret))
    assert_equal(BAD_SECRET_MSG, djinn.remove_role("baz", @secret))
    assert_equal(BAD_SECRET_MSG, djinn.start_roles_on_nodes({}, @secret))
    assert_equal(BAD_SECRET_MSG, djinn.start_new_roles_on_nodes([], '', 
      @secret))
    assert_equal(BAD_SECRET_MSG, djinn.add_appserver_to_haproxy(@app, 'baz',
      'baz', @secret))
    assert_equal(BAD_SECRET_MSG, djinn.remove_appserver_from_haproxy(@app,
      'baz', 'baz', @secret))
    assert_equal(BAD_SECRET_MSG, djinn.run_groomer(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_property('baz', @secret))
    assert_equal(BAD_SECRET_MSG, djinn.set_property('baz', 'qux', @secret))
  end


  def test_get_role_info
    role1 = {
      "public_ip" => "public_ip",
      "private_ip" => "private_ip",
      "jobs" => ["shadow"],
      "instance_id" => "instance_id"
    }

    role2 = {
      "public_ip" => "public_ip2",
      "private_ip" => "private_ip2",
      "jobs" => ["appengine"],
      "instance_id" => "instance_id2"
    }

    keyname = "appscale"

    node1 = DjinnJobData.new(role1, keyname)
    node2 = DjinnJobData.new(role2, keyname)

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
    assert_equal(["shadow"], role1_to_hash['jobs'])
    assert_equal("instance_id", role1_to_hash['instance_id'])
    assert_equal("cloud1", role1_to_hash['cloud'])

    # and make sure role2 got hashed fine
    assert_equal("public_ip2", role2_to_hash['public_ip'])
    assert_equal("private_ip2", role2_to_hash['private_ip'])
    assert_equal(["appengine"], role2_to_hash['jobs'])
    assert_equal("instance_id2", role2_to_hash['instance_id'])
    assert_equal("cloud1", role2_to_hash['cloud'])
  end


  def test_set_params_w_bad_params
    flexmock(HelperFunctions).should_receive(:get_all_local_ips).
      and_return(["127.0.0.1"])

    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    djinn = Djinn.new

    # Try passing in params that aren't the required type
    bad_param = ""
    result_1 = djinn.set_parameters([], [], [], @secret)
    assert_equal(true, result_1.include?("Error: djinn_locations"))

    result_2 = djinn.set_parameters("", bad_param, [], @secret)
    assert_equal(true, result_2.include?("Error: database_credentials"))

    result_3 = djinn.set_parameters("", [], bad_param, @secret)
    assert_equal(true, result_3.include?("Error: app_names"))

    # Since DB credentials will be turned from an Array to a Hash,
    # it should have an even number of items in it
    bad_credentials = ['a']
    result_4 = djinn.set_parameters("", bad_credentials, [], @secret)
    expected_1 = "Error: DB Credentials wasn't of even length"
    assert_equal(true, result_4.include?(expected_1))

    # Now try credentials with an even number of items, but not all the
    # required parameters
    better_credentials = ['a', 'b']
    result_5 = djinn.set_parameters("", better_credentials, [], @secret)
    assert_equal("Error: Credential format wrong", result_5)

    # Now try good credentials, but with bad node info
    credentials = ['table', 'cassandra', 'hostname', '127.0.0.1', 'ips', '', 
      'keyname', 'appscale']
    bad_node_info = "[1]"
    assert_raises(Exception) {
      djinn.set_parameters(bad_node_info, credentials, better_credentials,
        @secret)
    }

    # Finally, try credentials with info in the right format, but where it
    # refers to nodes that aren't in our deployment
    one_node_info = JSON.dump({
      'public_ip' => 'public_ip',
      'private_ip' => 'private_ip',
      'jobs' => ['some_role'],
      'instance_id' => 'instance_id'
    })
    app_names = []

    udpsocket = flexmock(UDPSocket)
    udpsocket.should_receive(:open).and_return("not any ips above")
    assert_raises(Exception) {
      djinn.set_parameters(one_node_info, credentials, app_names, @secret)
    }
  end

  def test_set_params_w_good_params
    flexmock(Djinn).should_receive(:log_run).with(
      "mkdir -p /opt/appscale/apps")

    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    djinn = Djinn.new

    credentials = ['table', 'cassandra', 'hostname', 'public_ip', 'ips', '', 
      'keyname', 'appscale', 'alter_etc_resolv', 'False', 'verbose', 'False']
    one_node_info = JSON.dump([{
      'public_ip' => 'public_ip',
      'private_ip' => '1.2.3.4',
      'jobs' => ['some_role'],
      'instance_id' => 'instance_id'
    }])
    app_names = []

    flexmock(HelperFunctions).should_receive(:shell).with("ifconfig").
      and_return("inet addr:1.2.3.4 ")

    expected = "OK"
    actual = djinn.set_parameters(one_node_info, credentials, app_names,
      @secret)
    assert_equal(expected, actual)
  end

  def test_set_apps
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    djinn = Djinn.new

    bad_app_list = "boo, foo"
    expected_bad_result = "app names was not an Array but was a String"
    assert_equal(expected_bad_result, djinn.set_apps(bad_app_list, @secret))

    good_app_list = ["boo", "foo"]
    expected_good_result = "App names is now boo, foo"
    assert_equal(expected_good_result, djinn.set_apps(good_app_list, @secret))
  end

  def test_taskqueue_master
    # TaskQueue master nodes should configure and deploy RabbitMQ/celery on their node

    # Set up some dummy data that points to our master role as the
    # taskqueue_master
    master_role = {
      "public_ip" => "public_ip",
      "private_ip" => "private_ip",
      "jobs" => ["taskqueue_master"],
      "instance_id" => "instance_id"
    }

    djinn = Djinn.new
    djinn.my_index = 0
    djinn.nodes = [DjinnJobData.new(master_role, "appscale")]

    # make sure we write the secret to the cookie file
    # throw in Proc as the last arg to the mock since we don't care about what
    # the block actually contains
    helperfunctions = flexmock(HelperFunctions)
    helperfunctions.should_receive(:get_secret).and_return(@secret)
    flexmock(MonitInterface).should_receive(:start).and_return()

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
      "jobs" => ["taskqueue_master"],
      "instance_id" => "instance_id1"
    }

    slave_role = {
      "public_ip" => "public_ip2",
      "private_ip" => "private_ip2",
      "jobs" => ["taskqueue_slave"],
      "instance_id" => "instance_id2"
    }

    djinn = Djinn.new
    djinn.my_index = 1
    djinn.nodes = [DjinnJobData.new(master_role, "appscale"), DjinnJobData.new(slave_role, "appscale")]

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

    # mock out and commands
    flexmock(Djinn).should_receive(:log_run).and_return()
    flexmock(MonitInterface).should_receive(:start).and_return()

    flexmock(HelperFunctions).should_receive(:sleep_until_port_is_open).
      and_return()
    assert_equal(true, djinn.start_taskqueue_slave())
  end


  def test_write_our_node_info
    role = {
      "public_ip" => "public_ip",
      "private_ip" => "private_ip",
      "jobs" => ["shadow"],
      "instance_id" => "instance_id"
    }

    djinn = Djinn.new
    djinn.my_index = 0
    djinn.done_loading = true
    my_node = DjinnJobData.new(role, "appscale")
    djinn.nodes = [my_node]

    baz = flexmock("baz")
    all_ok = {:rc => 0}

    # Mocks for lock acquire / release
    baz.should_receive(:create).and_return(all_ok)
    baz.should_receive(:delete).and_return(all_ok)

    # Mocks for the AppController root node
    baz.should_receive(:get).with(:path => ZKInterface::APPCONTROLLER_PATH).
      and_return({:rc => 0, :data => ZKInterface::DUMMY_DATA,
        :stat => flexmock(:exists => true)})

    # Mocks for writing the IP list
    json_data = '{"ips":[],"last_updated":1331849005}'
    baz.should_receive(:get).
      with(:path => ZKInterface::IP_LIST).
      and_return({:rc => 0, :data => json_data, 
          :stat => flexmock(:exists => true)})

    flexmock(Time).should_receive(:now).and_return(
      flexmock(:to_i => "NOW"))
    new_data = '{"last_updated":"NOW","ips":["public_ip"]}'
    flexmock(JSON).should_receive(:dump).with(
      {"ips" => ["public_ip"], "last_updated" => "NOW"}).
      and_return(new_data)
    flexmock(JSON).should_receive(:dump).with(true).and_return('true')

    baz.should_receive(:set).with(:path => ZKInterface::IP_LIST, 
      :data => new_data).and_return(all_ok)

    # Mocks for the appcontroller lock
    flexmock(JSON).should_receive(:dump).with("public_ip").
      and_return('"public_ip"')
    baz.should_receive(:get).with(
      :path => ZKInterface::APPCONTROLLER_LOCK_PATH).
      and_return({:rc => 0, :data => JSON.dump("public_ip")})

    # Mocks for writing node information
    baz.should_receive(:get).with(
      :path => ZKInterface::APPCONTROLLER_NODE_PATH).
      and_return({:stat => flexmock(:exists => false)})
    baz.should_receive(:create).with(
      :path => ZKInterface::APPCONTROLLER_NODE_PATH,
      :ephemeral => ZKInterface::NOT_EPHEMERAL,
      :data => ZKInterface::DUMMY_DATA).and_return(all_ok)

    node_path = "#{ZKInterface::APPCONTROLLER_NODE_PATH}/public_ip"
    baz.should_receive(:create).with(
      :path => node_path,
      :ephemeral => ZKInterface::NOT_EPHEMERAL,
      :data => ZKInterface::DUMMY_DATA).and_return(all_ok)

    baz.should_receive(:create).with(
      :path => node_path + "/live",
      :ephemeral => ZKInterface::EPHEMERAL,
      :data => ZKInterface::DUMMY_DATA).and_return(all_ok)

    baz.should_receive(:get).with(
      :path => node_path + "/job_data").and_return({
        :rc => 0, :stat => flexmock(:exists => false)})

    flexmock(JSON).should_receive(:dump).with(Hash).
      and_return('"{\"disk\":null,\"public_ip\":\"public_ip\",\"private_ip\":\"private_ip\",\"cloud\":\"cloud1\",\"instance_id\":\"instance_id\",\"ssh_key\":\"/etc/appscale/keys/cloud1/appscale.key\",\"jobs\":\"shadow\"}"')
    baz.should_receive(:set).with(
      :path => node_path + "/job_data",
      :data => JSON.dump(my_node.to_hash())).and_return(all_ok)

    baz.should_receive(:get).with(
      :path => node_path + "/done_loading").and_return({
        :rc => 0, :stat => flexmock(:exists => true)})

    baz.should_receive(:set).with(
      :path => node_path + "/done_loading",
      :data => JSON.dump(true)).and_return(all_ok)

    flexmock(HelperFunctions).should_receive(:sleep_until_port_is_open).
      and_return()
    flexmock(Zookeeper).should_receive(:new).with("public_ip:2181",
      ZKInterface::TIMEOUT).and_return(baz)
    ZKInterface.init_to_ip("public_ip", "public_ip")
    assert_equal(nil, djinn.write_our_node_info)
  end

  def test_update_local_nodes
    role = {
      "public_ip" => "public_ip",
      "private_ip" => "private_ip",
      "jobs" => ["shadow"],
      "instance_id" => "instance_id"
    }

    djinn = Djinn.new
    djinn.my_index = 0
    djinn.nodes = [DjinnJobData.new(role, "appscale")]
    djinn.last_updated = 0
    djinn.done_loading = true

    failure = {:rc => -1}
    all_ok = {:rc => 0, :stat => flexmock(:exists => true)}

    baz = flexmock("baz")

    # Mocks for lock acquisition / release
    baz.should_receive(:get).with(
      :path => ZKInterface::APPCONTROLLER_PATH).
      and_return({:stat => flexmock(:exists => true)})

    baz.should_receive(:create).with(
      :path => ZKInterface::APPCONTROLLER_LOCK_PATH, 
      :ephemeral => ZKInterface::EPHEMERAL,
      :data => JSON.dump("public_ip")).and_return(failure, all_ok)
    baz.should_receive(:get).with(
      :path => ZKInterface::APPCONTROLLER_LOCK_PATH).
      and_return({:rc => 0, :data => JSON.dump("public_ip")})
    baz.should_receive(:delete).with(
      :path => ZKInterface::APPCONTROLLER_LOCK_PATH).
      and_return(all_ok)

    # Mocks for ips file
    json_data = JSON.dump({'last_updated' => 1, 'ips' => ['public_ip']})
    baz.should_receive(:get).with(:path => ZKInterface::IP_LIST).
      and_return({:rc => 0, :data => json_data})

    baz.should_receive(:get).with(
      :path => "#{ZKInterface::APPCONTROLLER_NODE_PATH}/public_ip/live").
      and_return(all_ok)

    # Mocks for ip file - we have a new role here, so we're expecting
    # this method to stop the shadow role (set above), and start
    # memcache, as set below.
    new_data = {
      "public_ip" => "public_ip",
      "private_ip" => "private_ip",
      "jobs" => ["memcache"],
      "instance_id" => "instance_id"
    }

    path = "#{ZKInterface::APPCONTROLLER_NODE_PATH}/public_ip/job_data"
    baz.should_receive(:get).with(
      :path => path).and_return({:rc => 0, :data => JSON.dump(new_data)})

    # Mocks for done_loading file, which we will initially set to false,
    # load the new roles, then set to true
    done_loading = "#{ZKInterface::APPCONTROLLER_NODE_PATH}/public_ip/done_loading"
    baz.should_receive(:get).with(:path => done_loading).
      and_return({:rc => 0, :stat => flexmock(:exists => true)})
    baz.should_receive(:set).with(:path => done_loading,
      :data => JSON.dump(false)).and_return(all_ok)
    baz.should_receive(:set).with(:path => done_loading,
      :data => JSON.dump(true)).and_return(all_ok)

    flexmock(HelperFunctions).should_receive(:get_all_local_ips).
      and_return(["private_ip"])

    flexmock(MonitInterface).should_receive(:start).and_return()

    flexmock(HelperFunctions).should_receive(:sleep_until_port_is_open).
      and_return()
    flexmock(Zookeeper).should_receive(:new).with("public_ip:2181",
      ZKInterface::TIMEOUT).and_return(baz)
    ZKInterface.init_to_ip("public_ip", "public_ip")

    # make sure the appcontroller does an update
    assert_equal("UPDATED", djinn.update_local_nodes())

    # also make sure that the last_updated time updates to the
    # value the appcontroller receives from ZK
    assert_equal(1, djinn.last_updated)

    # make sure the appcontroller doesn't update
    # since there's no new information
    assert_equal("NOT UPDATED", djinn.update_local_nodes())

    # finally, since done_loading can change as we start or stop roles,
    # make sure it got set back to true when it's done
    assert_equal(true, djinn.done_loading)
  end

  def test_ensure_all_roles_are_running
    my_role = {
      "public_ip" => "public_ip",
      "private_ip" => "private_ip",
      "jobs" => ["open"],
      "instance_id" => "instance_id"
    }

    new_role = {
      "public_ip" => "public_ip",
      "private_ip" => "private_ip",
      "jobs" => ["shadow"],
      "instance_id" => "instance_id"
    }

    other_role = {
      "public_ip" => "public_ip2",
      "private_ip" => "private_ip2",
      "jobs" => ["shadow"],
      "instance_id" => "instance_id"
    }

    not_done_loading_role = {
      "public_ip" => "public_ip3",
      "private_ip" => "private_ip3",
      "jobs" => ["appengine"],
      "instance_id" => "instance_id"
    }

    my_node = DjinnJobData.new(my_role, "appscale")
    nodes = [my_node, DjinnJobData.new(other_role, "appscale"), 
      DjinnJobData.new(not_done_loading_role, "appscale")]
    new_node = DjinnJobData.new(new_role, "appscale")
 
    failure = {:rc => -1}
    all_ok = {:rc => 0}

    baz = flexmock("baz")

    # Mocks for lock acquisition / release
    baz.should_receive(:get).with(
      :path => ZKInterface::APPCONTROLLER_PATH).
      and_return({:stat => flexmock(:exists => true)})

    baz.should_receive(:create).with(
      :path => ZKInterface::APPCONTROLLER_LOCK_PATH, 
      :ephemeral => ZKInterface::EPHEMERAL,
      :data => JSON.dump("public_ip")).and_return(failure, all_ok)
    baz.should_receive(:get).with(
      :path => ZKInterface::APPCONTROLLER_LOCK_PATH).
      and_return({:rc => 0, :data => JSON.dump("public_ip")})
    baz.should_receive(:delete).with(
      :path => ZKInterface::APPCONTROLLER_LOCK_PATH).
      and_return(all_ok)

    # Mocks for ips file - the first time, all ips are up
    # but the second time, we've removed node2
    ips1 = JSON.dump({'ips' => ['public_ip', 'public_ip2', 'public_ip3'], 
      'last_updated' => 1})
    ip_list1 = {:rc => 0, :data => ips1, :stat => flexmock(:exists => true)}

    ips2 = JSON.dump({'ips' => ['public_ip', 'public_ip3'], 
      'last_updated' => 1})
    ip_list2 = {:rc => 0, :data => ips2, :stat => flexmock(:exists => true)}

    baz.should_receive(:get).with(
      :path => ZKInterface::IP_LIST).and_return(ip_list1, ip_list2)

    # Mocks for is node done loading
    baz.should_receive(:get).with(
      :path => ZKInterface::APPCONTROLLER_NODE_PATH).
      and_return({:stat => flexmock(:exists => true)})

    # ac1 has finished loading
    loading_file1 = "#{ZKInterface::APPCONTROLLER_NODE_PATH}/public_ip/done_loading"
    baz.should_receive(:get).with(
      :path => loading_file1).
      and_return({:stat => flexmock(:exists => true),
        :rc => 0, :data => 'true'})

    # and ac2 has finished loading
    loading_file2 = "#{ZKInterface::APPCONTROLLER_NODE_PATH}/public_ip2/done_loading"
    baz.should_receive(:get).with(
      :path => loading_file2).
      and_return({:stat => flexmock(:exists => true),
        :rc => 0, :data => 'true'})

    # but ac3 hasn't finished loading yet
    loading_file3 = "#{ZKInterface::APPCONTROLLER_NODE_PATH}/public_ip3/done_loading"
    baz.should_receive(:get).with(
      :path => loading_file3).
      and_return({:stat => flexmock(:exists => true),
        :rc => 0, :data => 'false'})

    # Mocks for is node live
    # first node (our node) is alive
    live_file = "#{ZKInterface::APPCONTROLLER_NODE_PATH}/public_ip/live"
    baz.should_receive(:get).with(
      :path => live_file).
      and_return({:stat => flexmock(:exists => true),
        :rc => 0, :data => ZKInterface::DUMMY_DATA})

    # but let's say the second has failed
    ip2_path = "#{ZKInterface::APPCONTROLLER_NODE_PATH}/public_ip2"
    live_file = "#{ip2_path}/live"
    baz.should_receive(:get).with(
      :path => live_file).
      and_return({:stat => flexmock(:exists => false), :rc => 0})

    # so now the first appcontroller will ask for the jobs that ac2 was
    # running - here are mocks to return that info
    job_data_file = "#{ip2_path}/job_data"
    baz.should_receive(:get).with(:path => job_data_file).
      and_return({:stat => flexmock(:exists => true), :rc => 0,
        :data => JSON.dump(other_role)})

    # the appcontroller then should find out what apps AC2 is running,
    # and then delete them from the UserAppServer
    app_instance_file = "#{ip2_path}/#{ZKInterface::APP_INSTANCE}"
    app_info = {'app_name' => 'baz', 'ip' => 'public_ip2', 'port' => '8080'}
    baz.should_receive(:get).with(:path => app_instance_file).
      and_return({:stat => flexmock(:exists => true), :rc => 0,
        :data => JSON.dump([app_info])})

    flexmock(UserAppClient).new_instances { |instance|
      instance.should_receive(:delete_instance).
        with('baz', 'public_ip2', '8080').and_return('OK')
    }

    # the appcontroller should start by deleting all the info for ac2
    # from zk, so put in mocks for each of those operations
    baz.should_receive(:get_children).with(
      :path => ip2_path).
      and_return({:children => ['job_data', 'done_loading', 
        ZKInterface::APP_INSTANCE]})

    baz.should_receive(:get_children).with(
      :path => "#{ip2_path}/job_data").
      and_return({:children => nil})

    baz.should_receive(:get_children).with(
      :path => "#{ip2_path}/done_loading").
      and_return({:children => nil})

    baz.should_receive(:get_children).with(
      :path => "#{ip2_path}/#{ZKInterface::APP_INSTANCE}").
      and_return({:children => nil})

    baz.should_receive(:delete).with(
      :path => ip2_path).and_return(all_ok)

    # Next, we should be writing a new ips file that doesn't
    # include ip2, so mock out the ZK write there
    flexmock(Time).should_receive(:now).and_return(
      flexmock(:to_i => "NOW"))
    new_data = '{"ips":["public_ip","public_ip3"],"last_updated":"NOW"}'

    flexmock(JSON).should_receive(:dump).with(
      {"ips" => ["public_ip", "public_ip3"], "last_updated" => "NOW"}).
      and_return(new_data)

    baz.should_receive(:set).with(:path => ZKInterface::IP_LIST,
      :data => new_data).and_return(all_ok)

    # Finally, we should be telling the first open node (our node) to take
    # on the fallen Shadow role
    flexmock(JSON).should_receive(:dump).with(Hash).
      and_return("{\"instance_id\":\"instance_id\",\"private_ip\":\"private_ip\",\"jobs\":[\"shadow\"],\"ssh_key\":\"/etc/appscale/keys/cloud1/appscale.key\",\"cloud\":\"cloud1\",\"public_ip\":\"public_ip\",\"disk\":null}")
    baz.should_receive(:get).with(
      :path => "#{ZKInterface::APPCONTROLLER_NODE_PATH}/public_ip/job_data").
      and_return({:rc => 0, :data => JSON.dump(my_node.to_hash()),
        :stat => flexmock(:exists => true)})

    baz.should_receive(:set).with(
      :path => "#{ZKInterface::APPCONTROLLER_NODE_PATH}/public_ip/job_data",
      :data => JSON.dump(new_node.to_hash())).and_return({:rc => 0})

    flexmock(JSON).should_receive(:dump).
      with(false).and_return('false')
    baz.should_receive(:set).with(
      :path => "#{ZKInterface::APPCONTROLLER_NODE_PATH}/public_ip/done_loading",
      :data => JSON.dump(false)).and_return(all_ok)

    # TODO(cgb): this mocks out the lock file's contents,
    # so it should be up with the lock file mock, but it messes up everything
    # after that uses json
    flexmock(JSON).should_receive(:dump).
      with("public_ip").and_return('"public_ip"')

    # mocks for zookeeper initialization
    flexmock(HelperFunctions).should_receive(:sleep_until_port_is_open).
      and_return() 
    flexmock(Zookeeper).should_receive(:new).with("public_ip:2181",
      ZKInterface::TIMEOUT).and_return(baz)

    djinn = Djinn.new
    djinn.my_index = 0
    djinn.nodes = nodes
    djinn.userappserver_private_ip = 'uaserver_ip'
    ZKInterface.init_to_ip("public_ip", "public_ip")

    # we should get back a list of the roles we recovered - in this
    # case it's just shadow
    assert_equal([["shadow"]], djinn.ensure_all_roles_are_running())
  end

  def test_get_lock_when_somebody_else_has_it
    # this test ensures that if we don't initially have the lock, we
    # wait for it and try again

    boo = 1

    mocked_zk = flexmock("zk")

    # Mocks for Appcontroller root node
    file_exists = {:rc => 0, :data => ZKInterface::DUMMY_DATA,
      :stat => flexmock(:exists => true)}
    mocked_zk.should_receive(:get).with(
      :path => ZKInterface::APPCONTROLLER_PATH).and_return(file_exists)

    # Mocks for AppController lock file - the create should fail the first
    # time since the file already exists, and the second time, it should
    # succeed because the file doesn't exist (they've released the lock)
    does_not_exist = {:rc => -1}
    all_ok = {:rc => 0}
    mocked_zk.should_receive(:create).times(2).with(
      :path => ZKInterface::APPCONTROLLER_LOCK_PATH,
      :ephemeral => ZKInterface::EPHEMERAL, :data => JSON.dump("public_ip")).
      and_return(does_not_exist, all_ok)

    # On the first get, the file exists (user2 has it)
    get_response = {:rc => 0, :data => JSON.dump("public_ip2")}
    mocked_zk.should_receive(:get).with(
      :path => ZKInterface::APPCONTROLLER_LOCK_PATH).
      and_return(get_response)

    # Finally, we should get rid of the lock once we're done with it
    mocked_zk.should_receive(:delete).with(
      :path => ZKInterface::APPCONTROLLER_LOCK_PATH).
      and_return(all_ok)

    # mock out ZooKeeper's init stuff
    flexmock(HelperFunctions).should_receive(:sleep_until_port_is_open).
      and_return() 
    flexmock(Zookeeper).should_receive(:new).with("public_ip:2181",
      ZKInterface::TIMEOUT).and_return(mocked_zk)

    ZKInterface.init_to_ip("public_ip", "public_ip")
    ZKInterface.lock_and_run {
      boo = 2
    }

    assert_equal(2, boo)
  end

  def test_start_roles_on_nodes_bad_input
    # Calling start_roles_on_nodes with something other than a Hash
    # isn't acceptable
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }

    djinn = Djinn.new()
    expected = Djinn::BAD_INPUT_MSG
    actual = djinn.start_roles_on_nodes("", @secret)
    assert_equal(expected, actual)
  end


  def test_start_roles_on_nodes_in_cluster
    ips_hash = JSON.dump({'appengine' => ['node-1', 'node-2']})
    djinn = Djinn.new()
    djinn.nodes = [1, 2]
    expected = {'node-1' => ['appengine'], 'node-2' => ['appengine']}
    actual = djinn.start_roles_on_nodes(ips_hash, @secret)
    assert_equal(expected, actual)
  end

  def test_start_new_roles_on_nodes_in_cluster
    # try adding two new nodes to an appscale deployment, assuming that
    # the machines are already running and have appscale installed
    ips_to_roles = {'1.2.3.4' => ['appengine'], '1.2.3.5' => ['appengine']}

    # assume the machines are running and that we can scp and ssh to them
    flexmock(HelperFunctions).should_receive(:is_port_open?).
      with('1.2.3.4', Djinn::SSH_PORT, HelperFunctions::DONT_USE_SSL).
      and_return(true)
    flexmock(HelperFunctions).should_receive(:is_port_open?).
      with('1.2.3.5', Djinn::SSH_PORT, HelperFunctions::DONT_USE_SSL).
      and_return(true)

    key_location = "#{HelperFunctions::APPSCALE_KEYS_DIR}/boo.key"
    flexmock(FileUtils).should_receive(:chmod).
      with(HelperFunctions::CHMOD_READ_ONLY, key_location).and_return()
    flexmock(HelperFunctions).should_receive(:shell).with(/\Ascp/).
      and_return()
    flexmock(File).should_receive(:exists?).
      with(/\A#{HelperFunctions::APPSCALE_CONFIG_DIR}\/retval-/).
      and_return(true)
    flexmock(File).should_receive(:open).
      with(/\A#{HelperFunctions::APPSCALE_CONFIG_DIR}\/retval-/, Proc).
      and_return("0\n")
    flexmock(HelperFunctions).should_receive(:shell).with(/\Arm -fv/).
      and_return()

    # for individual ssh commands, the mock depends on what we're mocking
    # out - we don't just assume success
    flexmock(Kernel).should_receive(:system).with(/\Assh.* 'mkdir -p/).
      and_return('')

    # next, mock out our checks to see if the new boxes are AppScale
    # VMs and assume they are
    flexmock(HelperFunctions).should_receive(:shell).
      with(/\Assh.* root@1.2.3.4 'ls #{HelperFunctions::APPSCALE_CONFIG_DIR}/).and_return("0\n")
    flexmock(HelperFunctions).should_receive(:shell).
      with(/\Assh.* root@1.2.3.5 'ls #{HelperFunctions::APPSCALE_CONFIG_DIR}/).and_return("0\n")

    # mock out our attempts to rsync over to the new boxes
    flexmock(Djinn).should_receive(:log_run).with(/\Arsync.* root@1.2.3.4/).and_return()
    flexmock(Djinn).should_receive(:log_run).with(/\Arsync.* root@1.2.3.5/).and_return()

    # when the appcontroller asks those boxes where APPSCALE_HOME is,
    # let's assume they say it's in /usr/appscale
    flexmock(HelperFunctions).should_receive(:shell).
      with(/\Assh.* root@1.2.3.4 'cat #{HelperFunctions::APPSCALE_CONFIG_DIR}\/home/).and_return("/usr/appscale\n")
    flexmock(HelperFunctions).should_receive(:shell).
      with(/\Assh.* root@1.2.3.5 'cat #{HelperFunctions::APPSCALE_CONFIG_DIR}\/home/).and_return("/usr/appscale\n")

    # next, the appcontroller removes the json service metadata file
    # off of each of these nodes - assume it succeeds
    flexmock(Kernel).should_receive(:system).with(/\Assh.* root@1.2.3.4 'rm -rf #{HelperFunctions::APPSCALE_CONFIG_DIR}/).
      and_return('')
    flexmock(Kernel).should_receive(:system).with(/\Assh.* root@1.2.3.5 'rm -rf #{HelperFunctions::APPSCALE_CONFIG_DIR}/).
      and_return('')

    # finally, mock out when the appcontroller starts monit and the
    # remote appcontrollers on the other boxes
    flexmock(File).should_receive(:open).with(/\A\/tmp\/monit/, "w+", Proc).
      and_return()
    flexmock(HelperFunctions).should_receive(:shell).with(/monit/)
    flexmock(Kernel).should_receive(:system).
      with(/\Assh.* root@1.2.3.4 'rm -rf \/tmp\/monit/).and_return('')
    flexmock(Kernel).should_receive(:system).
      with(/\Assh.* root@1.2.3.5 'rm -rf \/tmp\/monit/).and_return('')
    flexmock(Djinn).should_receive(:log_run).with(/\Arm -rf \/tmp\/monit/).
      and_return()

    # and assume that the appcontrollers start up fine
    flexmock(HelperFunctions).should_receive(:is_port_open?).
      with('1.2.3.4', Djinn::SERVER_PORT, HelperFunctions::USE_SSL).
      and_return(true)
    flexmock(HelperFunctions).should_receive(:is_port_open?).
      with('1.2.3.5', Djinn::SERVER_PORT, HelperFunctions::USE_SSL).
      and_return(true)

    # add the login role here to force our node to regenerate its
    # nginx config files
    original_node_info = {
      "public_ip" => "1.2.3.3",
      "private_ip" => "1.2.3.3",
      "jobs" => ["shadow", "login"],
      "instance_id" => "id1",
      "cloud" => "cloud1",
      "ssh_key" => "/etc/appscale/keys/cloud1/boo.key",
      "disk" => nil
    }

    node1_info = {
      "public_ip" => "1.2.3.4",
      "private_ip" => "1.2.3.4",
      "jobs" => ["appengine"],
      "cloud" => "cloud1",
      "ssh_key" => "/etc/appscale/keys/cloud1/boo.key",
      "disk" => nil
    }

    node2_info = {
      "public_ip" => "1.2.3.5",
      "private_ip" => "1.2.3.5",
      "jobs" => ["appengine"],
      "cloud" => "cloud1",
      "ssh_key" => "/etc/appscale/keys/cloud1/boo.key",
      "disk" => nil
    }

    original_node = DjinnJobData.new(original_node_info, "boo")
    new_node1 = DjinnJobData.new(node1_info, "boo")
    new_node2 = DjinnJobData.new(node2_info, "boo")
    all_nodes_serialized = JSON.dump([original_node.to_hash(),
      new_node2.to_hash(), new_node1.to_hash()])

    options = {'keyname' => 'boo', 'user_commands' => []}
    options_as_array = options.to_a.flatten
    no_apps = []

    # and that the appcontrollers receive the initial message to start
    # up from our appcontroller
    flexmock(AppControllerClient).new_instances { |instance|
      instance.should_receive(:set_parameters).with(all_nodes_serialized,
        options_as_array, no_apps).and_return("OK")
    }

    # the appcontroller will update its local /etc/hosts file
    # and /etc/hostname file with info about the new node and its own
    # node
    flexmock(File).should_receive(:open).with("/etc/hosts", "w+", Proc).
      and_return()
    flexmock(File).should_receive(:open).with("/etc/hostname", "w+", Proc).
      and_return()
    flexmock(Djinn).should_receive(:log_run).with("/bin/hostname appscale-image0").
      and_return()

    # next, nginx will rewrite its config files for the one app we
    # have running
    flexmock(HelperFunctions).should_receive(:parse_static_data).with('booapp').
      and_return([])
    app_dir = "/var/apps/booapp/app"
    app_yaml = "#{app_dir}/app.yaml"
    flexmock(YAML).should_receive(:load_file).with(app_yaml).
      and_return({})

    nginx_conf = "/usr/local/nginx/conf/sites-enabled/booapp.conf"
    flexmock(File).should_receive(:open).with(nginx_conf, "w+", Proc).and_return()
    flexmock(Nginx).should_receive(:is_running?).and_return(true)

    # mock out updating the firewall config
    ip_list = "#{Djinn::CONFIG_FILE_LOCATION}/all_ips"
    flexmock(File).should_receive(:open).with(ip_list, "w+", Proc).and_return()
    flexmock(Djinn).should_receive(:log_run).with(/bash .*firewall.conf/)

    flexmock(HelperFunctions).should_receive(:shell).and_return()
    djinn = Djinn.new()
    djinn.nodes = [original_node]
    djinn.my_index = 0
    djinn.options = options
    djinn.apps_loaded = ["booapp"]
    djinn.app_info_map = {
      'booapp' => {
        'nginx' => Nginx::START_PORT + 1
      }
    }
    actual = djinn.start_new_roles_on_nodes_in_xen(ips_to_roles)
    assert_equal(node2_info['public_ip'], actual[0]['public_ip'])
    assert_equal(node1_info['public_ip'], actual[1]['public_ip'])
  end

  def test_start_new_roles_on_nodes_in_cloud
    # mock out getting our ip address
    flexmock(HelperFunctions).should_receive(:shell).with("ifconfig").
      and_return("inet addr:1.2.3.4 ")

    # try adding two new nodes to an appscale deployment, assuming that
    # the machines are already running and have appscale installed
    ips_to_roles = {'node-1' => ['appengine'], 'node-2' => ['appengine']}

    # mock out spawning the two new machines, assuming they get IPs
    # 1.2.3.4 and 1.2.3.5
    flexmock(InfrastructureManagerClient).new_instances { |instance|
      instance.should_receive(:make_call).
      with(InfrastructureManagerClient::NO_TIMEOUT,
        InfrastructureManagerClient::RETRY_ON_FAIL, "run_instances",
        Proc).
      and_return({'reservation_id' => '0123456'})

    # let's say that the first time we do 'describe-instances', the
    # machines aren't initially ready, and that they become ready the
    # second time
    new_two_nodes_info = {
      'public_ips' => ['1.2.3.4', '1.2.3.5'],
      'private_ips' => ['1.2.3.4', '1.2.3.5'],
      'instance_ids' => ['i-ABCDEFG', 'i-HIJKLMN'],
    }

    pending = {'state' => 'pending'}
    ready = {'state' => 'running', 'vm_info' => new_two_nodes_info}
      instance.should_receive(:make_call).
      with(InfrastructureManagerClient::NO_TIMEOUT,
        InfrastructureManagerClient::RETRY_ON_FAIL, "describe_instances",
        Proc).
      and_return(pending, ready)
    }

    # assume the machines are running and that we can scp and ssh to them
    flexmock(HelperFunctions).should_receive(:is_port_open?).
      with('1.2.3.4', Djinn::SSH_PORT, HelperFunctions::DONT_USE_SSL).
      and_return(true)
    flexmock(HelperFunctions).should_receive(:is_port_open?).
      with('1.2.3.5', Djinn::SSH_PORT, HelperFunctions::DONT_USE_SSL).
      and_return(true)

    key_location = "#{HelperFunctions::APPSCALE_KEYS_DIR}/boo.key"
    flexmock(FileUtils).should_receive(:chmod).
      with(HelperFunctions::CHMOD_READ_ONLY, key_location).and_return()
    flexmock(HelperFunctions).should_receive(:shell).with(/\Ascp/).
      and_return()
    flexmock(File).should_receive(:exists?).
      with(/\A#{HelperFunctions::APPSCALE_CONFIG_DIR}\/retval-/).
      and_return(true)
    flexmock(File).should_receive(:open).
      with(/\A#{HelperFunctions::APPSCALE_CONFIG_DIR}\/retval-/, Proc).
      and_return("0\n")
    flexmock(HelperFunctions).should_receive(:shell).with(/\Arm -fv/).
      and_return()

    # for individual ssh commands, the mock depends on what we're mocking
    # out - we don't just assume success
    flexmock(Kernel).should_receive(:system).with(/\Assh.* 'mkdir -p/).
      and_return('')

    # next, mock out our checks to see if the new boxes are AppScale
    # VMs and assume they are
    flexmock(HelperFunctions).should_receive(:shell).
      with(/\Assh.* root@1.2.3.4 'ls #{HelperFunctions::APPSCALE_CONFIG_DIR}/).and_return("0\n")
    flexmock(HelperFunctions).should_receive(:shell).
      with(/\Assh.* root@1.2.3.5 'ls #{HelperFunctions::APPSCALE_CONFIG_DIR}/).and_return("0\n")

    # mock out our attempts to rsync over to the new boxes
    flexmock(HelperFunctions).should_receive(:shell).with(/\Arsync.* root@1.2.3.4/).and_return()
    flexmock(HelperFunctions).should_receive(:shell).with(/\Arsync.* root@1.2.3.5/).and_return()

    # when the appcontroller asks those boxes where APPSCALE_HOME is,
    # let's assume they say it's in /usr/appscale
    flexmock(HelperFunctions).should_receive(:shell).
      with(/\Assh.* root@1.2.3.4 'cat #{HelperFunctions::APPSCALE_CONFIG_DIR}\/home/).and_return("/usr/appscale\n")
    flexmock(HelperFunctions).should_receive(:shell).
      with(/\Assh.* root@1.2.3.5 'cat #{HelperFunctions::APPSCALE_CONFIG_DIR}\/home/).and_return("/usr/appscale\n")

    # next, the appcontroller removes the json service metadata file
    # off of each of these nodes - assume it succeeds
    flexmock(Kernel).should_receive(:system).with(/\Assh.* root@1.2.3.4 'rm -rf #{HelperFunctions::APPSCALE_CONFIG_DIR}/).
      and_return('')
    flexmock(Kernel).should_receive(:system).with(/\Assh.* root@1.2.3.5 'rm -rf #{HelperFunctions::APPSCALE_CONFIG_DIR}/).
      and_return('')

    # finally, mock out when the appcontroller starts monit and the
    # remote appcontrollers on the other boxes
    flexmock(File).should_receive(:open).with(/\A\/tmp\/monit/, "w+", Proc).
      and_return()
    flexmock(HelperFunctions).should_receive(:shell).with(/monit/)
    flexmock(Kernel).should_receive(:system).
      with(/\Assh.* root@1.2.3.4 'rm -rf \/tmp\/monit/).and_return('')
    flexmock(Kernel).should_receive(:system).
      with(/\Assh.* root@1.2.3.5 'rm -rf \/tmp\/monit/).and_return('')
    flexmock(Djinn).should_receive(:log_run).with(/\Arm -rf \/tmp\/monit/).
      and_return()

    # and assume that the appcontrollers start up fine
    flexmock(HelperFunctions).should_receive(:is_port_open?).
      with('1.2.3.4', Djinn::SERVER_PORT, HelperFunctions::USE_SSL).
      and_return(true)
    flexmock(HelperFunctions).should_receive(:is_port_open?).
      with('1.2.3.5', Djinn::SERVER_PORT, HelperFunctions::USE_SSL).
      and_return(true)

    original_node_info = {
      "public_ip" => "1.2.3.3",
      "private_ip" => "1.2.3.3",
      "jobs" => ["shadow"],
      "instance_id" => "i-000000"
    }

    node1_info = {
      "public_ip" => "1.2.3.4",
      "private_ip" => "1.2.3.4",
      "jobs" => ["appengine"],
      "instance_id" => "i-ABCDEFG",
      "disk" => nil
    }

    node2_info = {
      "public_ip" => "1.2.3.5",
      "private_ip" => "1.2.3.5",
      "jobs" => ["appengine"],
      "instance_id" => "i-HIJKLMN",
      "disk" => nil
    }

    original_node = DjinnJobData.new(original_node_info, "boo")
    new_node1 = DjinnJobData.new(node1_info, "boo")
    new_node2 = DjinnJobData.new(node2_info, "boo")
    all_nodes_serialized = JSON.dump([original_node.to_hash(),
      new_node1.to_hash(), new_node2.to_hash()])

    options = {'keyname' => 'boo', 'user_commands' => []}
    options_as_array = options.to_a.flatten
    no_apps = []

    # and that the appcontrollers receive the initial message to start
    # up from our appcontroller
    flexmock(AppControllerClient).new_instances { |instance|
      instance.should_receive(:set_parameters).with(all_nodes_serialized,
        options_as_array, no_apps).and_return("OK")
    }

    # lastly, the appcontroller will update its local /etc/hosts file
    # and /etc/hostname file with info about the new node and its own
    # node
    flexmock(File).should_receive(:open).with("/etc/hosts", "w+", Proc).
      and_return()
    flexmock(File).should_receive(:open).with("/etc/hostname", "w+", Proc).
      and_return()
    flexmock(Djinn).should_receive(:log_run).with("/bin/hostname appscale-image0").
      and_return()

    # mock out updating the firewall config
    ip_list = "#{Djinn::CONFIG_FILE_LOCATION}/all_ips"
    flexmock(File).should_receive(:open).with(ip_list, "w+", Proc).and_return()
    flexmock(Djinn).should_receive(:log_run).with(/bash .*firewall.conf/)

    djinn = Djinn.new()
    djinn.nodes = [original_node]
    djinn.my_index = 0
    djinn.options = options
    actual = djinn.start_new_roles_on_nodes_in_cloud(ips_to_roles)
    assert_equal(true, actual.include?(node1_info))
    assert_equal(true, actual.include?(node2_info))
  end

  def test_log_sending
    # mock out getting our ip address
    flexmock(HelperFunctions).should_receive(:shell).with("ifconfig").
      and_return("inet addr:1.2.3.4 ")

    node_info = {
      "public_ip" => "1.2.3.3",
      "private_ip" => "1.2.3.3",
      "jobs" => ["shadow", "login"],
      "instance_id" => "i-000000"
    }
    node = DjinnJobData.new(node_info, "boo")

    djinn = Djinn.new()
    djinn.nodes = [node]
    djinn.my_index = 0

    # test that the buffer is initially empty
    assert_equal([], Djinn.get_logs_buffer())

    # do a couple log statements to populate the buffer
    Djinn.log_fatal("one")
    Djinn.log_fatal("two")
    Djinn.log_fatal("three")

    # and make sure they're in there
    assert_equal(3, Djinn.get_logs_buffer().length)

    # mock out sending the logs
    flexmock(Net::HTTP).new_instances { |instance|
      instance.should_receive(:post).with("/logs/upload", String, Hash)
    }

    # flush the buffer
    djinn.flush_log_buffer()

    # make sure our buffer is empty again
    assert_equal([], Djinn.get_logs_buffer())
  end

  def test_send_request_info_to_dashboard_when_dash_is_up
    # mock out getting our ip address
    flexmock(HelperFunctions).should_receive(:shell).with("ifconfig").
      and_return("inet addr:1.2.3.4 ")

    node_info = "1.2.3.3:1.2.3.3:shadow:login:i-000000:cloud1"
    node = DjinnJobData.new(node_info, "boo")

    djinn = Djinn.new()
    djinn.nodes = [node]
    djinn.my_index = 0

    # mock out sending the request info
    flexmock(Net::HTTP).new_instances { |instance|
      instance.should_receive(:post).with("/apps/bazapp", String, Hash)
    }

    assert_equal(true, djinn.send_request_info_to_dashboard("bazapp", 0, 0))
  end

  def test_send_request_info_to_dashboard_when_dash_is_up
    # mock out getting our ip address
    flexmock(HelperFunctions).should_receive(:shell).with("ifconfig").
      and_return("inet addr:1.2.3.4 ")

    node_info = {
      "public_ip" => "1.2.3.3",
      "private_ip" => "1.2.3.3",
      "jobs" => ["shadow", "login"],
      "instance_id" => "i-000000"
    }
    node = DjinnJobData.new(node_info, "boo")

    djinn = Djinn.new()
    djinn.nodes = [node]
    djinn.my_index = 0

    # mock out sending the request info
    flexmock(Net::HTTP).new_instances { |instance|
      instance.should_receive(:post).with("/apps/bazapp", String, Hash).and_raise(Exception)
    }

    assert_equal(false, djinn.send_request_info_to_dashboard("bazapp", 0, 0))
  end

  def test_scale_appservers_across_nodes_with_no_action_taken
    # mock out getting our ip address
    flexmock(HelperFunctions).should_receive(:shell).with("ifconfig").
      and_return("inet addr:1.2.3.4 ")

    node_info = {
      "public_ip" => "1.2.3.3",
      "private_ip" => "1.2.3.3",
      "jobs" => ["shadow", "login"],
      "instance_id" => "i-000000"
    }
    node = DjinnJobData.new(node_info, "boo")

    djinn = Djinn.new()
    djinn.nodes = [node]
    djinn.my_index = 0
    
    # let's say there's one app running
    djinn.apps_loaded = ['bazapp']

    # and that it has not requested scaling
    flexmock(ZKInterface).should_receive(:get_scaling_requests_for_app).
      with('bazapp').and_return([])
    flexmock(ZKInterface).should_receive(:clear_scaling_requests_for_app).
      with('bazapp')

    # Finally, make sure that we didn't add any nodes
    assert_equal(0, djinn.scale_appservers_across_nodes())
  end

  def test_scale_appservers_across_nodes_and_scale_up_one_app
    # mock out getting our ip address
    flexmock(HelperFunctions).should_receive(:shell).with("ifconfig").
      and_return("inet addr:1.2.3.4 ")


    # Let's say that we've got two nodes - one is open so we can scale onto it.
    node_info = {
      "public_ip" => "1.2.3.3",
      "private_ip" => "1.2.3.3",
      "jobs" => ["shadow", "login"],
      "instance_id" => "i-000000"
    }

    open_node_info = {
      "public_ip" => "1.2.3.4",
      "private_ip" => "1.2.3.4",
      "jobs" => ["open"],
      "instance_id" => "i-000000"
    }

    node = DjinnJobData.new(node_info, "boo")
    open_node = DjinnJobData.new(open_node_info, "boo")

    djinn = Djinn.new()
    djinn.nodes = [node, open_node]
    djinn.my_index = 0
    djinn.options = { 'keyname' => 'boo' }
    
    # let's say there's one app running
    djinn.apps_loaded = ['bazapp']
    djinn.app_info_map = {
      'bazapp' => {
        'nginx' => 123
      }
    }

    # and that we haven't scaled up in a long time
    djinn.last_scaling_time = Time.utc(2000, "jan", 1, 20, 15, 1).to_i

    # and that two nodes have requested scaling
    flexmock(ZKInterface).should_receive(:get_scaling_requests_for_app).
      with('bazapp').and_return(['scale_up', 'scale_up'])
    flexmock(ZKInterface).should_receive(:clear_scaling_requests_for_app).
      with('bazapp')

    # assume the open node is done starting up
    flexmock(ZKInterface).should_receive(:is_node_done_loading?).
      with('1.2.3.4').and_return(true)

    # mock out adding the appengine role to the open node
    flexmock(ZKInterface).should_receive(:add_roles_to_node).
      with(["memcache", "taskqueue_slave", "appengine"], open_node, "boo")

    # mock out writing updated nginx config files
    flexmock(Nginx).should_receive(:write_fullproxy_app_config)
    flexmock(Nginx).should_receive(:reload)

    # Finally, make sure that we added a node
    assert_equal(1, djinn.scale_appservers_across_nodes())
  end


  def test_relocate_app_but_port_in_use_by_nginx
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    djinn = Djinn.new()
    djinn.app_info_map = {
      'another-app' => {
        'nginx' => 80,
        'nginx_https' => 443,
        'haproxy' => 10000,
        'appengine' => [20000]
      }
    }

    expected = "Error: Port in use by nginx for app another-app"
    assert_equal(expected, djinn.relocate_app('myapp', 80, 4380, @secret))
  end


  def test_relocate_app_but_port_in_use_by_nginx_https
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    djinn = Djinn.new()
    djinn.app_info_map = {
      'another-app' => {
        'nginx' => 80,
        'nginx_https' => 443,
        'haproxy' => 10000,
        'appengine' => [20000]
      }
    }

    expected = "Error: Port in use by nginx for app another-app"
    assert_equal(expected, djinn.relocate_app('myapp', 8080, 443, @secret))
  end


  def test_relocate_app_but_port_in_use_by_haproxy
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    djinn = Djinn.new()
    djinn.app_info_map = {
      'another-app' => {
        'nginx' => 80,
        'nginx_https' => 443,
        'haproxy' => 4380,
        'appengine' => [20000]
      }
    }

    expected = "Error: Port in use by haproxy for app another-app"
    assert_equal(expected, djinn.relocate_app('myapp', 8080, 4380, @secret))
  end


  def test_relocate_app_but_port_in_use_by_appserver
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    djinn = Djinn.new()
    djinn.app_info_map = {
      'another-app' => {
        'nginx' => 80,
        'nginx_https' => 443,
        'haproxy' => 10000,
        'appengine' => [8080]
      }
    }

    expected = "Error: Port in use by AppServer for app another-app"
    assert_equal(expected, djinn.relocate_app('myapp', 8080, 4380, @secret))
  end


  def test_get_property
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    djinn = Djinn.new()

    # First, make sure that using a regex that matches nothing returns an empty
    # Hash.
    empty_hash = JSON.dump({})
    assert_equal(empty_hash, djinn.get_property("not-a-variable-name", @secret))

    # Next, we know that there's a variable called 'state'. Make sure that using
    # it as the regex actually returns that variable (and only that).
    djinn.state = "AppController is taking it easy today"
    state_only = JSON.dump({'state' => djinn.state})
    assert_equal(state_only, djinn.get_property('state', @secret))

    # Finally, passing in the regex userappserver_*_ip should return both the
    # public and private UserAppServer IPs.
    djinn.userappserver_public_ip = "public-ip"
    djinn.userappserver_private_ip = "private-ip"
    userappserver_ips = JSON.dump({
      'userappserver_public_ip' => 'public-ip',
      'userappserver_private_ip' => 'private-ip'
    })
    assert_equal(userappserver_ips, djinn.get_property('userappserver_.*_ip',
      @secret))
  end


  def test_set_property
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    djinn = Djinn.new()

    # Verify that setting a property that doesn't exist returns an error.
    assert_equal(Djinn::KEY_NOT_FOUND, djinn.set_property('not-a-real-key',
      'value', @secret))

    # Verify that setting a property that we allow users to set
    # results in subsequent get calls seeing the correct value.
    djinn.state = "AppController is taking it easy today"
    new_state = "AppController is back to work"
    assert_equal('OK', djinn.set_property('state', new_state, @secret))

    state_only = JSON.dump({'state' => new_state})
    assert_equal(state_only, djinn.get_property('state', @secret))
  end


end
