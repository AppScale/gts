# Programmer: Navraj Chohan

$:.unshift File.join(File.dirname(__FILE__), "..", "lib")
require 'error_app'


require 'rubygems'
require 'flexmock/test_unit'


class TestErrorApp < Test::Unit::TestCase
  def setup
    file = flexmock(File)
    file.should_receive(:open).and_return()
    dir = flexmock(Dir)
    dir.should_receive(:chdir).and_return()
  end
 
  def test_creation
    errorapp = flexmock(ErrorApp)
    errorapp.new_instances { |i|
      i.should_receive(:run_shell).and_return(0)
    }

    ea_class = ErrorApp.new("testapp", "ERROR")
    ea_class.generate()
  end
end
