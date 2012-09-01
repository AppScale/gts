require 'rubygems'
require 'rake'
require 'rake/testtask'
require 'rcov/rcovtask'


namespace :appcontroller do


  TEST_SUITE_FILE = "AppController/test/ts_all.rb"


  desc "Generates AppController code coverage statistics"
  Rcov::RcovTask.new(:coverage) do |t|
    t.test_files = FileList[TEST_SUITE_FILE]
    t.output_dir = "AppController/coverage"
    t.rcov_opts << "-x #{TEST_SUITE_FILE} -x ~/.rvm -x /usr/local/lib/site_ruby/1.8/rubygems/gem_path_searcher.rb"
  end


  desc "Generates AppController rdoc"
  task :doc do
    puts `bash AppController/generate_rdoc.sh`
  end


  desc "Runs AppController unit tests"
  Rake::TestTask.new("test") do |t|
    t.pattern = TEST_SUITE_FILE
    t.verbose = true
    t.warning = false
  end


end


namespace :neptunemanager do


  TEST_SUITE_FILE = "Neptune/test/ts_all.rb"


  desc "Generates NeptuneManager code coverage statistics"
  Rcov::RcovTask.new(:coverage) do |t|
    t.test_files = FileList[TEST_SUITE_FILE]
    t.output_dir = "Neptune/coverage"
    t.rcov_opts << "-x #{TEST_SUITE_FILE} -x ~/.rvm -x /usr/local/lib/site_ruby/1.8/rubygems/gem_path_searcher.rb"
  end


  desc "Generates NeptuneManager rdoc"
  task :doc do
    puts `bash Neptune/generate_rdoc.sh`
  end


  desc "Runs NeptuneManager unit tests"
  Rake::TestTask.new("test") do |t|
    t.pattern = 'Neptune/test/ts_all.rb'
    t.verbose = true
    t.warning = false
  end


end


task :default => ['appcontroller:test', 'neptunemanager:test']
