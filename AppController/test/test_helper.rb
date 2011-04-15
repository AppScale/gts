# Load in all of the gems and plugins from the load balancer so they can be used
Dir.glob(File.dirname(__FILE__)+"/../../AppLoadBalancer/vendor/*/*/lib").each do |path|
  $LOAD_PATH.unshift(File.expand_path(path))
end

require 'shoulda'
require 'flexmock'
require 'flexmock/test_unit'
begin 
  require 'redgreen'
rescue LoadError
  # Redgreen gem could not be found, oh well its not really necessary
end

