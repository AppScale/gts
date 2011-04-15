require 'mkmf'

dir_config( "sqlite3" )

have_library( "rt", "fdatasync" )

if have_header( "sqlite3.h" ) && have_library( "sqlite3", "sqlite3_open" ) then
  $CFLAGS << " -fno-strict-aliasing" unless RUBY_PLATFORM =~ /mswin/
  create_makefile( "sqlite3_api" )
end
