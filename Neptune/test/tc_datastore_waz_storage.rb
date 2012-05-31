# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..", "lib")
require 'datastore_factory'
require 'datastore_waz_storage'


require 'rubygems'
require 'flexmock/test_unit'


class TestDatastoreWAZStorage < Test::Unit::TestCase

  
  def setup
    # all writing to stdout should do nothing
    flexmock(Kernel).should_receive(:puts).and_return()

    # set up a mock for shell calls to prevent all non-explicitly mocked
    # out shell calls from executing
    flexmock(HelperFunctions).should_receive(:shell).with("").and_return()

    # same goes for file calls
    flexmock(File).should_receive(:directory?).with("").and_return()
    flexmock(File).should_receive(:new).with("").and_return()
    flexmock(File).should_receive(:open).with("").and_return()
    flexmock(File).should_receive(:write).with("").and_return()

    # similarly for FileUtils
    flexmock(FileUtils).should_receive(:mkdir_p).with("").and_return()

    # a common set of acceptable credentials
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


  def test_get_and_set_with_strings
    # mock out the waz storage connection first
    flexmock(WAZ::Storage::Base).should_receive(:establish_connection!).
      with(:account_name => @creds['@WAZ_Account_Name'], 
        :access_key => @creds['@WAZ_Access_Key']).and_return()

    expected = "baz boo something else"

    waz_container = flexmock("container")

    # mock out writing to waz storage
    waz_container.should_receive(:store).with("keyname", expected, 
      DatastoreWAZStorage::PLAIN_TEXT).and_return()

    # and mock out reading from waz storage
    blob = flexmock("blob")
    blob.should_receive(:value).and_return(expected)
    waz_container.should_receive(:[]).with("keyname").and_return(blob)

    # put in our mocked object
    flexmock(WAZ::Blobs::Container).should_receive(:find).with("bucketname").
      and_return(waz_container)


    datastore = DatastoreFactory.get_datastore(DatastoreWAZStorage::NAME,
      @creds)
    remote_path = "/bucketname/keyname"
    datastore.write_remote_file_from_string(remote_path, expected)

    actual = datastore.get_output_and_return_contents(remote_path)
    assert_equal(expected, actual)
  end

  
  def test_get_and_set_with_files
    # this test sets up a local directory with two files, writes the contents
    # of their files to WAZ storage, reads them back from WAZ storage to a
    # local directory, and then tests to see if the files we got back were
    # the same as the ones we wrote to it

    remote_path = "/container/directory"
    remote1_path = "directory/file1.txt"
    remote2_path = "directory/file2.txt"

    local_dir1 = "/home/baz/filedir1"
    local_dir2 = "/home/baz/filedir2"

    file1_name = "file1.txt"
    file1_contents = "baz boo pikachu1"

    file2_name = "file2.txt"
    file2_contents = "foo bar pikachu2"

    # mock out the waz storage connection first
    flexmock(WAZ::Storage::Base).should_receive(:establish_connection!).
      with(:account_name => @creds['@WAZ_Account_Name'], 
        :access_key => @creds['@WAZ_Access_Key']).and_return()

    # add in mocks for writing files
    waz_container = flexmock("container")
    waz_container.should_receive(:store).
      with(remote1_path, file1_contents, DatastoreWAZStorage::PLAIN_TEXT).
      and_return(true)
    waz_container.should_receive(:store).
      with(remote2_path, file2_contents, DatastoreWAZStorage::PLAIN_TEXT).
      and_return(true)

    # add in mocks for reading files
    blob1 = flexmock("blob1")
    blob2 = flexmock("blob2")

    blob1.should_receive(:name).and_return(remote1_path)
    blob2.should_receive(:name).and_return(remote2_path)

    blob1.should_receive(:value).and_return(file1_contents)
    blob2.should_receive(:value).and_return(file2_contents)

    flexmock(waz_container).should_receive(:blobs).and_return([blob1, blob2])

    flexmock(waz_container).should_receive(:[]).with(remote1_path).
      and_return(blob1)
    flexmock(waz_container).should_receive(:[]).with(remote2_path).
      and_return(blob2)

    flexmock(WAZ::Blobs::Container).should_receive(:find).with("container").
      and_return(waz_container)

    datastore = DatastoreFactory.get_datastore(DatastoreWAZStorage::NAME,
      @creds)

    # mock out reading the local file system for the directory to upload
    flexmock(File).should_receive(:directory?).with(local_dir1).
      and_return(true)
    flexmock(HelperFunctions).should_receive(:shell).with("ls #{local_dir1}").
      and_return("#{file1_name}\n#{file2_name}")

    # and the same for the files to upload
    dir1_file1 = "#{local_dir1}/#{file1_name}"
    flexmock(File).should_receive(:directory?).
      with(dir1_file1).and_return(false)

    dir1_file2 = "#{local_dir1}/#{file2_name}"
    flexmock(File).should_receive(:directory?).
      with(dir1_file2).and_return(false)

    flexmock(File).should_receive(:open).with(dir1_file1, Proc).
      and_return(file1_contents)
    flexmock(File).should_receive(:open).with(dir1_file2, Proc).
      and_return(file2_contents)

    # put in mocks so that we can write files from the mocked WAZ storage
    # back to our local file system
    local_dir3 = "#{local_dir2}/directory"
    flexmock(FileUtils).should_receive(:mkdir_p).with(local_dir3).and_return()

    dir2_file1 = "#{local_dir3}/#{file1_name}"
    dir2_file2 = "#{local_dir3}/#{file2_name}"

    flexmock(File).should_receive(:open).with(dir2_file1, "w+", Proc).
      and_return()
    flexmock(File).should_receive(:open).with(dir2_file2, "w+", Proc).
      and_return()

    flexmock(File).should_receive(:open).with(dir2_file1, Proc).
      and_return(file1_contents)

    flexmock(File).should_receive(:open).with(dir2_file2, Proc).
      and_return(file2_contents)

    # finally, write our files to the mocked out WAZ storage and read
    # them back
    datastore.write_remote_file_from_local_file(remote_path, local_dir1)
    datastore.get_output_and_save_to_fs(remote_path, local_dir2)

    # make sure we got the first file back fine
    written_file1_contents = File.open(dir2_file1) { |f| f.read }
    assert_equal(file1_contents, written_file1_contents)

    # and the same for the second file
    written_file2_contents = File.open(dir2_file2) { |f| f.read }
    assert_equal(file2_contents, written_file2_contents)
  end


end
