# add lib folder to the path
$:.unshift File.expand_path(File.join(File.dirname(__FILE__), '..', 'lib'))

require 'sqlite3'

require 'rubygems'
require 'test/unit'

# define mocks to be used
require 'mocha'

class Driver < Mocha::Mock
  def initialize
    super
    stubs( :open ).returns([0, 'cookie'])
    stubs( :close ).returns(0)
    stubs( :complete? ).returns(0)
    stubs( :errmsg ).returns('')
    stubs( :errcode ).returns(0)
    stubs( :trace ).returns(nil)
    stubs( :set_authorizer ).returns(0)
    stubs( :prepare ).returns([0, 'stmt', 'remainder'])
    stubs( :finalize ).returns(0)
    stubs( :changes ).returns(14)
    stubs( :total_changes ).returns(28)
    stubs( :interrupt ).returns(0)
  end
end

class MockResultSet < Mocha::Mock
  def initialize
    super
    stubs( :each ).yields(['foo'])
    stubs( :columns ).returns(['name'])
  end
end

class Statement < Mocha::Mock
  attr_reader :handle
  attr_reader :sql
  attr_reader :last_result

  def initialize( handle, sql )
    super()
    @handle = handle
    @sql = sql
    stubs( :close ).returns(0)
    stubs( :remainder ).returns('')
    stubs( :execute ).returns(MockResultSet.new)
  end
end

# UTF conversion extensions
class String
  def to_utf16(terminate=false)
    self.split(//).map { |c| c[0] }.pack("v*") +
      (terminate ? "\0\0" : "")
  end

  def from_utf16
    result = ""
    length.times do |i|
      result << self[i,1] if i % 2 == 0 && self[i] != 0
    end
    result
  end
end
