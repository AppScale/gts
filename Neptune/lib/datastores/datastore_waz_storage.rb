# Programmer: Chris Bunch


require 'datastore'
require 'datastore_s3'


require 'rubygems'
require 'waz-blobs'


class DatastoreWAZStorage < Datastore

  
  attr_accessor :account_name


  attr_accessor :access_key


  NAME = "waz-storage"


  PLAIN_TEXT = "text/plain"


  def initialize(credentials)
    if credentials[:WAZ_Account_Name].nil?
      raise BadConfigurationException.new("No WAZ account name specified")
    end
    @account_name = credentials[:WAZ_Account_Name]

    if credentials[:WAZ_Access_Key].nil?
      raise BadConfigurationException.new("No WAZ access key specified")
    end
    @access_key = credentials[:WAZ_Access_Key]

    WAZ::Storage::Base.establish_connection!(:account_name => @account_name,
      :access_key => @access_key)
  end

  
  # Given an S3-style storage path ("/container/blob"), fetches the named
  # Blob from Azure Blob Storage and returns its contents as a String.
  def get_output_and_return_contents(remote_path)
    container_name, blob_name = DatastoreS3.parse_s3_key(remote_path)
    container = WAZ::Blobs::Container.find(container_name)
    return container[blob_name].value 
  end


  # Writes a string to a Blob in Windows Azure Blob Storage.
  # TODO(cgb): This assumes the string is plaintext - fix it to also
  # handle cases where the string is binary.
  def write_remote_file_from_string(remote_path, string)
    container_name, blob_name = DatastoreS3.parse_s3_key(remote_path)
    container = WAZ::Blobs::Container.find(container_name)
    return container.store(blob_name, string, PLAIN_TEXT)
  end


end
