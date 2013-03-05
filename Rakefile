require 'rubygems'
require 'rake'
require 'rake/rdoctask'
require 'rake/testtask'
require 'rcov/rcovtask'


namespace :appcontroller do


  APPCONTROLLER_TEST_SUITE = "AppController/test/ts_all.rb"


  desc "Generates AppController code coverage statistics"
  Rcov::RcovTask.new(:coverage) { |t|
    t.test_files = FileList[APPCONTROLLER_TEST_SUITE]
    t.output_dir = "AppController/coverage"
    t.rcov_opts << "-x #{APPCONTROLLER_TEST_SUITE} -x ~/.rvm -x /usr/local/lib/site_ruby/1.8/rubygems/gem_path_searcher.rb"
  }


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


namespace :neptunemanager do


  NEPTUNE_TEST_SUITE = "Neptune/test/ts_all.rb"


  desc "Generates NeptuneManager code coverage statistics"
  Rcov::RcovTask.new(:coverage) { |t|
    t.test_files = FileList[NEPTUNE_TEST_SUITE]
    t.output_dir = "Neptune/coverage"
    t.rcov_opts << "-x #{NEPTUNE_TEST_SUITE} -x ~/.rvm -x /usr/local/lib/site_ruby/1.8/rubygems/gem_path_searcher.rb"
  }


  desc "Generates NeptuneManager rdoc"
  Rake::RDocTask.new(:doc) { |rd|
    rd.rdoc_files.include("Neptune/neptune_manager.rb", 
      "Neptune/neptune_manager_server.rb", "Neptune/lib")
    rd.rdoc_dir = "Neptune/doc"
  }


  desc "Runs NeptuneManager unit tests"
  Rake::TestTask.new("test") { |t|
    t.pattern = 'Neptune/test/ts_all.rb'
    t.verbose = true
    t.warning = false
  }

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

namespace :lib do

  task :test do
    sh "nosetests lib/test/unit"
  end

end

namespace :xmppreceiver do

  task :test do
    sh "nosetests XMPPReceiver"
  end

end

task :default => ['appcontroller:test', 'neptunemanager:test', 'infrastructuremanager:test', 'appmanager:test', 'appdb:test', 'lib:test', 'xmppreceiver:test']
