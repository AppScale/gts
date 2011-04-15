module SQLite3

  module Version

    MAJOR = 1
    MINOR = 2
    TINY  = 5
    BUILD = nil

    STRING = [ MAJOR, MINOR, TINY, BUILD ].compact.join( "." )
    #:beta-tag:

    VERSION = '1.2.5'
  end

end
