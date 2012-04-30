# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..")
require 'neptune_manager'


$:.unshift File.join(File.dirname(__FILE__), "..", "lib", "job_types")
require 'appscale_helper'


require 'rubygems'
require 'flexmock/test_unit'


class TestAppScaleHelper < Test::Unit::TestCase
  def setup
    kernel = flexmock(Kernel)
    kernel.should_receive(:puts).and_return()

    thread = flexmock(Thread)
    thread.should_receive(:initialize).and_return()

    flexmock(HelperFunctions).should_receive(:read_file).
      with("/etc/appscale/secret.key", true).and_return(@secret)
  end

  def test_entry_point_bad_secret
    nodes = nil
    job_data_1 = {}
    secret = "anything"

    flexmock(NeptuneManager).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(false)
    }
    neptune = NeptuneManager.new
    
    result_1 = neptune.appscale_run_job(nodes, job_data_1, secret)
    assert_equal(NeptuneManager::BAD_SECRET_MSG, result_1)
  end

  def test_entry_point_good_secret
    nodes = nil
    job_data_1 = {}
    secret = "anything"

    flexmock(NeptuneManager).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }
    neptune = NeptuneManager.new

    job_data_2 = {"@time_needed_for" => 120}
    result_2 = neptune.appscale_run_job(nodes, job_data_2, secret)
    assert_equal(NeptuneManager::MISSING_PARAM, result_2)

    job_data_3 = {"@add_component" => "db_slave"}
    result_3 = neptune.appscale_run_job(nodes, job_data_3, secret)
    assert_equal(NeptuneManager::MISSING_PARAM, result_3)

    job_data_4 = {"@time_needed_for" => 120, "@add_component" => "db_slave"}
    result_4 = neptune.appscale_run_job(nodes, job_data_4, secret)
    assert_equal(NeptuneManager::STARTED_SUCCESSFULLY, result_4)
  end
end
