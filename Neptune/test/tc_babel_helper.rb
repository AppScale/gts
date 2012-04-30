# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..")
require 'neptune_manager'


$:.unshift File.join(File.dirname(__FILE__), "..", "lib", "job_types")
require 'babel_helper'


require 'rubygems'
require 'flexmock/test_unit'


class TestBabelHelper < Test::Unit::TestCase
  def setup
    kernel = flexmock(Kernel)
    kernel.should_receive(:puts).and_return()
    
    neptune_class = flexmock(NeptuneManager)
    neptune_class.should_receive(:log_debug).and_return()
    neptune_class.should_receive(:log_run).and_return()

    @secret = "baz"
    flexmock(HelperFunctions).should_receive(:read_file).
      with("/etc/appscale/secret.key", true).and_return(@secret)

    thread = flexmock(Thread)
    thread.should_receive(:initialize).and_return()
  end

  def test_neptune_babel_soap_exposed_methods_bad_secret
    flexmock(NeptuneManager).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(false)
    }
    neptune = NeptuneManager.new

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
    neptune = NeptuneManager.new
    no_credentials = {}
    result = neptune.get_supported_babel_engines(no_credentials,
      "good secret")
    assert_equal(NeptuneManager::INTERNAL_ENGINES, result)

    # with aws credentials, we can use internal queues or sqs
    neptune = NeptuneManager.new
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
    flexmock(NeptuneManager).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    neptune = NeptuneManager.new

    fileutils = flexmock(FileUtils)
    fileutils.should_receive(:mkdir_p).and_return()

    s3 = flexmock('s3')
    flexmock(RightAws::S3Interface).should_receive(:new).and_return(s3)

    flexmock(DatastoreS3).new_instances { |instance|
      instance.should_receive(:get_output_and_save_to_fs).and_return()
      instance.should_receive(:write_remote_file_from_local_file).and_return()
    }

    job_data = {'@run_local' => true, '@code' => '/boo/baz',
      '@argv' => ['/boo/baz2'], '@storage' => 's3',
      '@output' => '/boo/baz3', '@EC2_ACCESS_KEY' => 'boo',
      '@EC2_SECRET_KEY' => 'baz', '@S3_URL' => 'bloo',
      '@metadata_info' => {'input_storage_time' => 0,
        'time_to_store_inputs' => 0}}
    job_list = [job_data]
    result = neptune.run_or_delegate_tasks(job_list)
    assert_equal([NeptuneManager::RUN_LOCALLY], result)

    job_list2 = [job_data, job_data]
    result2 = neptune.run_or_delegate_tasks(job_list2)
    assert_equal([NeptuneManager::RUN_LOCALLY, NeptuneManager::RUN_LOCALLY], result2)
  end

  def test_convert_remote_file_location_to_local_file
    fileutils = flexmock(FileUtils)
    fileutils.should_receive(:mkdir_p).and_return()

    flexmock(RightAws::S3Interface).new_instances { |instance|
      instance.should_receive(:list_bucket).and_return([{:key => 'boo'}])
      instance.should_receive(:get).and_return("boo")
    }

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

    neptune = NeptuneManager.new
    result = neptune.run_or_delegate_tasks(job_list)
    assert_equal([NeptuneManager::RUN_VIA_EXECUTOR], result)
  end
end
