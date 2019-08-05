require 'rubygems'
require 'rake'
require 'rdoc/task'
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

namespace :apps do

  task :test do
    sh 'python -m unittest discover -b -v -s Apps/sensor/tests'
    sh 'python -m unittest discover -b -v -s Apps/sensor/common/tests'
  end

end

namespace :infrastructuremanager do

  task :test do
    sh 'python -m unittest discover -b -v -s InfrastructureManager'
  end

end

namespace :appdb do

  task :test do
    sh 'python -m unittest discover -b -v -s AppDB/test/unit'
  end

end

namespace :apptaskqueue do

  task :test do
    sh '/opt/appscale_venvs/appscale_taskqueue/bin/python -m unittest discover -b -v -s AppTaskQueue/test/unit'
  end

end

namespace :hermes do

  task :test do
    sh '/opt/appscale_venvs/hermes/bin/pip install pytest pytest-asyncio'
    sh '/opt/appscale_venvs/hermes/bin/pytest Hermes/tests'
  end

end

namespace :searchservice do

  task :test do
    sh 'python -m unittest discover -b -v -s SearchService/test/unit'
  end

end

namespace :searchservice2 do

  task :test do
    sh '/opt/appscale_venvs/search2/bin/pip install pytest'
    sh '/opt/appscale_venvs/search2/bin/pytest SearchService2/tests'
  end

end

namespace :appserver do

  task :test do
    sh 'python -m unittest discover -b -v '\
      '-s AppServer/google/appengine/api/taskqueue/test'
    sh 'python -m unittest discover -b -v '\
      '-s AppServer/google/appengine/api/xmpp/test'
  end

end


namespace :common do

  task :test do
    sh 'python -m unittest discover -b -v -s common/test/unit -t common/'
  end

end

namespace :appdashboard do

  task :test do
    sh 'python -m unittest discover -b -v -s AppDashboard/test/unit'
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
    sh 'python -m unittest discover -b -v -s XMPPReceiver/test'
  end

end

namespace :adminserver do

  task :test do
    sh 'python -m unittest discover -b -v -s AdminServer/tests'
  end

end

python_tests = [
  'appdashboard:test',
  'appdb:test',
  'appserver:test',
  'apptaskqueue:test',
  'common:test',
  'hermes:test',
  'infrastructuremanager:test',
  'searchservice:test',
  'searchservice2:test',
  'xmppreceiver:test',
  'apps:test',
  'adminserver:test'
]
ruby_tests = ['appcontroller:test']

task :default => python_tests + ruby_tests
