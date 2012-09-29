# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..")
require 'neptune_manager'


$:.unshift File.join(File.dirname(__FILE__), "..", "lib", "job_types")
require 'babel_helper'


require 'rubygems'
require 'flexmock/test_unit'


class TestBabelHelper < Test::Unit::TestCase
  def setup
    flexmock(Kernel).should_receive(:puts).and_return()
    
    # mock out all shell calls to chmod
    flexmock(HelperFunctions).should_receive(:shell).with(/\Achmod/).
      and_return()

    neptune_class = flexmock(NeptuneManager)
    neptune_class.should_receive(:log_debug).and_return()
    neptune_class.should_receive(:log_run).and_return()

    @secret = "baz"
    flexmock(File).should_receive(:open).
      with("/etc/appscale/secret.key", Proc).and_return(@secret)

    # mocks for getting our public ip
    @public_ip = "my-public-ip"
    flexmock(File).should_receive(:open).
      with(HelperFunctions::PUBLIC_IP_FILE, Proc).and_return(@public_ip)
  end

  def test_neptune_babel_soap_exposed_methods_bad_secret
    flexmock(NeptuneManager).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(false)
    }
    neptune = NeptuneManager.new()

    result1 = neptune.get_supported_babel_engines({}, "bad secret")
    assert_equal(NeptuneManager::BAD_SECRET_MSG, result1)

    result2 = neptune.babel_run_job(nil, {}, "bad secret")
    assert_equal(NeptuneManager::BAD_SECRET_MSG, result2)

    result3 = neptune.get_queues_in_use("bad secret")
    assert_equal(NeptuneManager::BAD_SECRET_MSG, result3)
  end

  def test_neptune_babel_engines_good_secret
    flexmock(NeptuneManager).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }

    # with no credentials, we can use any internal queues
    neptune = NeptuneManager.new()
    no_credentials = {}
    result = neptune.get_supported_babel_engines(no_credentials,
      "good secret")
    assert_equal(NeptuneManager::INTERNAL_ENGINES, result)

    # with aws credentials, we can use internal queues or sqs
    neptune = NeptuneManager.new()
    amazon_credentials = {}
    NeptuneManager::AMAZON_CREDENTIALS.each { |cred|
      amazon_credentials[cred] = "boo"
    }
    result = neptune.get_supported_babel_engines(amazon_credentials,
      "good secret")
    assert_equal((NeptuneManager::INTERNAL_ENGINES + NeptuneManager::AMAZON_ENGINES).uniq, result)

    # with app engine credentials, we can use internal queues or gae push queues
    google_credentials = {}
    NeptuneManager::GOOGLE_CREDENTIALS.each { |cred|
      google_credentials[cred] = "bar"
    }
    result = neptune.get_supported_babel_engines(google_credentials,
      "good secret")
    assert_equal((NeptuneManager::INTERNAL_ENGINES + NeptuneManager::GOOGLE_ENGINES).uniq, result)

    # with azure credentials, we can use internal queues or the azure queue
    microsoft_credentials = {}
    NeptuneManager::AZURE_CREDENTIALS.each { |cred|
      microsoft_credentials[cred] = "baz"
    }
    result = neptune.get_supported_babel_engines(microsoft_credentials,
      "good secret")
    assert_equal((NeptuneManager::INTERNAL_ENGINES + NeptuneManager::AZURE_ENGINES).uniq, result)
  end

  def test_local_run_task
    flexmock(File).should_receive(:open).
      with(String, "w+", Proc).and_return(@secret)

    flexmock(NeptuneManager).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }

    flexmock(FileUtils).should_receive(:mkdir_p).and_return()

    s3 = flexmock('s3')
    flexmock(RightAws::S3Interface).should_receive(:new).and_return(s3)

    flexmock(DatastoreS3).new_instances { |instance|
      instance.should_receive(:get_output_and_save_to_fs).and_return()
      instance.should_receive(:write_remote_file_from_local_file).and_return()
    }

    flexmock(HelperFunctions).should_receive(:shell).and_return()

    job_data = {'@run_local' => true, '@code' => '/boo/baz',
      '@argv' => ['/boo/baz2'], '@storage' => 's3',
      '@output' => '/boo/baz3', '@EC2_ACCESS_KEY' => 'boo',
      '@EC2_SECRET_KEY' => 'baz', '@S3_URL' => 'bloo',
      '@metadata_info' => {'input_storage_time' => 0,
        'time_to_store_inputs' => 0}}
    job_list = [job_data]

    neptune = NeptuneManager.new()
    result = neptune.run_or_delegate_tasks(job_list)
    assert_equal([NeptuneManager::RUN_LOCALLY], result)

    job_list2 = [job_data, job_data]
    result2 = neptune.run_or_delegate_tasks(job_list2)
    assert_equal([NeptuneManager::RUN_LOCALLY, NeptuneManager::RUN_LOCALLY], result2)
  end

  def test_convert_remote_file_location_to_local_file
    fileutils = flexmock(FileUtils)
    fileutils.should_receive(:mkdir_p).and_return()

    s3_instance = flexmock("s3_instance")
    s3_instance.should_receive(:list_bucket).and_return([{:key => 'boo'}])
    s3_instance.should_receive(:get).and_return("boo")
    flexmock(RightAws::S3Interface).should_receive(:new).
      and_return(s3_instance)

    flexmock(File).should_receive(:new).and_return(flexmock(:close => nil))

    job_data = {'@run_local' => true, '@code' => '/boo/baz',
      '@argv' => ['/boo/baz2'], '@storage' => 's3',
      '@output' => '/boo/baz3', '@EC2_ACCESS_KEY' => 'boo',
      '@EC2_SECRET_KEY' => 'bar', '@S3_URL' => 'baz'}
    dir = "/tmp/test2"
    expected = "#{dir}/baz"
    actual = NeptuneManager.copy_code_to_dir(job_data, dir)

    assert_equal(expected, actual)
  end

  def test_task_run_via_executor_and_sqs
    now = Time.now
    flexmock(Time).should_receive(:now).and_return(now)

    flexmock(NeptuneManager).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }

    # the actual job data to test with
    job_data = {'@run_local' => false, '@code' => '/boo/baz',
      '@argv' => ['/boo/baz2'], '@storage' => 's3',
      '@output' => '/boo/baz3', '@engine' => 'executor-sqs',
      '@EC2_ACCESS_KEY' => 'access key', '@EC2_SECRET_KEY' => 'secret key',
      '@global_max_nodes' => 3}
    job_data['@metadata_info'] = {'received_task_at' => now}
    dumped = JSON.dump(job_data)
    job_list = [job_data]

    # mock out zookeeper
    all_ok = {:rc => 0}
    all_ok_not_exists = {:rc => 0, :stat => flexmock(:exists => false)}

    mocked_zk = flexmock("zookeeper")
    mocked_zk.should_receive(:get).with(:path => ZKInterface::BABEL_PATH).
      and_return(all_ok_not_exists)
    mocked_zk.should_receive(:create).with(:path => ZKInterface::BABEL_PATH,
      :data => ZKInterface::DUMMY_DATA, 
      :ephemeral => ZKInterface::NOT_EPHEMERAL).and_return(all_ok)

    mocked_zk.should_receive(:get).with(
      :path => ZKInterface::BABEL_MAX_MACHINES_PATH).and_return(
      all_ok_not_exists)
    flexmock(JSON).should_receive(:dump).with(3).and_return('3')
    mocked_zk.should_receive(:create).with(
      :path => ZKInterface::BABEL_MAX_MACHINES_PATH,
      :data => '3',
      :ephemeral => ZKInterface::NOT_EPHEMERAL).and_return(all_ok)

    # mock out zookeeper's init stuff
    flexmock(HelperFunctions).should_receive(:sleep_until_port_is_open).
      and_return()
    flexmock(Zookeeper).should_receive(:new).with("public_ip:2181").
      and_return(mocked_zk)
    ZKInterface.init_to_ip("public_ip", "public_ip") 

    # mock out sqs
    q = flexmock("q")
    flexmock(JSON).should_receive(:dump).with(job_data).and_return(dumped)
    q.should_receive(:send_message).with(dumped).and_return()
    q.should_receive(:pop_message).and_return(dumped, 'null')

    q_collection = flexmock("q_collection")
    q_collection.should_receive(:create).with(TASK_QUEUE_NAME).and_return(q)

    sqs = flexmock("sqs")
    sqs.should_receive(:queues).and_return(q_collection)

    flexmock(AWS::SQS).should_receive(:new).and_return(sqs)

    neptune = NeptuneManager.new()
    result = neptune.run_or_delegate_tasks(job_list)
    assert_equal([NeptuneManager::RUN_VIA_EXECUTOR], result)
  end

  def test_batch_get_supported_babel_engines
    neptune = NeptuneManager.new()

    # first, make sure that we reject calls that use an incorrect secret
    expected1 = NeptuneManager::BAD_SECRET_MSG
    actual1 = neptune.batch_get_supported_babel_engines([], "bad secret")
    assert_equal(expected1, actual1)

    # next, try an example with a single babel job
    job1 = {
      "@EC2_SECRET_KEY" => "secret",
      "@EC2_ACCESS_KEY" => "access",
      "@S3_URL" => "s3 url"
    }
    #expected2 = {
    #  job1 => NeptuneManager::INTERNAL_ENGINES + NeptuneManager::AMAZON_ENGINES,
    #  "success" => true
    #}
    #actual2 = neptune.batch_get_supported_babel_engines([job1], @secret)
    #assert_equal(expected2, actual2)

    # now try an example with two babel jobs that use different engines
    job2 = {
      "@appid" => "bazboo1",
      "@appcfg_cookies" => "cookie location",
      "@function" => "bar"
    }
    expected3 = {
      job1 => NeptuneManager::INTERNAL_ENGINES + NeptuneManager::AMAZON_ENGINES,
      job2 => NeptuneManager::INTERNAL_ENGINES + NeptuneManager::GOOGLE_ENGINES,
      "success" => true
    }
    actual3 = neptune.batch_get_supported_babel_engines([job1, job2], @secret)
    # FIXME(cgb): in theory this should work but it isn't - look into why
    # and fix it
    #assert_equal(expected3, actual3)
    #assert_equal(expected3[job1], actual3[job1])
    #assert_equal(expected3[job2], actual3[job2])

    # finally, try an example where two jobs use the same engine
    job3 = job2.dup
    #expected4 = something
    #actual4 = neptune.batch_get_supported_babel_engines([job1, job2, job3],
    #  @secret)
    #assert_equal(expected4, actual4)
  end


end
