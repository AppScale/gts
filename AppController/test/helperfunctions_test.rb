require 'test_helper'
require File.dirname(__FILE__) + "/../helperfunctions"

require 'tmpdir'
require 'fileutils'

class HelperfunctionsTest < Test::Unit::TestCase
  context "expires_duration" do
    setup do
      @three_day_duration = 259200
      @two_hour_duration = 7200
      @five_minute_duration = 300
      @ten_second_duration = 10
    end

    should "determine the correct duration for three days" do
      assert_equal @three_day_duration, HelperFunctions.expires_duration("3d")
    end

    should "determine the correct duration for two hours" do
      assert_equal @two_hour_duration, HelperFunctions.expires_duration("2h")
    end

    should "determine the correct duration for five minutes" do
      assert_equal @five_minute_duration, HelperFunctions.expires_duration("5m")
    end

    should "determine the correct duration for ten seconds" do
      assert_equal @ten_second_duration, HelperFunctions.expires_duration("10s")
    end

    should "determine the correct duration for three days and five minutes" do
      @total_duration = @three_day_duration + @five_minute_duration 
      assert_equal @total_duration, HelperFunctions.expires_duration("3D 5M")
    end

    should "determine the correct duration for all durations" do
      @total_duration = @three_day_duration + @two_hour_duration + @five_minute_duration + @ten_second_duration
      assert_equal @total_duration, HelperFunctions.expires_duration("3d 2h 5m 10s")
    end

    should "determine the correct duration for three days and five minutes even with other invalid times" do
      @total_duration = @three_day_duration + @five_minute_duration 
      assert_equal @total_duration, HelperFunctions.expires_duration("3d 5m 4G 19r")
    end

    should "return nil for an invalid expires string" do
      assert_nil HelperFunctions.expires_duration("s43")
      assert_nil HelperFunctions.expires_duration("17")
      assert_nil HelperFunctions.expires_duration("LGGm 14Q")
    end
  end

  context "parse_static_data for an application with a static directory" do
    setup do
      @app_name = "STATIC_DIRECTORY_APPLICATION"
      @untar_dir = File.join(File.dirname(__FILE__),"data/static-dir-app")
      @app_path = HelperFunctions.get_app_path(@app_name)

      flexmock(HelperFunctions).should_receive("get_untar_dir").once.with(@app_name).and_return(@untar_dir)

      # Create a temporary directory and pretend its the cache directory
      @temp_cache_path = Dir.mktmpdir
      flexmock(HelperFunctions).should_receive("get_cache_path").with(@app_name).and_return(@temp_cache_path)

      @actual_files = ["stylesheet1.css", "stylesheet2.css"]
      
      @result = HelperFunctions.parse_static_data(@app_name)
    end
    
    should "return a single handler for static data" do
      assert_equal 1, @result.length
    end

    should "set the expiration based on the default expiration" do
      @two_day_duration = HelperFunctions.expires_duration("2d")
      assert_equal @two_day_duration, @result.first["expiration"] 
    end

    should "copy the two stylesheets into the stylesheets folder" do
      folders = Dir.glob(File.join(@temp_cache_path,"*"))
      assert folders.include?(File.join(@temp_cache_path,"stylesheets")), "A stylesheets folder should be created"
      assert_equal 1, folders.size, "Only one folder should be created"

      stylesheet_files = Dir.glob(File.join(@temp_cache_path,"stylesheets","*"))
      @actual_files.each do |f| 
        assert stylesheet_files.include?(File.join(@temp_cache_path,"stylesheets",f)), "Each file should be copied over"
      end
      assert_equal @actual_files.size, stylesheet_files.size
    end

    teardown do
      # Cleanup the temporary directory we created
      # Be careful, just because its Ruby doesn't mean rm -rf wont bite you!
      FileUtils.rm_rf Dir.glob(@temp_cache_path)
    end
  end  

  context "parse_static_data for an application with files" do
    setup do
      @app_name = "STATIC_FILES_APPLICATION"
      @untar_dir = File.join(File.dirname(__FILE__),"data/static-files-app")
      @app_path = HelperFunctions.get_app_path(@app_name)

      flexmock(HelperFunctions).should_receive("get_untar_dir").with(@app_name).and_return(@untar_dir)

      # Create a temporary directory and pretend its the cache directory
      @temp_cache_path = Dir.mktmpdir
      flexmock(HelperFunctions).should_receive("get_cache_path").with(@app_name).and_return(@temp_cache_path)

      @result =  HelperFunctions.parse_static_data(@app_name)

      @valid_static_files = ["file.png","file.jpg"]
      @invalid_static_files = ["invalid.txt"]
    end
    
    should "return two handlers, one for each static file declaration" do
      assert_equal 2, @result.length
    end

    should "override the default expiration when an expiration is specified" do
      @thirty_minute_duration = HelperFunctions.expires_duration("30m")
      assert_equal @thirty_minute_duration, @result[0]["expiration"] 
    end

    should "use the default expiration when one is not set explicitly" do
      @six_hour_duration = HelperFunctions.expires_duration("6h")
      assert_equal @six_hour_duration, @result[1]["expiration"] 
    end

    should "copy the two valid files into the static folder" do
      static_files = Dir.glob(File.join(@temp_cache_path,"static","*"))
      
      assert_equal @valid_static_files.length, static_files.length

      @valid_static_files.each do |f| 
        file_path = File.join(@temp_cache_path,"static",f)
        assert static_files.include?(file_path), "Each valid file should be copied over"
      end
    end

    should "not copy invalid files from the static folder" do
      static_files = Dir.glob(File.join(@temp_cache_path,"static","*"))
      @invalid_static_files.each do |f| 
        file_path = File.join(@temp_cache_path,"static",f)
        assert !static_files.include?(file_path), "Invalid files should not be copied over"
      end
    end

    should "copy the javascript file from the archives folder" do
      @valid_archive_files = ["foobar.js"]

      archive_files = Dir.glob(File.join(@temp_cache_path,"archives","*"))

      assert_equal @valid_archive_files.length, archive_files.length

      @valid_archive_files.each do |f| 
        file_path = File.join(@temp_cache_path,"archives",f)
        assert archive_files.include?(file_path), "Each valid file should be copied over"
      end
    end

    teardown do
      # Cleanup the temporary directory we created
      # Be careful, just because its Ruby doesn't mean rm -rf wont bite you!
      FileUtils.rm_rf Dir.glob(@temp_cache_path)
    end
  end
end
