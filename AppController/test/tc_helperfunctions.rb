
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
    @appengine_web_xml_stripped = "/appengine-web.xml"
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
