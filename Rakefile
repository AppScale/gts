require 'rake'


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
  task :test do
    puts `ruby AppController/test/ts_all.rb`
  end


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
  task :test do
    puts `ruby Neptune/test/ts_all.rb`
  end


end


task :default => ['appcontroller:test', 'neptunemanager:test']
