# Programmer: Chris Bunch


require 'datastore'
require 'repo'


# A class that abstracts away access to our Repository application (also known
# as the Repo). Since it's a web application, it can be hosted anywhere, and thus
# this class dictates what we expect the application to return. Implementers of
# this class need only tell us where we can expect to find the Repo application
# and how to make sure it's running there.
class DatastoreRepo

  
  # The host (IP:port) that the Repo app is hosted at.
  attr_accessor :host


  # The name of this datastore, which DatastoreFactory will use to find this
  # Datastore. Implementers should use a unique name amongst Datastore
  # implementers.
  NAME = ""

  
  # Creates a new connection to the Repo running on AppScale. Since AppScale
  # starts the Repo automatically, this initialization does not start it
  # or verify that it is running (although it perhaps should do the latter).
  def initialize(credentials)
    raise NotImplementedError.new("Can't init an abstract Repo")
  end


  # Writes the contents of the remotely specified file to the local filesystem.
  def get_output_and_save_to_fs(repo_path, local_path)
    data = get_output_and_return_contents(repo_path)
    HelperFunctions.write_file(local_path, data)
  end


  # Returns the output of the given file as a string.
  def get_output_and_return_contents(repo_path)
    Djinn.log_debug("Attempting to get output for file [#{repo_path}]")
    return do_http_get_for_get(repo_path, :output)
  end


  # Writes the contents of the given file to a file hosted in the Repo.
  # If the given file is a directory, we also write all files / directories
  # found in that directory.
  def write_remote_file_from_local_file(repo_path, local_path)
    if File.directory?(local_path)
      files_to_upload = HelperFunctions.shell("ls #{local_path}")
      files_to_upload.split.each { |file|
        full_repo_path = repo_path + "/" + file
        full_local_path = local_path + "/" + file
        Djinn.log_debug("Recursive dive - now saving remote " +
          "[#{full_repo_path}], local [#{full_local_path}]")
        temp = write_remote_file_from_local_file(full_repo_path, full_local_path)
        if !temp
          Djinn.log_debug("Setting remote [#{full_repo_path}] failed - reported [#{temp}]")
          return false
        end
      }

      return true
    else
      Djinn.log_debug("Attempting to put local file #{local_path} into file #{repo_path}")
      val = HelperFunctions.read_file(local_path, chomp=false)
      return do_http_post_for_set(repo_path, :output, val)
    end
  end


  # Writes the contents of the given string to a file hosted in the Repo.
  def write_remote_file_from_string(repo_path, string)
    Djinn.log_debug("Attempting to put local file into location #{repo_path}")
    return do_http_post_for_set(repo_path, :output, string)
  end


  # Retrieves the access policy for the given file.
  def get_acl(repo_path)
    Djinn.log_debug("Attempting to get acl for file [#{repo_path}]")
    return do_http_get_for_get(repo_path, :acl)
  end


  # Sets the access policy for the given file hosted in the Repo.
  def set_acl(repo_path, acl)
    Djinn.log_debug("Attempting to set acl to [#{acl}] for file #{repo_path}")
    return do_http_post_for_set(repo_path, :acl, acl)
  end


  # Queries the Repo app to see if the given file exists.
  def does_file_exist?(repo_path)
    Djinn.log_debug("Performing a does_file_exist? on file [#{repo_path}]")
    exists_url = "http://#{@host}/doesexist"
    params = {'SECRET' => HelperFunctions.get_secret(), 'KEY' => repo_path}
    result = Net::HTTP.post_form(URI.parse(exists_url), params).body
    if result == "true"
      return true
    else
      return false
    end
  end


  # A convenience method that can be used to perform GET requests on the
  # Repo app, returning whatever it returns.
  def do_http_get_for_get(repo_path, type)
    Djinn.log_debug("Performing a get on key [#{repo_path}], type [#{type}]")
    get_url = "http://#{@host}/get"
    params = {'SECRET' => HelperFunctions.get_secret(), 'KEY' => repo_path, 
      'TYPE' => type}
    data = Net::HTTP.post_form(URI.parse(get_url), params).body
    return Base64.decode64(data)
  end


  # A convenience method that can be used to perform POST requests on the
  # Repo app, returning a boolean corresponding to if the operation succeeded.
  def do_http_post_for_set(repo_path, type, val)
    encoded_val = Base64.encode64(val)
    set_url = "http://#{@host}/set"
    params = {'SECRET' => HelperFunctions.get_secret(), 'KEY' => repo_path,
      'VALUE' => encoded_val, 'TYPE' => type}
    result = Net::HTTP.post_form(URI.parse(set_url), params).body
    Djinn.log_debug("set key=#{repo_path} type=#{type} returned #{result}")
    if result == "success"
      return true
    else
      return false
    end
  end
end
