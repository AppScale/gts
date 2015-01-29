require 'rubygems'
require 'rake'
require 'rake/rdoctask'
require 'rake/testtask'


namespace :appcontroller do


  APPCONTROLLER_TEST_SUITE = "AppController/test/ts_all.rb"


  desc "Generates AppController rdoc"
  Rake::RDocTask.new(:doc) { |rd|
    rd.rdoc_files.include("AppController/djinn.rb", 
      "AppController/djinnServer.rb", "AppController/lib")
    rd.rdoc_dir = "AppController/doc"
  }


  desc "Runs AppController unit tests"
  Rake::TestTask.new("test") do |t|
    t.pattern = APPCONTROLLER_TEST_SUITE
    t.verbose = true
    t.warning = false
  end


end


namespace :python do

  task :test do
    sh "bash ts_python.sh"
  end

end

namespace :appmanager do
  
  task :test do
   sh "nosetests AppManager/test/unit"
  end

end

namespace :infrastructuremanager do

  task :test do
    sh "nosetests InfrastructureManager"
  end

end

namespace :appdb do

  task :test do
    sh "nosetests AppDB/test/unit"
  end

end

namespace :apptaskqueue do

  task :test do
    sh "nosetests AppTaskQueue/test/unit"
  end

end

namespace :searchservice do

  task :test do
    sh "nosetests SearchService/test/unit"
  end

end

namespace :appserver do

  task :test do
    sh "nosetests AppServer/google/appengine/api/taskqueue/test " +
      "AppServer/google/appengine/api/xmpp/test"
  end

end


namespace :lib do

  task :test do
    sh "nosetests lib/test/unit"
  end

end

namespace :appdashboard do

  task :test do
    sh "python AppDashboard/test/unit/test_suite.py"
  end

  task :coverage do |test|
    sh "rm -rf AppDashboard/coverage"
    sh "coverage erase"
    sh "coverage run --include='AppDashboard/lib/*,AppDashboard/dashboard.py' --omit='*tests*' AppDashboard/test/test_suite.py"
    sh "coverage report -m"
    sh "coverage html --directory=AppDashboard/coverage"
  end

end

namespace :xmppreceiver do

  task :coverage do
    sh "rm -rf XMPPReceiver/coverage"
    sh "cd XMPPReceiver && coverage -e"
    sh "cd XMPPReceiver && coverage run --include='xmpp_receiver.py' --omit='*tests*' --omit='*Python*' test/test_suite.py"
    sh "cd XMPPReceiver && coverage report -m"
    sh "cd XMPPReceiver && coverage html"
    sh "cd XMPPReceiver && mv htmlcov coverage"
  end

  task :test do
    sh "nosetests XMPPReceiver"
  end

end

task :default => ['appcontroller:test', 'infrastructuremanager:test', 'appmanager:test', 'appdb:test', 'apptaskqueue:test', 'searchservice:test', 'lib:test', 'appserver:test', 'xmppreceiver:test', 'appdashboard:test']
