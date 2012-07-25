# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..")
require 'babel_helper'


require 'rubygems'
require 'flexmock/test_unit'


class TestGoogleAppEnginePushQueue < Test::Unit::TestCase

  
  def setup
    # any writing to stdout should not get there
    flexmock(Kernel).should_receive(:puts).and_return()
    flexmock(STDOUT).should_receive(:flush).and_return()

    # mock out reading the secret file and return a predetermined secret
    @secret = "secret"
    flexmock(File).should_receive(:open).
      with("/etc/appscale/secret.key", Proc).and_return(@secret)

    # mock out zookeeper files
    @my_public_ip = "my-public-ip"
    json_zk_info = JSON.dump({'locations' => @my_public_ip})
    flexmock(File).should_receive(:exists?).
      with(NeptuneManager::ZK_LOCATIONS_FILE).and_return(true)
    flexmock(File).should_receive(:open).
      with(HelperFunctions::PUBLIC_IP_FILE, Proc).and_return(@my_public_ip)
    flexmock(File).should_receive(:open).
      with(NeptuneManager::ZK_LOCATIONS_FILE, Proc).and_return(json_zk_info)

    # make sure that any shell calls that we haven't mocked out fail
    flexmock(HelperFunctions).should_receive(:shell).with("").and_return()

    # and the same for calls to anything else on the filesystem
    flexmock(FileUtils).should_receive(:rm_f).with("").and_return()
  end


  def test_appengine_job_without_app_upload
    # mock out zookeeper
    zookeeper = flexmock("zookeeper")
    flexmock(HelperFunctions).should_receive(:is_port_open?).
      with(@my_public_ip, ZKInterface::SERVER_PORT, 
        HelperFunctions::DONT_USE_SSL).and_return(true)
    flexmock(Zookeeper).should_receive(:new).
      with("#{@my_public_ip}:#{ZKInterface::SERVER_PORT}").
      and_return(zookeeper)

    # mock out S3
    remote_code = "/neptune-testbin/babel/nbody.py"
    remote_dir = File.dirname(remote_code)
    output_path = "/neptune-testbin/babel/temp-o0z5A7Yim2"
    local_path = /\A\/tmp\/babel-/
    flexmock(DatastoreS3).new_instances { |instance|
      instance.should_receive(:get_output_and_save_to_fs).
        with(remote_dir, local_path).and_return()

      instance.should_receive(:write_remote_file_from_local_file).
        with(output_path, local_path).and_return()

      instance.should_receive(:write_remote_file_from_local_file).
        with(String, "/tmp/baz").and_return()

      instance.should_receive(:write_remote_file_from_local_file).
        with(String, /\/tmp\/metadata-/).and_return()
    }

    # mock out Google App Engine - let's pretend that our app is already
    # uploaded there and responds to /id the right way so that we don't
    # try to upload the app again
    appid = "bazappid"
    host = "http://#{appid}.appspot.com"
    flexmock(GoogleAppEnginePushQueue).should_receive(:get).
      with("#{host}/id").and_return("nbody.main")

    # and add in mocks for each of the URL routes that the Cicero interface
    # will call
    flexmock(JSONClient).should_receive(:put).with("#{host}/task", Hash).
      and_return({"response" => "success"})

    flexmock(JSONClient).should_receive(:get).with("#{host}/task", Hash).
      and_return({"state" => "finished"})

    output = "yay the result of my task!"
    flexmock(JSONClient).should_receive(:get).with("#{host}/data", Hash).
      and_return({"output" => output})

    # finally, writing the output of the job is fine
    flexmock(File).should_receive(:open).with(/\A\/tmp\/babel-/, "w+", Proc).
      and_return()

    # and reading it back should get the output of our task
    flexmock(File).should_receive(:open).with(/\A\/tmp\/babel-/).
      and_return(output)

    # app engine jobs write an empty stderr file to the local filesystem
    # mock out that interaction
    flexmock(File).should_receive(:open).with("/tmp/baz", "w+", Proc).
      and_return()

    # also mock out writing the job's metadata
    flexmock(File).should_receive(:open).with(/\/tmp\/metadata-/, 
      "w+", Proc).and_return()

    # cleaning up the local code off the filesystem is fine
    flexmock(FileUtils).should_receive(:rm_f).with(local_path).and_return()

    # and the same for the metadata we wrote
    flexmock(FileUtils).should_receive(:rm_f).with(/\/tmp\/metadata-/).
      and_return()

    neptune = NeptuneManager.new()
    neptune.start()

    job = {
      "@S3_URL" => "https://s3.amazonaws.com/",
      "@EC2_ACCESS_KEY" => "bazkey",
      "@engine" => "appengine-push-q",
      "@appcfg_cookies" => "/neptune-testbin/.appcfg_cookies",
      "@output" => output_path,
      "@EC2_SECRET_KEY" => "bazsecret",
      "@metadata_info" => {"time_to_store_inputs" => 1.327694},
      "@appid" => appid,
      "@error" => "/neptune-testbin/babel/temp-2tMlvx3XLX",
      "@storage" => "s3",
      "@function" => "main",
      "@is_remote" => false,
      "@run_local" => false,
      "@bucket_name" => "neptune-testbin",
      "@metadata" => "/neptune-testbin/babel/temp-x5LMt2a09h",
      "@executable" => "python",
      "@code" => remote_code 
    }

    expected = [NeptuneManager::RUN_VIA_REMOTE_ENGINE]
    actual = neptune.run_or_delegate_tasks([job])
    assert_equal(expected, actual)
  end


end
