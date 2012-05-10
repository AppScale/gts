# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..")
require 'neptune_manager'


require 'rubygems'
require 'flexmock/test_unit'


class TestNeptuneManager < Test::Unit::TestCase
  def setup
    @secret = "baz"
    flexmock(HelperFunctions).should_receive(:read_file).
      with("/etc/appscale/secret.key", true).and_return(@secret)
  end

  def test_start_job
    # mock out starting new threads, since we just want to test the SOAP
    # call
    flexmock(Thread).should_receive(:new).and_return()

    neptune = NeptuneManager.new()
    job_params = {}
    actual = neptune.start_job(job_params, @secret)
    assert_equal(NeptuneManager::JOB_IS_RUNNING, actual)
  end

  def test_dispatch_parallel_jobs
    neptune = NeptuneManager.new()
    one = {
      "@type" => "babel"
    }

    two = {
      "@type" => "babel"
    }

    batch_params = [one, two]
    actual = neptune.dispatch_jobs(batch_params)
    assert_equal(NeptuneManager::RUN_JOBS_IN_PARALLEL, actual)
  end

  def test_dispatch_serial_jobs
    #neptune = NeptuneManager.new()
    #batch_params = {

    #}
    #actual = neptune.start_job(batch_params)
    #assert_equal(NeptuneManager::JOB_IS_RUNNING, actual)
  end

end
