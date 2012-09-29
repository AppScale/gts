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
    neptune.start(max_iterations=0)

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
    neptune.start(max_iterations=0)

    one = {
      "@type" => "mpi",
      "@nodes_to_use" => 1
    }

    actual = neptune.dispatch_jobs([one])
    assert_equal(NeptuneManager::RUN_JOBS_IN_PARALLEL, actual)
  end

  def test_batch_start_job
    # mock out any actual job running - we're just testing the interface
    flexmock(NeptuneManager).new_instances { |instance|
      instance.should_receive(:dispatch_jobs).and_return()
    }

    neptune = NeptuneManager.new()

    # first, make sure that we reject calls that use an incorrect secret
    expected1 = NeptuneManager::BAD_SECRET_MSG
    actual1 = neptune.batch_start_job([], "bad secret")
    assert_equal(expected1, actual1)

    # next, test out how we run one job
    job1 = {}
    expected = {
      "success" => true,
      "state" => NeptuneManager::JOB_IS_RUNNING
    }
    actual2 = neptune.batch_start_job([job1], @secret)
    assert_equal(expected, actual2)

    # and then multiple jobs
    actual3 = neptune.batch_start_job([job1, job1], @secret)
    assert_equal(expected, actual3)
  end

  def test_batch_put_input
    # mock out all logging
    flexmock(NeptuneManager).should_receive(:log).and_return()

    # mock out interactions with s3
    fake_s3 = flexmock('s3')
    remote = "/remote/baz.rb"
    fake_s3.should_receive(:put).with("remote", "baz.rb", "anything").
      and_return(true)
    flexmock(RightAws::S3Interface).should_receive(:new).with("access", 
      "secret").and_return(fake_s3)

    # lets say that our local file to test putting in exists
    local = "/local/baz.rb"
    flexmock(File).should_receive(:exists?).with(local).and_return(true)
    flexmock(File).should_receive(:open).with(local).and_return("anything")

    # mock out all occurrences of fileutils, and add back in the ones we need
    # to verify
    flexmock(FileUtils).should_receive(:rm_rf).and_return()

    neptune = NeptuneManager.new()

    # first, make sure that we reject calls that use an incorrect secret
    expected1 = NeptuneManager::BAD_SECRET_MSG
    actual1 = neptune.batch_put_input({}, "bad secret")
    assert_equal(expected1, actual1)

    # now test when we put in a single file
    creds = {
      "@storage" => "s3",
      "@EC2_ACCESS_KEY" => "access",
      "@EC2_SECRET_KEY" => "secret",
      "@S3_URL" => "s3 url"
    }
    file = {
      "local" => local,
      "remote" => "/remote/baz.rb"
    }
    files = [file]
    creds_and_files = {creds => files}
    expected2 = {"success" => true} 
    actual2 = neptune.batch_put_input(creds_and_files, @secret)
    assert_equal(expected2, actual2)
  end

  def test_batch_does_file_exist
    neptune = NeptuneManager.new()

    # first, make sure that we reject calls that use an incorrect secret
    expected1 = NeptuneManager::BAD_SECRET_MSG
    actual1 = neptune.batch_does_file_exist([], "bad secret")
    assert_equal(expected1, actual1)

    # now, let's do a test where all the files exist

    # first, mock out our s3 connection
    access = "access key"
    secret = "secret key"
    s3_url = "s3 url"

    fake_s3 = flexmock('fake_s3')
    fake_s3.should_receive(:list_all_my_buckets).with().
      and_return([{:name => "boo"}])
    fake_s3.should_receive(:get_acl).with("boo", "baz1.rb").and_return(true)
    fake_s3.should_receive(:get_acl).with("boo", "baz2.rb").and_return(true)
    flexmock(RightAws::S3Interface).should_receive(:new).with(access, secret).
      and_return(fake_s3)

    creds = {
      "@storage" => DatastoreS3::NAME,
      "@EC2_ACCESS_KEY" => access,
      "@EC2_SECRET_KEY" => secret,
      "@S3_URL" => s3_url
    }
    file1 = "/boo/baz1.rb"
    file2 = "/boo/baz2.rb"
    files1 = {creds => [file1, file2]}
    expected2 = {
      "files_that_exist" => files1,
      "files_that_dont_exist" => {},
      "success" => true
    }
    actual2 = neptune.batch_does_file_exist(files1, @secret)
    assert_equal(expected2['files_that_exist'][creds].sort, 
      actual2['files_that_exist'][creds].sort)
    assert_equal(expected2['files_that_dont_exist'], 
      actual2['files_that_dont_exist'])
    assert_equal(expected2['success'], actual2['success'])
  end

  
  def test_start_with_roles_not_changing
    # assume that ZK is up
    zookeeper = flexmock("zookeeper")

    # mock out getting this node's job data
    my_ip_job_path = "#{ZKInterface::APPCONTROLLER_NODE_PATH}/#{@public_ip}" +
      "/job_data"
    job_data = "#{@public_ip}:private_ip:shadow:mpi_master:instance_id:cloud1"
    zookeeper.should_receive(:get).with(:path => my_ip_job_path).
      and_return({:rc => 0, :data => job_data})

    # mock out getting all node data
    all_node_data = JSON.dump({
      'last_updated' => 1,
      'ips' => [@public_ip]
    })
    zookeeper.should_receive(:get).with(:path => ZKInterface::IP_LIST).
      and_return({:rc => 0, :data => all_node_data})

    flexmock(Zookeeper).should_receive(:new).with('public_ip1:2181').
      and_return(zookeeper)

    neptune = NeptuneManager.new()
    neptune.start(max_iterations=1)

    expected = true
    actual = neptune.my_node.is_mpi_master?
    assert_equal(expected, actual)

    expected_roles_running = ["shadow", "mpi_master"]
    actual_roles_running = neptune.roles_running
    assert_equal(expected_roles_running, actual_roles_running)
  end


end
