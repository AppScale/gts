require File.join(File.dirname(__FILE__), 'helper')

class TC_Errors < Test::Unit::TestCase
  (1..26).each do |code|
    define_method( "test_error_code_%02d" % code ) do
      db = stub('database', :errmsg => 'message')
      begin
        SQLite3::Error.check( code, db )
      rescue SQLite3::Exception => e
        assert_instance_of SQLite3::EXCEPTIONS[code], e
        assert_equal code, e.code
        assert_equal code, e.class.code
        assert_equal "message", e.message
      end
    end
  end
end
