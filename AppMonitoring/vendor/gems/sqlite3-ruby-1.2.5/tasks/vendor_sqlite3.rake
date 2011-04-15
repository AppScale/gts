require 'rake/clean'
require 'rake/extensioncompiler'

# download sqlite3 library and headers

# only on Windows or cross platform compilation
def dlltool(dllname, deffile, libfile)
  # define if we are using GCC or not
  if Rake::ExtensionCompiler.mingw_gcc_executable then
    dir = File.dirname(Rake::ExtensionCompiler.mingw_gcc_executable)
    tool = case RUBY_PLATFORM
      when /mingw/
        File.join(dir, 'dlltool.exe')
      when /linux|darwin/
        File.join(dir, "#{Rake::ExtensionCompiler.mingw_host}-dlltool")
    end
    return "#{tool} --dllname #{dllname} --def #{deffile} --output-lib #{libfile}"
  else
    if RUBY_PLATFORM =~ /mswin/ then
      tool = 'lib.exe'
    else
      fail "Unsupported platform for cross-compilation (please, contribute some patches)."
    end
    return "#{tool} /DEF:#{deffile} /OUT:#{libfile}"
  end
end

version = '3_6_16'

# required folder structure for --with-sqlite3-dir (include + lib)
directory "vendor/sqlite3/lib"
directory "vendor/sqlite3/include"

# download amalgamation version (for include files)
file "vendor/sqlite-amalgamation-#{version}.zip" => ['vendor'] do |t|
  url = "http://www.sqlite.org/#{File.basename(t.name)}"
  when_writing "downloading #{t.name}" do
    cd File.dirname(t.name) do
      system "wget -c #{url} || curl -C - -O #{url}"
    end
  end
end

# download dll binaries
file "vendor/sqlitedll-#{version}.zip" => ['vendor'] do |t|
  url = "http://www.sqlite.org/#{File.basename(t.name)}"
  when_writing "downloading #{t.name}" do
    cd File.dirname(t.name) do
      system "wget -c #{url} || curl -C - -O #{url}"
    end
  end
end

# extract header files into include folder
file "vendor/sqlite3/include/sqlite3.h" => ['vendor/sqlite3/include', "vendor/sqlite-amalgamation-#{version}.zip"] do |t|
  full_file = File.expand_path(t.prerequisites.last)
  when_writing "creating #{t.name}" do
    cd File.dirname(t.name) do
      sh "unzip #{full_file}"
      # update file timestamp to avoid Rake perform this extraction again.
      touch File.basename(t.name)
    end
  end
end

# extract dll files into lib folder
file "vendor/sqlite3/lib/sqlite3.dll" => ['vendor/sqlite3/lib', "vendor/sqlitedll-#{version}.zip"] do |t|
  full_file = File.expand_path(t.prerequisites.last)
  when_writing "creating #{t.name}" do
    cd File.dirname(t.name) do
      sh "unzip #{full_file}"
      # update file timestamp to avoid Rake perform this extraction again.
      touch File.basename(t.name)
    end
  end
end

# generate import library from definition and dll file
file "vendor/sqlite3/lib/sqlite3.lib" => ["vendor/sqlite3/lib/sqlite3.dll"] do |t|
  libfile = t.name
  dllname = libfile.ext('dll')
  deffile = libfile.ext('def')

  when_writing "creating #{t.name}" do
    sh dlltool(dllname, deffile, libfile)
  end
end

# clean and clobber actions
# All the uncompressed files must be removed at clean
 CLEAN.include('vendor/sqlite3')

# clobber vendored packages
CLOBBER.include('vendor')

# vendor:sqlite3
task 'vendor:sqlite3' => ["vendor/sqlite3/lib/sqlite3.lib", "vendor/sqlite3/include/sqlite3.h"]

# hook into cross compilation vendored sqlite3 dependency
if RUBY_PLATFORM =~ /mingw|mswin/ then
  Rake::Task['compile'].prerequisites.unshift 'vendor:sqlite3'
else
  Rake::Task['cross'].prerequisites.unshift 'vendor:sqlite3'
end
