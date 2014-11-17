# Programmer: Navraj Chohan

$:.unshift File.join(File.dirname(__FILE__), "..")
require 'djinn'

$:.unshift File.join(File.dirname(__FILE__), "../..", "lib")
require 'error_app'
require 'helperfunctions'

require 'rubygems'
require 'flexmock/test_unit'


class TestErrorApp < Test::Unit::TestCase
  def setup
    djinn = flexmock(Djinn)
    djinn.should_receive(:log_run).and_return()
    djinn.should_receive(:log_debug).and_return()

    dir = flexmock(Dir)
    dir.should_receive(:chdir).and_return()

    helper_functions = flexmock(HelperFunctions)
    helper_functions.should_receive(:write_file).and_return() 
  end
 
  def test_creation
    errorapp = flexmock(ErrorApp)
    assert_nothing_raised(Exception) {
      ea_class = ErrorApp.new("testapp", "ERROR")
      ea_class.generate("java")
    }
  end
end
