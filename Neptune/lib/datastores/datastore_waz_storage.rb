# Programmer: Chris Bunch


require 'datastore'
require 'datastore_s3'


require 'rubygems'


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


  def get_output_and_save_to_fs(remote_path, local_path)
    container_name, blob_name = DatastoreS3.parse_s3_key(remote_path)
    container = WAZ::Blobs::Container.find(container_name)

    remote_list = []

    # find all blobs that match the remote path
    container.blobs.each { |blob|
      if blob.name =~ /\A#{blob_name}/
        NeptuneManager.log("This blob, #{blob.name}, matches remote path " +
          "#{remote_path} - adding it to the list of files to download.")
        remote_list << blob.name
      else
        NeptuneManager.log("This blob, #{blob.name}, does not match " +
          "remote path #{remote_path} - not adding it to the list of files" +
          " to download.")
        next
      end
    }

    NeptuneManager.log("Files to download are: " + remote_list.join("\n"))
    return get_output_with_file_list(remote_list, local_path, container)
  end


  def get_output_with_file_list(remote_list, local_path, container)
    remote_list.each { |blob_name|
      full_local_path = local_path + File::Separator + blob_name
      NeptuneManager.log("Writing local file #{full_local_path} from " +
        "path #{local_path} and WAZ Storage blob name #{blob_name}")

      # if the user gives us a file to fetch that's several directories
      # deep, we need to make all the directories first
      FileUtils.mkdir_p(File.dirname(full_local_path))

      begin
        contents = container[blob_name].value
        HelperFunctions.write_file(full_local_path, contents) 
      rescue Exception => e
        NeptuneManager.log("Saw an Exception of class #{e.class} while " +
          "trying to to download file #{blob_name} from WAZ Blob Storage")
        raise e
      end
    }
  end

  
  # Given an S3-style storage path ("/container/blob"), fetches the named
  # Blob from Azure Blob Storage and returns its contents as a String.
  def get_output_and_return_contents(remote_path)
    container_name, blob_name = DatastoreS3.parse_s3_key(remote_path)
    container = WAZ::Blobs::Container.find(container_name)
    return container[blob_name].value 
  end

  
  def write_remote_file_from_local_file(remote_path, local_path)
    container_name, blob_name = DatastoreS3.parse_s3_key(remote_path)
    container = WAZ::Blobs::Container.find(container_name)
    write_remote_file_with_container(remote_path, local_path, container)
  end

  
  def write_remote_file_with_container(remote_path, local_path, container)
    container_name, blob_name = DatastoreS3.parse_s3_key(remote_path)

    if File.directory?(local_path)
      files_to_upload = HelperFunctions.shell("ls #{local_path}")
      files_to_upload.split.each { |file|
        full_remote_path = remote_path + "/" + file
        full_local_path = local_path + "/" + file
        NeptuneManager.log("Recursive dive - now saving remote " +
          "[#{full_remote_path}], local [#{full_local_path}]")
        success = write_remote_file_with_container(full_remote_path, 
          full_local_path, container)

        if !success
          return false
        end
      }
    else
      NeptuneManager.log("Attempting to put local file #{local_path} into " +
        "container #{container_name}, blob name #{blob_name}")
      contents = File.open(local_path) { |file| file.read }
      return container.store(blob_name, contents, PLAIN_TEXT)
    end

    return true
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
