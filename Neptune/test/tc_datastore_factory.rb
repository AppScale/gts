# Programmer: Chris Bunch

$:.unshift File.join(File.dirname(__FILE__), "..", "lib")
require 'datastore_factory'


require 'rubygems'
require 'flexmock/test_unit'


class TestDatastore < Test::Unit::TestCase

  
  def setup
    @secret = "baz"
    @helperfunctions = flexmock(HelperFunctions)
    @helperfunctions.should_receive(:sleep_until_port_is_open).and_return()
    @helperfunctions.should_receive(:read_file).
      with("/etc/appscale/secret.key", true).and_return(@secret)

    @neptune = flexmock(NeptuneManager)
    @neptune.should_receive(:log).and_return()

    @datastore_appscale = DatastoreFactory.get_datastore(
      DatastoreRepoOnAppScale::NAME, {})

    @s3_creds = {'@EC2_ACCESS_KEY' => "baz", '@EC2_SECRET_KEY' => "boo", 
      '@S3_URL' => "bar"}
  end


  def test_repo_is_abstract
    assert_raises(NotImplementedError) { DatastoreRepo.new({}) }
  end


  def test_repo_get_output
    @helperfunctions.should_receive(:write_file).with("/baz.txt", "output").and_return()

    http = flexmock(Net::HTTP)
    http.should_receive(:post_form).and_return(flexmock(:body => "base64data"))

    base64 = flexmock(Base64)
    base64.should_receive(:decode64).with("base64data").and_return("output")

    expected = nil
    actual = @datastore_appscale.get_output_and_save_to_fs("/repo/baz.txt", "/baz.txt")
    assert_equal(expected, actual)
  end


  def test_repo_on_appscale
    expected = "127.0.0.1:#{DatastoreRepoOnAppScale::SERVER_PORT}"
    actual = @datastore_appscale.host
    assert_equal(expected, actual)
  end


  def test_repo_appscale_get_acl
    http = flexmock(Net::HTTP)
    http.should_receive(:post_form).and_return(flexmock(:body => "base64data"))

    base64 = flexmock(Base64)
    base64.should_receive(:decode64).with("base64data").and_return("private")

    expected = "private"
    actual = @datastore_appscale.get_acl("/baz")
    assert_equal(expected, actual)
  end


  def test_repo_appscale_set_acl_success
    http = flexmock(Net::HTTP)
    http.should_receive(:post_form).and_return(flexmock(:body => "success"))

    expected = true
    actual = @datastore_appscale.set_acl("/baz", "private")
    assert_equal(expected, actual)
  end


  def test_repo_appscale_set_acl_failure
    http = flexmock(Net::HTTP)
    http.should_receive(:post_form).and_return(flexmock(:body => "failure"))

    expected = false
    actual = @datastore_appscale.set_acl("/baz", "private")
    assert_equal(expected, actual)
  end


  def test_repo_appscale_file_exists
    http = flexmock(Net::HTTP)
    http.should_receive(:post_form).and_return(flexmock(:body => "true"))

    expected = true
    actual = @datastore_appscale.does_file_exist?("/baz")
    assert_equal(expected, actual)
  end


  def test_repo_appscale_file_does_not_exist
    http = flexmock(Net::HTTP)
    http.should_receive(:post_form).and_return(flexmock(:body => "false"))

    expected = false
    actual = @datastore_appscale.does_file_exist?("/baz")
    assert_equal(expected, actual)
  end


  def test_repo_appscale_upload_dir_w_one_file
    # So we will choose to upload /baz, which is a directory with one
    # file in it: /baz/boo.txt

    file = flexmock(File)
    file.should_receive(:directory?).with("/baz").and_return(true)
    file.should_receive(:directory?).with("/baz/boo.txt").and_return(false)
    
    @helperfunctions.should_receive(:shell).with("ls /baz").and_return("boo.txt\n")
    @helperfunctions.should_receive(:read_file).with("/baz/boo.txt", false).and_return("")

    http = flexmock(Net::HTTP)
    http.should_receive(:post_form).and_return(flexmock(:body => "success"))

    expected = true
    actual = @datastore_appscale.write_remote_file_from_local_file("/repo/baz", "/baz")
    assert_equal(expected, actual)
  end


  def test_repo_appscale_upload_dir_w_two_files
    # So this is similar to the last test, but here, uploading one file will
    # fail, which should cause the entire operation to fail

    file = flexmock(File)
    file.should_receive(:directory?).with("/baz").and_return(true)
    file.should_receive(:directory?).with("/baz/boo.txt").and_return(false)
    file.should_receive(:directory?).with("/baz/boo2.txt").and_return(false)
    
    @helperfunctions.should_receive(:shell).with("ls /baz").and_return("boo.txt\nboo2.txt\n")
    @helperfunctions.should_receive(:read_file).with("/baz/boo.txt", false).and_return("")
    @helperfunctions.should_receive(:read_file).with("/baz/boo2.txt", false).and_return("")

    flexmock(DatastoreRepoOnAppScale).new_instances { |instance|
      instance.should_receive(:do_http_post_for_set).with("/repo/baz/boo.txt", :output, "").and_return(true)
      instance.should_receive(:do_http_post_for_set).with("/repo/baz/boo2.txt", :output, "").and_return(false)
    }

    d = DatastoreFactory.get_datastore(DatastoreRepoOnAppScale::NAME, {}) 

    expected = false
    actual = d.write_remote_file_from_local_file("/repo/baz", "/baz")
    assert_equal(expected, actual)

  end


  def test_repo_appscale_upload_file_from_string
    http = flexmock(Net::HTTP)
    http.should_receive(:post_form).and_return(flexmock(:body => "success"))

    expected = true
    actual = @datastore_appscale.write_remote_file_from_string("/repo/baz", "boo")
    assert_equal(expected, actual)
  end

  
  def test_repo_on_app_engine
    assert_raises(BadConfigurationException) {
      DatastoreFactory.get_datastore(DatastoreRepoOnAppEngine::NAME, "")
    }

    assert_raises(BadConfigurationException) {
      DatastoreFactory.get_datastore(DatastoreRepoOnAppEngine::NAME, {})
    }

    assert_raises(BadConfigurationException) {
      creds = {'@appid' => 'baz'}
      DatastoreFactory.get_datastore(DatastoreRepoOnAppEngine::NAME, creds)
    }
  end


  def test_s3_validation
    assert_raises(BadConfigurationException) {
      DatastoreFactory.get_datastore(DatastoreS3::NAME, "")
    }

    assert_raises(BadConfigurationException) {
      DatastoreS3.new("")
    }

    assert_raises(BadConfigurationException) {
      DatastoreFactory.get_datastore(DatastoreS3::NAME, {})
    }

    assert_raises(BadConfigurationException) {
      creds = {'@EC2_ACCESS_KEY' => "baz"}
      DatastoreFactory.get_datastore(DatastoreS3::NAME, creds)
    }

    assert_raises(BadConfigurationException) {
      creds = {'@EC2_ACCESS_KEY' => "baz", '@EC2_SECRET_KEY' => "boo"}
      DatastoreFactory.get_datastore(DatastoreS3::NAME, creds)
    }

    creds = {'@EC2_ACCESS_KEY' => "baz", '@EC2_SECRET_KEY' => "boo", 
      '@S3_URL' => "bar"}

    s3 = flexmock(RightAws::S3Interface)
    s3.should_receive(:new).with("baz", "boo").and_return()

    d = DatastoreFactory.get_datastore(DatastoreS3::NAME, creds)
    assert_equal("baz", d.EC2_ACCESS_KEY)
    assert_equal("boo", d.EC2_SECRET_KEY)
    assert_equal("bar", d.S3_URL)
  end


  def test_s3_upload_dir_w_one_file
    file = flexmock(File)
    file.should_receive(:directory?).with("/baz").and_return(true)
    file.should_receive(:directory?).with("/baz/boo.txt").and_return(false)
    file.should_receive(:open).with("/baz/boo.txt").and_return("OPEN FILE 1")
    
    @helperfunctions.should_receive(:shell).with("ls /baz").and_return("boo.txt\n")
    @helperfunctions.should_receive(:read_file).with("/baz/boo.txt", false).and_return("")

    flexmock(RightAws::S3Interface).new_instances { |instance|
      instance.should_receive(:put).with("bucket", "baz/boo.txt", "OPEN FILE 1").and_return(true)
    }

    d = DatastoreFactory.get_datastore(DatastoreS3::NAME, @s3_creds)

    expected = true
    actual = d.write_remote_file_from_local_file("/bucket/baz", "/baz")
    assert_equal(expected, actual)
  end


  def test_s3_upload_dir_w_two_files
    # So this is similar to the last test, but here, uploading one file will
    # fail, which should cause the entire operation to fail

    file = flexmock(File)
    file.should_receive(:directory?).with("/baz").and_return(true)
    file.should_receive(:directory?).with("/baz/boo.txt").and_return(false)
    file.should_receive(:directory?).with("/baz/boo2.txt").and_return(false)
    file.should_receive(:open).with("/baz/boo.txt").and_return("OPEN FILE 1")
    file.should_receive(:open).with("/baz/boo2.txt").and_return("OPEN FILE 2")
    
    @helperfunctions.should_receive(:shell).with("ls /baz").and_return("boo.txt\nboo2.txt\n")
    @helperfunctions.should_receive(:read_file).with("/baz/boo.txt", false).and_return("")
    @helperfunctions.should_receive(:read_file).with("/baz/boo2.txt", false).and_return("")

    flexmock(RightAws::S3Interface).new_instances { |instance|
      instance.should_receive(:put).with("bucket", "baz/boo.txt", "OPEN FILE 1").and_return(true)
      instance.should_receive(:put).with("bucket", "baz/boo2.txt", "OPEN FILE 2").and_return(false)
    }

    d = DatastoreFactory.get_datastore(DatastoreS3::NAME, @s3_creds)

    expected = false
    actual = d.write_remote_file_from_local_file("/bucket/baz", "/baz")
    assert_equal(expected, actual)
  end


  def test_s3_file_exists_bucket_not_found
    flexmock(RightAws::S3Interface).new_instances { |instance|
      instance.should_receive(:list_all_my_buckets).and_return([])
    }

    d = DatastoreFactory.get_datastore(DatastoreS3::NAME, @s3_creds)

    expected = false
    actual = d.does_file_exist?("/baz")
    assert_equal(expected, actual)
  end


  def test_s3_file_exists_bucket_found_but_not_file
    flexmock(RightAws::S3Interface).new_instances { |instance|
      instance.should_receive(:list_all_my_buckets).and_return([{:name => "baz"}])
      instance.should_receive(:get_acl).with("baz", "boo.txt").and_raise(RightAws::AwsError)
    }

    d = DatastoreFactory.get_datastore(DatastoreS3::NAME, @s3_creds)

    expected = false
    actual = d.does_file_exist?("/baz/boo.txt")
    assert_equal(expected, actual)
  end


  def test_s3_file_exists_bucket_and_file_found
    flexmock(RightAws::S3Interface).new_instances { |instance|
      instance.should_receive(:list_all_my_buckets).and_return([{:name => "baz"}])
      instance.should_receive(:get_acl).with("baz", "boo.txt").and_return()
    }

    d = DatastoreFactory.get_datastore(DatastoreS3::NAME, @s3_creds)

    expected = true
    actual = d.does_file_exist?("/baz/boo.txt")
    assert_equal(expected, actual)
  end


  def test_bad_datastore
    assert_raises(NotImplementedError) {
      DatastoreFactory.get_datastore("definitely not supported", {})
    }
  end
end
