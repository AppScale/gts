# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..")
require 'neptune_manager'


$:.unshift File.join(File.dirname(__FILE__), "..", "lib", "job_types")
require 'cicero_helper'


require 'rubygems'
require 'flexmock/test_unit'


class TestCiceroHelper < Test::Unit::TestCase
  def setup
    kernel = flexmock(Kernel)
    kernel.should_receive(:puts).and_return()

    djinn = flexmock(Djinn)
    djinn.should_receive(:log_debug).and_return()

    @secret = "baz"
    flexmock(HelperFunctions).should_receive(:read_file).
      with("/etc/appscale/secret.key", true).and_return(@secret)
  end

  def test_cicero_run_job_param_validation
    flexmock(Djinn).new_instances { |instance|
      instance.should_receive(:valid_secret?).and_return(true)
    }

    djinn = Djinn.new
    secret = "anything"

    nodes = nil
    job_data = {}
    result = djinn.neptune_cicero_run_job(nodes, job_data, secret)
    assert_equal("nodes must be an Array", result)

    nodes = []
    job_data = []
    result = djinn.neptune_cicero_run_job(nodes, job_data, secret)
    assert_equal("job_data must be a Hash", result)

    nodes = []
    job_data = [{}]
    result = djinn.neptune_cicero_run_job(nodes, job_data, secret)
    assert_equal("OK", result)
  end
end
