# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..", "lib")
require 'datastore_factory'
require 'datastore_waz_storage'


require 'rubygems'
require 'flexmock/test_unit'


class TestDatastoreWAZStorage < Test::Unit::TestCase

  
  def setup
    flexmock(Kernel).should_receive(:puts).and_return()

    @creds = {
      '@WAZ_Account_Name' => "booname",
      '@WAZ_Access_Key' => "bazkey"
    }
  end


  def test_credential_validation
    # not providing credentials should result in an exception
    assert_raises(BadConfigurationException) {
      DatastoreFactory.get_datastore(DatastoreWAZStorage::NAME, {})
    }

    # same goes if we forget to include a credential
    assert_raises(BadConfigurationException) {
      DatastoreFactory.get_datastore(DatastoreWAZStorage::NAME,
        {'@WAZ_Account_Name' => "boo"})
    }

    # and finally, if we give all the credentials, they should be stored
    # in our datastore object

    # mock out the waz storage connection first
    flexmock(WAZ::Storage::Base).should_receive(:establish_connection!).
      with(:account_name => @creds['@WAZ_Account_Name'], 
        :access_key => @creds['@WAZ_Access_Key']).and_return()

    datastore = DatastoreFactory.get_datastore(DatastoreWAZStorage::NAME,
      @creds)
    assert_equal(datastore.account_name, @creds['@WAZ_Account_Name'])
    assert_equal(datastore.access_key, @creds['@WAZ_Access_Key'])
  end


end
