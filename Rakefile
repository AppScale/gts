require 'rake'
require 'rake/testtask'


namespace :appcontroller do


  desc "Generates AppController code coverage statistics"
  task :coverage do
    puts `bash AppController/generate_coverage.sh`
  end
  

  desc "Generates AppController rdoc"
  task :doc do
    puts `bash AppController/generate_rdoc.sh`
  end


  desc "Runs AppController unit tests"
  Rake::TestTask.new("test") { |t|
    t.pattern = 'AppController/test/ts_all.rb'
    t.verbose = true
    t.warning = false
  }


end


namespace :neptunemanager do


  desc "Generates NeptuneManager code coverage statistics"
  task :coverage do
    puts `bash Neptune/generate_coverage.sh`
  end
  

  desc "Generates NeptuneManager rdoc"
  task :doc do
    puts `bash Neptune/generate_rdoc.sh`
  end


  desc "Runs NeptuneManager unit tests"
  Rake::TestTask.new("test") { |t|
    t.pattern = 'Neptune/test/ts_all.rb'
    t.verbose = true
    t.warning = false
  }


end


task :default => ['appcontroller:test', 'neptunemanager:test']
