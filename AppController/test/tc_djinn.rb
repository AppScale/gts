# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..")
require 'djinn'

require 'rubygems'
require 'flexmock/test_unit'


class TestDjinn < Test::Unit::TestCase
  def setup
    kernel = flexmock(Kernel)
    kernel.should_receive(:puts).and_return()
    kernel.should_receive(:sleep).and_return()

    djinn_class = flexmock(Djinn)
    djinn_class.should_receive(:log_debug).and_return()
    djinn_class.should_receive(:log_run).and_return()

    @secret = "baz"
    flexmock(HelperFunctions).should_receive(:read_file).
      with("/etc/appscale/secret.key", true).and_return(@secret)

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
    assert_equal(BAD_SECRET_MSG, djinn.kill(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.set_parameters("", "", "", @secret))
    assert_equal(BAD_SECRET_MSG, djinn.set_apps([], @secret))
    assert_equal(BAD_SECRET_MSG, djinn.status(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_stats(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.stop_app(@app, @secret))
    assert_equal(BAD_SECRET_MSG, djinn.update([@app], @secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_all_public_ips(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.job_start(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.get_online_users_list(@secret))
    assert_equal(BAD_SECRET_MSG, djinn.done_uploading(@app, "/tmp/app", 
      @secret))
    assert_equal(BAD_SECRET_MSG, djinn.is_app_running(@app, @secret))
    assert_equal(BAD_SECRET_MSG, djinn.add_role("baz", @secret))
    assert_equal(BAD_SECRET_MSG, djinn.remove_role("baz", @secret))
    assert_equal(BAD_SECRET_MSG, djinn.start_new_roles_on_nodes([], '', 
      @secret))
  end


  def test_get_role_info
    role1 = "public_ip:private_ip:shadow:instance_id:cloud1"
    role2 = "public_ip2:private_ip2:appengine:instance_id2:cloud2"
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

    role1_to_hash, role2_to_hash = djinn.get_role_info(@secret)
  
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
    assert_equal("cloud2", role2_to_hash['cloud'])
  end


  def test_set_params_w_bad_params
    flexmock(HelperFunctions).should_receive(:local_ip).
      and_return("127.0.0.1")

    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    djinn = Djinn.new

    # Try passing in params that aren't Arrays, the required type
    bad_param = ""
    result_1 = djinn.set_parameters(bad_param, [], [], @secret)
    assert_equal(true, result_1.include?("Error: djinn_locations"))

    result_2 = djinn.set_parameters([], bad_param, [], @secret)
    assert_equal(true, result_2.include?("Error: database_credentials"))

    result_3 = djinn.set_parameters([], [], bad_param, @secret)
    assert_equal(true, result_3.include?("Error: app_names"))

    # Since DB credentials will be turned from an Array to a Hash,
    # it should have an even number of items in it
    bad_credentials = ['a']
    result_4 = djinn.set_parameters(bad_credentials, bad_credentials, 
      bad_credentials, @secret)
    expected_1 = "Error: DB Credentials wasn't of even length"
    assert_equal(true, result_4.include?(expected_1))

    # Now try credentials with an even number of items, but not all the
    # required parameters
    better_credentials = ['a', 'b']
    result_5 = djinn.set_parameters(better_credentials, better_credentials,
      better_credentials, @secret)
    assert_equal("Error: Credential format wrong", result_5)

    # Now try good credentials, but with bad node info
    credentials = ['table', 'cassandra', 'hostname', '127.0.0.1', 'ips', '', 
      'keyname', 'appscale']
    bad_node_info = [1]
    assert_raises(SystemExit) {
      djinn.set_parameters(bad_node_info, credentials, better_credentials,
        @secret)
    }

    # Finally, try credentials with info in the right format, but where it
    # refers to nodes that aren't in our deployment
    one_node_info = ['public_ip:private_ip:some_role:instance_id:cloud1']
    app_names = []

    udpsocket = flexmock(UDPSocket)
    udpsocket.should_receive(:open).and_return("not any ips above")

    expected_2 = "Error: Couldn't find me in the node map"
    result_6 = djinn.set_parameters(one_node_info, credentials, app_names,
      @secret)
    assert_equal(expected_2, result_6)
  end

  def test_set_params_w_good_params
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    djinn = Djinn.new

    credentials = ['table', 'cassandra', 'hostname', 'public_ip', 'ips', '', 
      'keyname', 'appscale']
    one_node_info = ['public_ip:private_ip:some_role:instance_id:cloud1']
    app_names = []

    flexmock(HelperFunctions).should_receive(:local_ip).
      and_return("private_ip")

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

  def test_rabbitmq_master
    # RabbitMQ master nodes should configure and deploy RabbitMQ on their node

    # Set up some dummy data that points to our master role as the
    # rabbitmq_master
    master_role = "public_ip:private_ip:rabbitmq_master:instance_id:cloud1"
    djinn = Djinn.new
    djinn.my_index = 0
    djinn.nodes = [DjinnJobData.new(master_role, "appscale")]

    # make sure we write the secret to the cookie file
    # throw in Proc as the last arg to the mock since we don't care about what
    # the block actually contains
    helperfunctions = flexmock(HelperFunctions)
    helperfunctions.should_receive(:get_secret).and_return(@secret)

    file = flexmock(File)
    file.should_receive(:open).with(RabbitMQ::COOKIE_FILE, "w+", Proc).and_return()

    assert_equal(true, djinn.start_rabbitmq_master())
  end

  def test_rabbitmq_slave
    # RabbitMQ slave nodes should wait for RabbitMQ to come up on the master
    # node, and then start RabbitMQ on their own node
    master_role = "public_ip1:private_ip1:rabbitmq_master:instance_id:cloud1"
    slave_role = "public_ip2:private_ip2:rabbitmq_slave:instance_id:cloud1"
    djinn = Djinn.new
    djinn.my_index = 1
    djinn.nodes = [DjinnJobData.new(master_role, "appscale"), DjinnJobData.new(slave_role, "appscale")]

    # make sure we write the secret to the cookie file
    # throw in Proc as the last arg to the mock since we don't care about what
    # the block actually contains
    helperfunctions = flexmock(HelperFunctions)
    helperfunctions.should_receive(:get_secret).and_return(@secret)
    helperfunctions.should_receive(:is_port_open?).
      with("private_ip1", RabbitMQ::SERVER_PORT, HelperFunctions::DONT_USE_SSL).
      and_return(true)
    helperfunctions.should_receive(:is_port_open?).
      with("localhost", RabbitMQ::SERVER_PORT, HelperFunctions::DONT_USE_SSL).
      and_return(true)

    file = flexmock(File)
    file.should_receive(:open).with(RabbitMQ::COOKIE_FILE, "w+", Proc).and_return()

    assert_equal(true, djinn.start_rabbitmq_slave())
  end


  def test_write_our_node_info
    role = "public_ip:private_ip:shadow:instance_id:cloud1"
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

    baz.should_receive(:set).with(
      :path => node_path + "/job_data",
      :data => my_node.serialize).and_return(all_ok)

    baz.should_receive(:get).with(
      :path => node_path + "/done_loading").and_return({
        :rc => 0, :stat => flexmock(:exists => true)})

    baz.should_receive(:set).with(
      :path => node_path + "/done_loading",
      :data => JSON.dump(true)).and_return(all_ok)

    flexmock(HelperFunctions).should_receive(:sleep_until_port_is_open).
      and_return()
    flexmock(Zookeeper).should_receive(:new).with("public_ip:2181", ZKInterface::TIMEOUT).
      and_return(baz)
    ZKInterface.init_to_ip("public_ip", "public_ip")
    assert_equal(nil, djinn.write_our_node_info)
  end

  def test_update_local_nodes
    role = "public_ip:private_ip:shadow:instance_id:cloud1"
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
    job_data = "public_ip:private_ip:memcache:instance_id:cloud1"
    path = "#{ZKInterface::APPCONTROLLER_NODE_PATH}/public_ip/job_data"
    baz.should_receive(:get).with(
      :path => path).and_return({:rc => 0, :data => job_data})

    # Mocks for done_loading file, which we will initially set to false,
    # load the new roles, then set to true
    done_loading = "#{ZKInterface::APPCONTROLLER_NODE_PATH}/public_ip/done_loading"
    baz.should_receive(:get).with(:path => done_loading).
      and_return({:rc => 0, :stat => flexmock(:exists => true)})
    baz.should_receive(:set).with(:path => done_loading,
      :data => JSON.dump(false)).and_return(all_ok)
    baz.should_receive(:set).with(:path => done_loading,
      :data => JSON.dump(true)).and_return(all_ok)

    flexmock(HelperFunctions).should_receive(:local_ip).
      and_return("private_ip")

    flexmock(GodInterface).should_receive(:start).and_return()

    flexmock(HelperFunctions).should_receive(:sleep_until_port_is_open).
      and_return()
    flexmock(Zookeeper).should_receive(:new).with("public_ip:2181", ZKInterface::TIMEOUT).
      and_return(baz)
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
    my_role = "public_ip:private_ip:open:instance_id:cloud1"
    new_role = "public_ip:private_ip:shadow:instance_id:cloud1"
    other_role = "public_ip2:private_ip2:shadow:instance_id:cloud1"
    not_done_loading_role = "public_ip3:private_ip3:appengine:instance_id:cloud1"
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
        :data => JSON.dump("#{other_role}:appscale")})

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
    baz.should_receive(:get).with(
      :path => "#{ZKInterface::APPCONTROLLER_NODE_PATH}/public_ip/job_data").
      and_return({:rc => 0, :data => my_node.serialize(),
        :stat => flexmock(:exists => true)})

    baz.should_receive(:set).with(
      :path => "#{ZKInterface::APPCONTROLLER_NODE_PATH}/public_ip/job_data",
      :data => new_node.serialize()).and_return({:rc => 0})

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
    flexmock(Zookeeper).should_receive(:new).with("public_ip:2181", ZKInterface::TIMEOUT).
      and_return(baz)

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
    flexmock(Zookeeper).should_receive(:new).with("public_ip:2181", ZKInterface::TIMEOUT).
      and_return(mocked_zk)

    ZKInterface.init_to_ip("public_ip", "public_ip")
    ZKInterface.lock_and_run {
      boo = 2
    }

    assert_equal(2, boo)
  end

end
