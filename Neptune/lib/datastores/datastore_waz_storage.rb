# Programmer: Chris Bunch


require 'datastore'


require 'rubygems'
require 'waz-blobs'


class DatastoreWAZStorage < Datastore

  
  attr_accessor :account_name


  attr_accessor :access_key


  NAME = "waz-storage"


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


end
