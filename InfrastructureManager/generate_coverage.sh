rm -rf coverage
# By default, we want to test coverage on the unit tests we have
rcov test/ts_all.rb -x test/ts_all.rb -x /usr/local/lib/site_ruby/1.8/rubygems/gem_path_searcher.rb
