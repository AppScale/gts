# Rakefile for flexmock        -*- ruby -*-

#---
# Copyright 2003, 2004, 2005, 2006, 2007 by Jim Weirich (jim@weirichhouse.org).
# All rights reserved.

# Permission is granted for use, copying, modification, distribution,
# and distribution of modified versions of this work as long as the
# above copyright notice is included.
#+++
task :noop
require 'rubygems'
require 'rake/gempackagetask'
require 'rake/clean'
require 'rake/rdoctask'
require 'rake/testtask'
require 'rake/contrib/rubyforgepublisher'

CLEAN.include('*.tmp')
CLOBBER.include("html", 'pkg')

PKG_VERSION = '0.8.6'

PKG_FILES = FileList[
  '[A-Z]*',
  'lib/**/*.rb', 
  'test/**/*.rb',
  '*.blurb',
  'install.rb'
]

RDOC_FILES = FileList[
  'README',
  'CHANGES',
  'lib/**/*.rb',
  'doc/**/*.rdoc',
]

task :default => [:test_all]
task :test_all => [:test]
task :test_units => [:test]
task :ta => [:test_all]

# Test Targets -------------------------------------------------------

Rake::TestTask.new do |t|
  t.pattern = 'test/test*.rb'
  t.verbose = false
  t.warning = true
end

Rake::TestTask.new(:test_extended) do |t|
  t.test_files = FileList['test/extended/test_*.rb']
  t.verbose = true
  t.warning = true
end

task :rspec do
  ENV['RUBYLIB'] = "/Users/jim/working/svn/software/flexmock/lib"
  sh 'echo $RUBYLIB'
  sh "spec test/rspec_integration/*_spec.rb" rescue nil
  puts
  puts "*** There should be three failures in the above report. ***"
  puts
end

# RCov Target --------------------------------------------------------

begin
  require 'rcov/rcovtask'
  
  Rcov::RcovTask.new do |t|
    t.libs << "test"
    t.rcov_opts = ['-xRakefile', '-xrakefile', '-xpublish.rf', '-x/Lib*', '--text-report', '--sort', 'coverage']
    t.test_files = FileList['test/test*.rb']
    t.verbose = true
  end
rescue LoadError => ex
end

# RDoc Target --------------------------------------------------------

task :rdoc => ["README"]

$rd = Rake::RDocTask.new("rdoc") do |rdoc|
  rdoc.rdoc_dir = 'html'
  rdoc.template = 'doc/jamis.rb'
  #  rdoc.template = 'html'
  #  rdoc.template = 'kilmer'
  #  rdoc.template = 'css2'
  rdoc.title    = "Flex Mock"
  rdoc.options << '--line-numbers' << '--inline-source' << '--main' << 'README'
  rdoc.rdoc_files.include(RDOC_FILES)
end

file "README" => ["Rakefile"] do
  ruby %{-i.bak -pe 'sub!(/^Version *:: *(\\d+\\.)+\\d+ *$/, "Version :: #{PKG_VERSION}")' README} # "
end

# Package Task -------------------------------------------------------

if ! defined?(Gem)
  puts "Package Target requires RubyGEMs"
else
  spec = Gem::Specification.new do |s|
    
    #### Basic information.

    s.name = 'flexmock'
    s.version = PKG_VERSION
    s.summary = "Simple and Flexible Mock Objects for Testing"
    s.description = %{
      FlexMock is a extremely simple mock object class compatible
      with the Test::Unit framework.  Although the FlexMock's 
      interface is simple, it is very flexible.
    }				# '

    #### Dependencies and requirements.
    
    #s.add_dependency('log4r', '> 1.0.4')
    #s.requirements << ""
    
    #### Which files are to be included in this gem?  Everything!  (Except CVS directories.)

    s.files = PKG_FILES.to_a

    #### C code extensions.

    #s.extensions << "ext/rmagic/extconf.rb"

    #### Load-time details: library and application (you will need one or both).

    s.require_path = 'lib'                         # Use these for libraries.

    #### Documentation and testing.

    s.has_rdoc = true
    s.extra_rdoc_files = $rd.rdoc_files.reject { |fn| fn =~ /\.rb$/ }.to_a
    s.rdoc_options <<
      '--title' <<  'Flex Mock' <<
      '--main' << 'README' <<
      '--line-numbers'

    #### Author and project details.

    s.author = "Jim Weirich"
    s.email = "jim@weirichhouse.org"
    s.homepage = "http://flexmock.rubyforge.org"
  end

  Rake::GemPackageTask.new(spec) do |pkg|
    pkg.need_zip = true
    pkg.need_tar = true
  end
end

desc "Display a list of all the rubyfiles in the project."
task :rubyfiles do
  puts FileList['**/*.rb']
end
task :rf => :rubyfiles

require 'rake/contrib/publisher'
require 'rake/contrib/sshpublisher'

publisher = Rake::CompositePublisher.new
publisher.add(Rake::RubyForgePublisher.new('flexmock', 'jimweirich'))
publisher.add(Rake::SshFreshDirPublisher.new(
    'umlcoop',
    'htdocs/software/flexmock',
    'html'))
publisher.add(Rake::SshFilePublisher.new(
    'umlcoop',
    'htdocs/software/flexmock',
    '.',
    'flexmock.blurb'))

desc "Publish the documentation on public websites"
task :publish => [:rdoc] do
  publisher.upload
end

SVNHOME = 'svn://localhost/software/flexmock'

task :specs do
  specs = FileList['test/spec_*.rb']
  ENV['RUBYLIB'] = "lib:test:#{ENV['RUBYLIB']}"
  sh %{spec #{specs}}
end

task :tag do
  sh "svn copy #{SVNHOME}/trunk #{SVNHOME}/tags/rel-#{PKG_VERSION} -m 'Release #{PKG_VERSION}'"
end

RUBY_FILES = FileList['**/*.rb']
RUBY_FILES.exclude(/^pkg/)
task :dbg do
  RUBY_FILES.egrep(/DBG/)
end

# Tagging ------------------------------------------------------------

# module Tags
#   RUBY_FILES = FileList['**/*.rb'].exclude("pkg")
# end

# namespace "tags" do
#   task :emacs => Tags::RUBY_FILES do
#     puts "Making Emacs TAGS file"
#     sh "xctags -e #{Tags::RUBY_FILES}", :verbose => false
#   end
# end

# task :tags => ["tags:emacs"]
