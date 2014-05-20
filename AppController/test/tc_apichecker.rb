
$:.unshift File.join(File.dirname(__FILE__), "..", "lib")
require 'apichecker'
require 'app_manager_client'
require 'haproxy'
require 'helperfunctions'
require 'nginx'

require 'flexmock/test_unit'
require 'rubygems'


class TestAPIChecker < Test::Unit::TestCase
  def test_start_app_failure
    flexmock(AppManagerClient).new_instances { |instance|
      instance.should_receive(:start_app).and_return(-1)
    }

    djinn = flexmock(Djinn)
    haproxy = flexmock(HAProxy)
    helper_functions = flexmock(HelperFunctions)
    nginx = flexmock(Nginx)
 
    djinn.should_receive(:log_debug).and_return()
    djinn.should_receive(:log_info).and_return()
    djinn.should_receive(:log_error).and_return()
    djinn.should_receive(:log_run).and_return()

    helper_functions.should_receive(:parse_static_data).and_return([])
    helper_functions.should_receive(:setup_app).and_return()
    helper_functions.should_receive(:read_file).and_return("fake contents")
    helper_functions.should_receive(:write_file).and_return()
    helper_functions.should_receive(:local_ip).and_return('123.123.123.123')

    nginx.should_receive(:write_app_config).and_return()
    nginx.should_receive(:reload).and_return()

    haproxy.should_receive(:app_list_port).and_return(20000)
    haproxy.should_receive(:write_app_config).and_return()

    apichecker = ApiChecker.init('123.123.123.123', '123.123.123.123', 'secret')

    assert_equal(false, ApiChecker.start("123.123.123.123", "123.123.123.123"))
  end


  def test_start_app_success
    flexmock(AppManagerClient).new_instances { |instance|
      instance.should_receive(:start_app).and_return(1)
    }

    djinn = flexmock(Djinn)
    haproxy = flexmock(HAProxy)
    helper_functions = flexmock(HelperFunctions)
    nginx = flexmock(Nginx)
 
    djinn.should_receive(:log_debug).and_return()
    djinn.should_receive(:log_info).and_return()
    djinn.should_receive(:log_error).and_return()
    djinn.should_receive(:log_run).and_return()

    helper_functions.should_receive(:parse_static_data).and_return([])
    helper_functions.should_receive(:setup_app).and_return()
    helper_functions.should_receive(:read_file).and_return("fake contents")
    helper_functions.should_receive(:write_file).and_return()
    helper_functions.should_receive(:local_ip).and_return('123.123.123.123')

    nginx.should_receive(:write_app_config).and_return()
    nginx.should_receive(:reload).and_return()

    haproxy.should_receive(:app_list_port).and_return(20000)
    haproxy.should_receive(:write_app_config).and_return()

    apichecker = ApiChecker.init('123.123.123.123', '123.123.123.123', 'secret')

    assert_equal(true, ApiChecker.start("123.123.123.123", "123.123.123.123"))
  end
end
