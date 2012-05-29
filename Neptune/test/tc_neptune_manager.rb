# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..")
require 'neptune_manager'


require 'rubygems'
require 'flexmock/test_unit'
require 'json'


class TestNeptuneManager < Test::Unit::TestCase
  def setup
    # all writing to stdout shouldn't
    flexmock(Kernel).should_receive(:puts).and_return()

    # all sleep calls should return immediately
    flexmock(Kernel).should_receive(:sleep).and_return()

    # mock out shell calls, to prevent arbitrary calls from being made
    # make the tester put in the mocks for the needed shell calls
    flexmock(HelperFunctions).should_receive(:shell).with("").and_return()

    # mocks for the secret file
    @secret = "baz"
    flexmock(File).should_receive(:open).
      with("/etc/appscale/secret.key", Proc).and_return(@secret)

    # mocks for the ZK locations file - for now, assume it's always
    # there
    @json_data = JSON.dump({'locations' => 'public_ip1'})
    flexmock(File).should_receive(:exists?).
      with(NeptuneManager::ZK_LOCATIONS_FILE).and_return(true)
    flexmock(File).should_receive(:open).
      with(NeptuneManager::ZK_LOCATIONS_FILE, Proc).and_return(@json_data)

    # mocks for getting our public ip
    @public_ip = "my-public-ip"
    flexmock(File).should_receive(:open).
      with(HelperFunctions::PUBLIC_IP_FILE, Proc).and_return(@public_ip)
    flexmock(HelperFunctions).should_receive(:sleep_until_port_is_open).
      with('public_ip1', ZKInterface::SERVER_PORT).and_return()
  end

  def test_start_job
    # mock out starting new threads, since we just want to test the SOAP
    # call
    flexmock(Thread).should_receive(:new).and_return()

    # assume that ZK is up
    zookeeper = flexmock("zookeeper")
    flexmock(Zookeeper).should_receive(:new).with('public_ip1:2181').
      and_return(zookeeper)

    neptune = NeptuneManager.new()
    job_params = {}
    actual = neptune.start_job(job_params, @secret)
    assert_equal(NeptuneManager::JOB_IS_RUNNING, actual)
  end

  def test_dispatch_parallel_jobs
    # mock out zookeeper interactions
    zookeeper = flexmock("zookeeper")

    # mock out getting this node's job data
    my_ip_job_path = "#{ZKInterface::APPCONTROLLER_NODE_PATH}/#{@public_ip}" +
      "/job_data"
    job_data = "#{@public_ip}:private_ip:shadow:instance_id:cloud1"
    zookeeper.should_receive(:get).with(:path => my_ip_job_path).
      and_return({:rc => 0, :data => job_data})

    # mock out getting all node data
    all_node_data = JSON.dump({
      'last_updated' => 1,
      'ips' => [@public_ip]
    })
    zookeeper.should_receive(:get).with(:path => ZKInterface::IP_LIST).
      and_return({:rc => 0, :data => all_node_data})

    # finally, use the mocked zookeeper object
    flexmock(Zookeeper).should_receive(:new).with('public_ip1:2181').
      and_return(zookeeper)

    # mock out appcontroller interactions
    flexmock(AppControllerClient).new_instances { |instance|
      instance.should_receive(:make_call).and_return()
    }

    # and the same for neptunemanager calls
    flexmock(NeptuneManagerClient).new_instances { |instance|
      instance.should_receive(:make_call).and_return()
    }

    # mock out shell calls to make the lock file, and make it generate
    # a non-random number
    flexmock(Kernel).should_receive(:rand).and_return(0)
    flexmock(HelperFunctions).should_receive(:shell).
      with("touch /tmp/babel-0-started").and_return()

    # mock out ssh calls to see if the job is done running. the first time,
    # we'll say that the job isn't done, and the second time, it is
    flexmock(HelperFunctions).should_receive(:shell).with(/^ssh.*/).
      and_return("0\n", "2\n")

    neptune = NeptuneManager.new()
    neptune.start()

    one = {
      "@type" => "babel",
      "@nodes_to_use" => 1
    }

    two = {
      "@type" => "babel",
      "@nodes_to_use" => 1
    }

    batch_params = [one, two]
    actual = neptune.dispatch_jobs(batch_params)
    assert_equal(NeptuneManager::RUN_JOBS_IN_PARALLEL, actual)
  end

  def test_dispatch_mpi_jobs
    # mock out zookeeper interactions
    zookeeper = flexmock("zookeeper")

    # mock out getting this node's job data
    my_ip_job_path = ZKInterface::APPCONTROLLER_NODE_PATH + "/" + @public_ip +
      "/job_data"
    job_data = "#{@public_ip}:private_ip:shadow:instance_id:cloud1"
    zookeeper.should_receive(:get).with(:path => my_ip_job_path).
      and_return({:rc => 0, :data => job_data})

    # mock out getting an open node's job data
    ip2_job_path = ZKInterface::APPCONTROLLER_NODE_PATH + "/ip2/job_data"
    job_data = "ip2:private_ip2:open:instance_id2:cloud1"
    zookeeper.should_receive(:get).with(:path => ip2_job_path).  
      and_return({:rc => 0, :data => job_data})

    # mock out getting all node data
    exists = {:rc => 0, :stat => flexmock(:exists => true)}
    zookeeper.should_receive(:get).
      with(:path => ZKInterface::APPCONTROLLER_PATH).and_return(exists)

    all_node_data = JSON.dump({
      'last_updated' => 1,
      'ips' => [@public_ip, "ip2"]
    })
    zookeeper.should_receive(:get).with(:path => ZKInterface::IP_LIST).
      and_return({:rc => 0, :data => all_node_data})

    # put in mocks to get and release the zookeeper lock
    all_ok = {:rc => 0}
    zookeeper.should_receive(:create).with(
      :path => ZKInterface::APPCONTROLLER_LOCK_PATH,
      :ephemeral => ZKInterface::EPHEMERAL,
      :data => JSON.dump(@public_ip)).and_return(all_ok)
    zookeeper.should_receive(:delete).with(
      :path => ZKInterface::APPCONTROLLER_LOCK_PATH).
      and_return(all_ok)

    # finally, use the mocked zookeeper object
    flexmock(Zookeeper).should_receive(:new).with('public_ip1:2181').
      and_return(zookeeper)

    # mock out appcontroller interactions
    flexmock(NeptuneManagerClient).new_instances { |instance|
      instance.should_receive(:make_call).and_return()
    }

    # mock out shell calls to make the lock file, and make it generate
    # a non-random number
    flexmock(Kernel).should_receive(:rand).and_return(0)
    flexmock(HelperFunctions).should_receive(:shell).
      with("touch /tmp/mpi-0-started").and_return()

    # mock out ssh calls to see if the job is done running. the first time,
    # we'll say that the job isn't done, and the second time, it is
    flexmock(HelperFunctions).should_receive(:shell).with(/^ssh.*/).
      and_return("0\n", "2\n")

    cloud_info_json = JSON.dump({'is_cloud?' => false, 
      'is_hybrid_cloud?' => false})
    flexmock(File).should_receive(:open).
      with(HelperFunctions::CLOUD_INFO_FILE, Proc).and_return(cloud_info_json)

    neptune = NeptuneManager.new()
    neptune.start()

    one = {
      "@type" => "mpi",
      "@nodes_to_use" => 1
    }

    actual = neptune.dispatch_jobs([one])
    assert_equal(NeptuneManager::RUN_JOBS_IN_PARALLEL, actual)
  end

end
