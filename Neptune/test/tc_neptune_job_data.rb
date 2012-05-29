# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..", "..", "Neptune")
require 'neptune_job_data'


require 'base64'


require 'rubygems'
require 'flexmock/test_unit'


class TestNeptuneJobData < Test::Unit::TestCase


  def setup
    flexmock(Kernel).should_receive(:puts).and_return()
  end


  def test_cost_calculation
    now = Time.now
    name = "boo"
    num_nodes = 1
    start_time = Base64.encode64(now._dump)
    end_time = Base64.encode64((now + ONE_HOUR)._dump)
    instance_type = "m1.large"
    json_data = {
      "name" => name,
      "num_nodes" => num_nodes,
      "start_time" => start_time,
      "end_time" => end_time,
      "instance_type" => instance_type,
      "total_time" => ONE_HOUR,
      "cost" => COST[instance_type]
    }

    job_data = nil
    assert_nothing_raised(SystemExit) {
      job_data = NeptuneJobData.from_hash(json_data)
    }

    assert_equal(json_data, job_data.to_hash)
    assert_equal(json_data.inspect, job_data.to_s)
  end
end
