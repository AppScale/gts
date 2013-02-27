require 'test_helper'

class AppsHelperTest < ActionView::TestCase
  context "Get ports from application data" do 
    should "return the number of ports with a valid string" do
      app_data = "num_ports:5"
      assert_equal get_num_ports(app_data), 5
    end

    should "return the integer zero when the numbers of ports is zero" do 
      app_data = "num_ports:0"
      assert_equal get_num_ports(app_data), 0
    end

    should "return nil if the number of ports is not a number" do
      app_data = "num_ports:coskdfasdl"
      assert_equal get_num_ports(app_data), nil
    end

    should "return nil if the number of ports is not specified" do
      app_data = "num_ports:"
      assert_equal get_num_ports(app_data), nil
    end
  end

  context "Parse application data" do
    should "return the host and port information" do
      app_data = "num_hosts:3\nhosts:timmy:bobby:jimmy\nnum_ports:3\nports: 14:54:10000"

      result = parse_app_data(app_data)
      assert_equal result.length, 3
      assert_same_elements result, ["timmy:14", "bobby:54", "jimmy:10000"]
    end    
  end

  context "get application path for bad application name" do
    should "return an error message if the application name is nil" do
      result = get_application_path(nil, "/")
      assert_equal result[:exists], false
      assert_equal result[:message], "Application not found."
    end

    should "return an error message if the application name is empty" do
      result = get_application_path("", "")
      assert_equal result[:exists], false
      assert_equal result[:message], "Application not found."
    end
  end
  context "get application path" do
    setup do 
      @app_name = "super cool application"

      @conn = flexmock("conn")
      @secret = flexmock("secret")
      flexmock(DBFrontend).should_receive("get_instance").once.and_return(@conn)
      flexmock(UserTools).should_receive("get_secret_key").once.and_return(@secret)
    end
    should "return an error message if the database is down" do
      @conn.should_receive("get_app_data").once.with(@app_name, @secret).and_raise(Errno::ECONNREFUSED)

      result = get_application_path(@app_name, "/")

      assert_equal result[:exists], false
      assert_equal result[:message], "The database appears to be down right now. Please see your cloud administrator."
    end

    should "return an error message if the application is not found" do
      @conn.should_receive("get_app_data").once.with(@app_name, @secret).and_return("Error: App not found")

      result = get_application_path(@app_name, "/")

      assert_equal result[:exists], false
      assert_equal result[:message], "We were not able to find any data for your application. If you just uploaded your application, please wait a moment and try again."
    end

    should "return an error message if the application doesnt have any ports" do
      @app_data = "fun application data stuff"
      @conn.should_receive("get_app_data").once.with(@app_name, @secret).and_return(@app_data)
      flexmock(self).should_receive("get_num_ports").once.with(@app_data).and_return(nil)

      result = get_application_path(@app_name, "/")

      assert_equal result[:exists], false
      assert_equal result[:message], "Your application is not running right now. If you just uploaded your application, please wait a moment and try again. Otherwise, please see your cloud administrator."
    end

    should "return the correct destination" do
      @app_data = "fun application data stuff"
      @conn.should_receive("get_app_data").once.with(@app_name, @secret).and_return(@app_data)
      flexmock(self).should_receive("get_num_ports").once.with(@app_data).and_return(5)
      servers = ["jimmy:231", "bobby:41234", "timmy:7"]
      flexmock(self).should_receive("parse_app_data").once.with(@app_data).and_return(servers)
      choice = servers.first
      flexmock(self).should_receive("find_rand_live_host").once.with(servers).and_return(choice)

      url_suffix = "foobar"
      choice_url = "http://#{choice}/#{url_suffix}"

      result = get_application_path(@app_name, url_suffix)

      assert_equal result[:exists], true
      assert_equal choice_url, result[:path]
    end
  end
end
