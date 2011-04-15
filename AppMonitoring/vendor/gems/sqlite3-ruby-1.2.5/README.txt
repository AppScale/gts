= SQLite3/Ruby Interface

* http://sqlite3-ruby.rubyforge.org
* http://rubyforge.org/projects/sqlite3-ruby
* http://github.com/jamis/sqlite3-ruby

== DESCRIPTION

This module allows Ruby programs to interface with the SQLite3
database engine (http://www.sqlite.org).  You must have the
SQLite engine installed in order to build this module.

Note that this module is NOT compatible with SQLite 2.x.

== Compilation and Installation

Simply do the following, after installing SQLite3:

  ruby setup.rb config
  ruby setup.rb setup
  ruby setup.rb install

Alternatively, you can download and install the RubyGem package for
SQLite3/Ruby (you must have RubyGems and SQLite3 installed, first):

  gem install sqlite3-ruby

If you have sqlite3 installed in a non-standard location, you can specify the location of the include and lib files by doing:

  gem install sqlite3-ruby -- --with-sqlite3-include=/opt/local/include \
     --with-sqlite3-lib=/opt/local/lib

Also, the gem ships with the C source-code pre-built, so (as of version 1.1.1)
you no longer need to have SWIG installed. However, if you have SWIG installed
and you want to generate the C file yourself, you can specify the
<code>--with-swig</code> option.

== Usage

For help figuring out the SQLite3/Ruby interface, check out the
FAQ[http://sqlite-ruby.rubyforge.org/sqlite3/faq.html]. It includes examples of
usage. If you have any questions that you feel should be address in the
FAQ, please send them to jamis@37signals.com

== Source Code

The source repository is accessible via git:

  git clone git://github.com/jamis/sqlite3-ruby.git

== Contact Information

The project page is http://rubyforge.org/projects/sqlite-ruby. There, you can
find links to mailing lists and forums that you can use to discuss this
library. Additionally, there are trackers for submitting bugs and feature
requests. Feel free to use them!
