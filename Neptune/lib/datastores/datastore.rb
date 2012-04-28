# Programmer: Chris Bunch


# Datastore provides a single interface that Neptune jobs can use to store
# and retrieve data. Since ACLs can also be modified, the underlying datastore
# must have this capability as well.
class Datastore

  
  # Creates a new Datastore from the given credentials (a Hash).
  def initialize(credentials)
    raise NotImplementedError.new("Datastore initialize is abstract")
  end


  # Queries the remote datastore for the given file and writes its
  # contents to the local filesystem.
  def get_output_and_save_to_fs(remote_path, local_path)
    raise NotImplementedError.new("Get output to FS is abstract")
  end 


  # Queries the remote datastore for the given file and returns its
  # contents as a string
  def get_output_and_return_contents(remote_path)
    raise NotImplementedError.new("Get output to string is abstract")
  end 


  # Writes the contents of a file on the local filesystem to the
  # remote datastore.
  def write_remote_file_from_local_file(remote_path, local_path)
    raise NotImplementedError.new("Write output to file is abstract")
  end


  # Writes the contents of a string to the remote datastore.
  def write_remote_file_from_string(remote_path, string)
    raise NotImplementedError.new("Write output to string is abstract")
  end


  # Returns the access policy for the named file, in the appropriate datastore.
  def get_acl(path)
    raise NotImplementedError.new("Get acl is abstract")
  end


  # Sets the access policy for the named file, in the appropriate datastore.
  def set_acl(path, acl)
    raise NotImplementedError.new("Set acl is abstract")
  end


  # Checks whether the given file exists in the specified datastore.
  def does_file_exist?(path)
    raise NotImplementedError.new("Does file exist is abstract")
  end


end
