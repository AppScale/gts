# use rake-compiler for building the extension
require 'rake/extensiontask'

# build sqlite3_api C extension
Rake::ExtensionTask.new('sqlite3_api', HOE.spec) do |ext|
  # reference to the sqlite3 library
  sqlite3_lib = File.expand_path(File.join(File.dirname(__FILE__), '..', 'vendor', 'sqlite3'))

  # define target for extension (supporting fat binaries)
  if RUBY_PLATFORM =~ /mingw/ then
    ruby_ver = RUBY_VERSION.match(/(\d+\.\d+)/)[1]
    ext.lib_dir = "lib/#{ruby_ver}"
  end

  # automatically add build options to avoid need of manual input
  if RUBY_PLATFORM =~ /mswin|mingw/ then
    ext.config_options << "--with-sqlite3-dir=#{sqlite3_lib}"
  else
    ext.cross_compile = true
    ext.cross_platform = ['i386-mswin32', 'i386-mingw32']
    ext.cross_config_options << "--with-sqlite3-dir=#{sqlite3_lib}"
  end
end

# C wrapper depends on swig file to be generated
file 'ext/sqlite3_api/sqlite3_api_wrap.c' => ['ext/sqlite3_api/sqlite3_api.i'] do |t|
  begin
    sh "swig -ruby -o #{t.name} #{t.prerequisites.first}"
  rescue
    fail "could not build wrapper via swig (perhaps swig is not installed?)"
  end
end

# ensure things are compiled prior testing
task :test => [:compile]
