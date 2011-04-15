require File.join(File.dirname(__FILE__), 'helper')

class TC_ResultSet < Test::Unit::TestCase
  def setup
    @db = SQLite3::Database.new( "test.db" )
    @db.transaction do
      @db.execute "create table foo ( a integer primary key, b text )"
      @db.execute "insert into foo ( b ) values ( 'foo' )"
      @db.execute "insert into foo ( b ) values ( 'bar' )"
      @db.execute "insert into foo ( b ) values ( 'baz' )"
    end
    @stmt = @db.prepare( "select * from foo where a in ( ?, ? )" )
    @result = @stmt.execute
  end

  def teardown
    @stmt.close
    @db.close
    File.delete( "test.db" )
  end

  def test_reset_unused
    assert_nothing_raised { @result.reset }
    assert @result.to_a.empty?
  end

  def test_reset_used
    @result.to_a
    assert_nothing_raised { @result.reset }
    assert @result.to_a.empty?
  end

  def test_reset_with_bind
    @result.to_a
    assert_nothing_raised { @result.reset( 1, 2 ) }
    assert_equal 2, @result.to_a.length
  end

  def test_eof_inner
    @result.reset( 1 )
    assert !@result.eof?
  end

  def test_eof_edge
    @result.reset( 1 )
    @result.next # to first row
    @result.next # to end of result set
    assert @result.eof?
  end

  def test_next_eof
    @result.reset( 1 )
    assert_not_nil @result.next
    assert_nil @result.next
  end

  def test_next_no_type_translation_no_hash
    @result.reset( 1 )
    assert_equal [ "1", "foo" ], @result.next
  end

  def test_next_type_translation
    @db.type_translation = true
    @result.reset( 1 )
    assert_equal [ 1, "foo" ], @result.next
  end

  def test_next_type_translation_with_untyped_column
    @db.type_translation = true
    @db.query( "select count(*) from foo" ) do |result|
      assert_equal ["3"], result.next
    end
  end

  def test_type_translation_with_null_column
    @db.type_translation = true
    @db.execute "create table bar ( a integer, b time, c string )"
    @db.execute "insert into bar (a, b, c) values (NULL, '1974-07-25 14:39:00', 'hello')"
    @db.execute "insert into bar (a, b, c) values (1, NULL, 'hello')"
    @db.execute "insert into bar (a, b, c) values (2, '1974-07-25 14:39:00', NULL)"
    @db.query( "select * from bar" ) do |result|
      assert_equal [nil, Time.local(1974, 7, 25, 14, 39, 0), 'hello'], result.next
      assert_equal [1, nil, 'hello'], result.next
      assert_equal [2, Time.local(1974, 7, 25, 14, 39, 0), nil], result.next
    end
  end

  def test_date_and_time_translation
    @db.type_translation = true
    @db.execute "create table bar ( a date, b datetime, c time, d timestamp )"
    @db.execute "insert into bar (a, b, c, d) values ('1999-01-08', '1997-12-17 07:37:16', '07:37:16', '2004-10-19 10:23:54')"
    @db.query( "select * from bar" ) do |result|
      result = result.next
      assert result[0].is_a?(Date)
      assert result[1].is_a?(DateTime)
      assert result[2].is_a?(Time)
      assert result[3].is_a?(Time)
    end
  end

  def test_next_results_as_hash
    @db.results_as_hash = true
    @result.reset( 1 )
    assert_equal( { "a" => "1", "b" => "foo", 0 => "1", 1 => "foo" },
      @result.next )
  end

  def test_tainted_results_as_hash
    @db.results_as_hash = true
    @result.reset( 1 )
    row = @result.next
    row.each do |_, v|
      assert_equal true, v.tainted?
    end
  end

  def test_tainted_row_values
    @result.reset( 1 )
    row = @result.next
    row.each do |v|
      assert_equal true, v.tainted?
    end
  end

  def test_each
    called = 0
    @result.reset( 1, 2 )
    @result.each { |row| called += 1 }
    assert_equal 2, called
  end

  def test_enumerable
    @result.reset( 1, 2 )
    assert_equal 2, @result.to_a.length
  end

  def test_types
    assert_equal [ "integer", "text" ], @result.types
  end

  def test_columns
    assert_equal [ "a", "b" ], @result.columns
  end

  def test_close
    stmt = @db.prepare( "select * from foo" )
    result = stmt.execute
    assert !result.closed?
    result.close
    assert result.closed?
    assert stmt.closed?
    assert_raise( SQLite3::Exception ) { result.reset }
    assert_raise( SQLite3::Exception ) { result.next }
    assert_raise( SQLite3::Exception ) { result.each }
    assert_raise( SQLite3::Exception ) { result.close }
    assert_raise( SQLite3::Exception ) { result.types }
    assert_raise( SQLite3::Exception ) { result.columns }
  end
end
