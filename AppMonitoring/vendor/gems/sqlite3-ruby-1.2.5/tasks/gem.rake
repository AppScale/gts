require 'rubygems/package_task'
require 'hoe'

HOE = Hoe.spec 'sqlite3-ruby' do
  self.rubyforge_name = 'sqlite-ruby'
  self.author         = ['Jamis Buck']
  self.email          = %w[jamis@37signals.com]
  self.readme_file    = 'README.txt'
  self.need_tar       = false
  self.need_zip       = false

  spec_extras[:required_ruby_version] = Gem::Requirement.new('> 1.8.5')

  spec_extras[:extensions] = ["ext/sqlite3_api/extconf.rb"]

  extra_dev_deps << 'mocha'
  extra_dev_deps << ['rake-compiler', "~> 0.5.0"]

  spec_extras['rdoc_options'] = proc do |rdoc_options|
    rdoc_options << "--main=README.txt"
  end

  clean_globs.push('**/test.db')
end

file "#{HOE.spec.name}.gemspec" => ['Rakefile', 'tasks/gem.rake', 'lib/sqlite3/version.rb'] do |t|
  puts "Generating #{t.name}"
  File.open(t.name, 'w') { |f| f.puts HOE.spec.to_yaml }
end

desc "Generate or update the standalone gemspec file for the project"
task :gemspec => ["#{HOE.spec.name}.gemspec"]
