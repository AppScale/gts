# Programmer: Chris Bunch

$:.unshift File.join(File.dirname(__FILE__), "..", "lib")
require 'helperfunctions'


require 'rubygems'
require 'flexmock/test_unit'


class TestHelperFunctions < Test::Unit::TestCase

  def setup
    @prefixed_appid = "gae_boo"
    @appid = "boo"
    @app_yaml = "/var/apps/boo/app/app.yaml"
    @appengine_web_xml = "/var/apps/boo/app/war/WEB-INF/appengine-web.xml"
  end

  def test_obscure_creds
    creds = {
      'ec2_access_key' => 'ABCDEFG',
      'ec2_secret_key' => 'HIJKLMN',
      'CLOUD_EC2_ACCESS_KEY' => 'OPQRSTU',
      'CLOUD_EC2_SECRET_KEY' => 'VWXYZAB'
    }

    expected = {
      'ec2_access_key' => '***DEFG',
      'ec2_secret_key' => '***KLMN',
      'CLOUD_EC2_ACCESS_KEY' => '***RSTU',
      'CLOUD_EC2_SECRET_KEY' => '***YZAB'
    }

    actual = HelperFunctions.obscure_creds(creds)
    assert_equal(expected['ec2_access_key'], actual['ec2_access_key'])
    assert_equal(expected['ec2_secret_key'], actual['ec2_secret_key'])
    assert_equal(expected['CLOUD_EC2_ACCESS_KEY'],
      actual['CLOUD_EC2_ACCESS_KEY'])
    assert_equal(expected['CLOUD_EC2_SECRET_KEY'],
      actual['CLOUD_EC2_SECRET_KEY'])
  end

  def test_get_app_env_vars_for_python_app_with_no_vars
    file = flexmock(File)
    file.should_receive(:exists?).with(@app_yaml).and_return(true)

    yaml = flexmock(YAML)
    yaml.should_receive(:load_file).with(@app_yaml).and_return(YAML.dump({
    }))

    assert_equal({}, HelperFunctions.get_app_env_vars(@appid))
  end

  def test_get_app_env_vars_for_java_app_with_no_vars
    file = flexmock(File)
    file.should_receive(:exists?).with(@app_yaml).and_return(false)
    file.should_receive(:exists?).with(@appengine_web_xml).and_return(true)
    file.should_receive(:open).with(@appengine_web_xml, Proc).and_return("")

    assert_equal({}, HelperFunctions.get_app_env_vars(@appid))
  end

  def test_get_app_env_vars_for_python_app_with_two_vars
    file = flexmock(File)
    file.should_receive(:exists?).with(@app_yaml).and_return(true)

    yaml = flexmock(YAML)
    yaml.should_receive(:load_file).with(@app_yaml).and_return({
      'env_variables' => {
        'VAR_ONE' => 'ONE',
        'VAR_TWO' => 'TWO'
      }
    })

    expected = {
      'VAR_ONE' => 'ONE',
      'VAR_TWO' => 'TWO'
    }
    assert_equal(expected, HelperFunctions.get_app_env_vars(@appid))
  end

  def test_get_app_env_vars_for_java_app_with_two_vars
    file = flexmock(File)
    file.should_receive(:exists?).with(@app_yaml).and_return(false)
    file.should_receive(:exists?).with(@appengine_web_xml).and_return(true)

    xml = <<XML
    <env-variables>
      <env-var name="VAR_ONE" value="ONE" />
      <env-var name="VAR_TWO" value="TWO" />
    </env-variables>
XML
    file.should_receive(:open).with(@appengine_web_xml, Proc).and_return(xml)

    expected = {
      'VAR_ONE' => 'ONE',
      'VAR_TWO' => 'TWO'
    }
    assert_equal(expected, HelperFunctions.get_app_env_vars(@appid))
  end

  def test_get_app_env_vars_for_app_with_no_config
    file = flexmock(File)
    file.should_receive(:exists?).with(@app_yaml).and_return(false)
    file.should_receive(:exists?).with(@appengine_web_xml).and_return(false)
    assert_raises(AppScaleException) {
      HelperFunctions.get_app_env_vars(@appid)
    }
  end

  def test_get_app_thread_safe_python_with_threadsafe_true
    file = flexmock(File)
    file.should_receive(:exists?).with(@app_yaml).and_return(true)
    
    yaml = flexmock(YAML)
    yaml.should_receive(:load_file).with(@app_yaml).and_return({
        'threadsafe' => 'true'
    })
     
    assert_equal(false, HelperFunctions.get_app_thread_safe(@prefixed_appid))
  end

  def test_get_app_thread_safe_python_with_threadsafe_false
    file = flexmock(File)
    file.should_receive(:exists?).with(@app_yaml).and_return(true)
    
    yaml = flexmock(YAML)
    yaml.should_receive(:load_file).with(@app_yaml).and_return({
        'threadsafe' => 'false'
    })
     
    assert_equal(false, HelperFunctions.get_app_thread_safe(@prefixed_appid))
  end

  def test_get_app_thread_safe_java_with_threadsafe_true
    file = flexmock(File)
    file.should_receive(:exists?).with(@app_yaml).and_return(false)
    file.should_receive(:exists?).with(@appengine_web_xml).and_return(true)
    xml = <<XML
    <threadsafe>true</threadsafe>
XML

    file.should_receive(:open).with(@appengine_web_xml, Proc).and_return(xml)
    assert_equal(true, HelperFunctions.get_app_thread_safe(@prefixed_appid))
  end

  def test_get_app_thread_safe_java_with_threadsafe_false
    file = flexmock(File)
    file.should_receive(:exists?).with(@app_yaml).and_return(false)
    file.should_receive(:exists?).with(@appengine_web_xml).and_return(true)
    xml = <<XML
    <threadsafe>false</threadsafe>
XML

    file.should_receive(:open).with(@appengine_web_xml, Proc).and_return(xml)
    assert_equal(false, HelperFunctions.get_app_thread_safe(@prefixed_appid))
  end

  def test_get_app_thread_safe_with_non_prefixed_appid
    file = flexmock(File)
    assert_equal(false, HelperFunctions.get_app_thread_safe(@appid))
  end

  def test_get_app_thread_safe_with_no_config_file
    file = flexmock(File)
    file.should_receive(:exists?).with(@app_yaml).and_return(false)
    file.should_receive(:exists?).with(@appengine_web_xml).and_return(false) 
    assert_equal(false, HelperFunctions.get_app_thread_safe(@prefixed_appid))
  end
 
  def test_app_has_config_file_with_no_config_file
    location = "/boo/baz.tar.gz"
    tar_output = <<BAZ
web/WEB-INF/classes/com/appscale/hawkeye/blobstore/BlobQueryHandlerServlet.class
web/WEB-INF/classes/com/appscale/hawkeye/blobstore/DownloadHandlerServlet.class
web/WEB-INF/classes/com/appscale/hawkeye/blobstore/MainHandlerServlet.class
web/WEB-INF/classes/com/appscale/hawkeye/blobstore/UploadHandlerServlet.class
web/WEB-INF/appengine-generated/datastore-indexes-auto.xml
web/WEB-INF/appengine-generated/local_db.bin
BAZ

    helperfunctions = flexmock(HelperFunctions)
    helperfunctions.should_receive(:shell).with("tar -ztf #{location}") \
      .and_return(tar_output)

    assert_equal(false, HelperFunctions.app_has_config_file?(location))
  end

  def test_app_has_config_file_with_app_yaml
    location = "/boo/baz.tar.gz"
    tar_output = <<BAZ
app.yaml
async_datastore.py
backends.yaml
blobstore.py
BAZ

    helperfunctions = flexmock(HelperFunctions)
    helperfunctions.should_receive(:shell).with("tar -ztf #{location}") \
      .and_return(tar_output)

    assert_equal(true, HelperFunctions.app_has_config_file?(location))
  end

  def test_app_has_config_file_with_appengine_web_xml
    location = "/boo/baz.tar.gz"
    tar_output = <<BAZ
war
web/
web/index.jsp
web/WEB-INF/
web/WEB-INF/appengine-generated/
web/WEB-INF/appengine-web.xml
web/WEB-INF/classes/
web/WEB-INF/cron.xml
web/WEB-INF/lib/
web/WEB-INF/queue.xml
web/WEB-INF/web.xml
BAZ

    helperfunctions = flexmock(HelperFunctions)
    helperfunctions.should_receive(:shell).with("tar -ztf #{location}") \
      .and_return(tar_output)

    assert_equal(true, HelperFunctions.app_has_config_file?(location))
  end
end
