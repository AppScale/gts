# Programmer: Chris Bunch


require 'datastore'


require 'rubygems'
require 'right_aws'


# A class that abstracts away access to Amazon S3, and services that are
# API-compatible with S3. Services store and retrieve files in the usual
class DatastoreS3 < Datastore


  # The EC2 access key that should be used to access S3.
  attr_accessor :EC2_ACCESS_KEY


  # The EC2 secret key that should be used to access S3.
  attr_accessor :EC2_SECRET_KEY


  # S3's location (changable to support services that are S3-compatible,
  # like Google Storage and Eucalyptus Walrus).
  attr_accessor :S3_URL


  # The name of this datastore, exposed so that tests and DatastoreFactory
  # can refer to it without worrying about mispelling it.
  NAME = "s3"

  
  # The maximum number of retries that we allow for when saving files to S3.
  MAX_RETRIES = 5


  # Validates the S3 credentials that we've been given and returns a new
  # S3 interface accordingly.
  def initialize(credentials)
    if credentials.class != Hash
      raise BadConfigurationException.new("Credentials was not a Hash")
    end

    if credentials[:EC2_ACCESS_KEY].nil?
      raise BadConfigurationException.new("No EC2 access key specified")
    end
    @EC2_ACCESS_KEY = credentials[:EC2_ACCESS_KEY]

    if credentials[:EC2_SECRET_KEY].nil?
      raise BadConfigurationException.new("No EC2 secret key specified")
    end
    @EC2_SECRET_KEY = credentials[:EC2_SECRET_KEY]

    if credentials[:S3_URL].nil?
      raise BadConfigurationException.new("No S3 URL specified")
    end
    @S3_URL = credentials[:S3_URL]
    old_s3_url = ENV['S3_URL']
    ENV['S3_URL'] = @S3_URL
    @conn = RightAws::S3Interface.new(@EC2_ACCESS_KEY, @EC2_SECRET_KEY)
    ENV['S3_URL'] = old_s3_url
  end


  # Contacts S3 to retrieve a file, and returns the location on the
  # local filesystem that we wrote it to. If the file is a directory,
  # we recursively save all files contained in that directory.
  def get_output_and_save_to_fs(s3_path, local_path)
    # If fetching a directory, fetch all files via the prefix parameter
    # TODO(cgb): presumably list_bucket only lists the first 1000 and
    # returns a cursor for more, so change this accordingly
    bucket, file = DatastoreS3.parse_s3_key(s3_path)
    NeptuneManager.log("Doing a list bucket on #{bucket}, with prefix #{file}")
    files_to_write = @conn.list_bucket(bucket, {'prefix'=> file})
    NeptuneManager.log("List bucket returned [#{files_to_write.join(', ')}]")

    result = ""
    files_to_write.each { |s3_file_data|
      s3_filename = s3_file_data[:key]
      full_local_path = local_path + File::Separator + s3_filename
      NeptuneManager.log("Writing local file #{full_local_path} from " +
        "path #{local_path} and S3 key name #{s3_filename}")

      # if the user gives us a file to fetch that's several directories
      # deep, we need to make all the directories first
      FileUtils.mkdir_p(File.dirname(full_local_path))

      if full_local_path[-1].chr == "/"
        NeptuneManager.log("Local file #{full_local_path} is a directory - " +
          "not downloading it remotely")
        next
      end

      if File.exists?(full_local_path)
        NeptuneManager.log("Local file #{full_local_path} already exists - " +
          "not downloading it again.")
        next
      end

      begin
        f = File.new(full_local_path, File::CREAT|File::RDWR)
        result = @conn.get(bucket, s3_filename) { |chunk|
          f.write(chunk)
        }
        f.close
      rescue Errno::ECONNRESET
        NeptuneManager.log("Saw a connection reset when trying to write " +
          "local file from S3, retrying in a moment.")
        Kernel.sleep(5)
        retry
      end
    }

    return result
  end


  def get_single_file_and_save_to_fs(s3_path, local_path)
    bucket, file = DatastoreS3.parse_s3_key(s3_path)
    NeptuneManager.log("Doing a list bucket on #{bucket}, with prefix #{file}")
    NeptuneManager.log("Writing local file #{local_path} from " +
      "S3 keyname #{file} and bucket #{bucket}")

    # if the user gives us a path to write to that's several directories
    # deep, we need to make all the directories first
    FileUtils.mkdir_p(File.dirname(local_path))

    begin
      f = File.new(local_path, File::CREAT|File::RDWR)
      @conn.get(bucket, file) { |chunk|
        f.write(chunk)
      }
      f.close
    rescue Errno::ECONNRESET
      NeptuneManager.log("Saw a connection reset when trying to write " +
        "local file from S3, retrying in a moment.")
      Kernel.sleep(5)
      retry
    end
    NeptuneManager.log("Done writing file #{local_path}")

    return true
  end


  # Contacts S3 to retrieve a file, returning the contents of the file
  # as a string.
  def get_output_and_return_contents(path)
    bucket, file = DatastoreS3.parse_s3_key(path)
    return @conn.get(bucket, file)[:object]
  end


  # Writes a file in S3 from either a locally-specified file or from a
  # string given to us. If the file is a directory, this function also
  # recursively dives into that directory to write all files and directories
  # contained.
  def write_remote_file_from_local_file(s3_path, local_path)
    bucket, file = DatastoreS3.parse_s3_key(s3_path)

    if File.directory?(local_path)
      files_to_upload = HelperFunctions.shell("ls #{local_path}")
      files_to_upload.split.each { |file|
        full_s3_path = s3_path + "/" + file
        full_local_path = local_path + "/" + file
        NeptuneManager.log("Recursive dive - now saving remote [#{full_s3_path}], local [#{full_local_path}]")
        success = write_remote_file_from_local_file(full_s3_path, full_local_path)

        if !success
          return false
        end
      }
    else
      NeptuneManager.log("Attempting to put local file #{local_path} into " +
        "bucket #{bucket}, location #{file}")
      tries = 0
      begin
        result = @conn.put(bucket, file, File.open(local_path))
        return result
      rescue Exception => e
        NeptuneManager.log("Saw an Exception of class #{e.class} when trying " +
          "to save local file.")
        if tries < MAX_RETRIES
          tries += 1
          Kernel.sleep(1)
          retry
        else
          return false
        end
      end
    end

    return true
  end


  # Writes a string to a file in S3.
  def write_remote_file_from_string(s3_path, string)
    bucket, file = DatastoreS3.parse_s3_key(s3_path)
    return @conn.put(bucket, file, string, 
      headers={"Content-Length" => string.length})
  end


  # Returns the access policy for the specified file.
  # TODO(cgb): Need to implement this and start using it.
  def get_acl(path)
    raise NotImplementedError.new("Need to implement S3 get_acl")
  end


  # Sets the access policy for the specified file.
  # TODO(cgb): Need to implement this and start using it.
  def set_acl(path, acl)
    raise NotImplementedError.new("Need to implement S3 set_acl")
  end

  
  # Checks whether the given file exists in S3.
  def does_file_exist?(path)
    bucket, file = DatastoreS3.parse_s3_key(path)

    if !s3_bucket_exists?(bucket)
      return false
    end

    begin
      NeptuneManager.log("[does file exist] getting acl for bucket [#{bucket}] and file [#{file}] ")
      @conn.get_acl(bucket, file)
      return true
    rescue RightAws::AwsError
      NeptuneManager.log("[does file exist] saw a RightAws::AwsError on path [#{path}]")
      return false
    end
  end


  # Checks whether the given files exist in S3.
  def batch_does_file_exist?(paths)
    results = {}
    paths.each { |path|
      results[path] = does_file_exist?(path)
    }
    return results
  end


  # Queries Amazon S3 with the given connection to see if the user owns the
  # named bucket.
  def s3_bucket_exists?(bucket)
    all_buckets = @conn.list_all_my_buckets()
    bucket_names = all_buckets.map { |b| b[:name] }
    bucket_exists = bucket_names.include?(bucket)
    NeptuneManager.log("the user owns buckets [#{bucket_names.join(', ')}] - do they own [#{bucket}]? #{bucket_exists}")
    return bucket_exists
  end


  # Given a full S3 path, returns the bucket and filename.
  def self.parse_s3_key(key)
    paths = key.split("/")
    bucket = paths[1]
    file = paths[2, paths.length - 1].join("/")
    return bucket, file
  end


end
