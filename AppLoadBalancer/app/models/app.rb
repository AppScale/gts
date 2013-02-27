class App
  include Validatable
  require 'timeout'
  require 'fileutils'

  validates_presence_of :file_data
  validates_true_for :file_data, :logic => lambda { valid_tar? }, :message => "Application must be a gzipped tar file with .tar.gz extension"

  attr_accessor :filename
  attr_accessor :file_data

  def initialize(options={})
    if options.kind_of?(Hash)
      options.each do |k,v|
        method = "#{k}="
        self.send(method,v) if self.respond_to?(method)
      end
    end
  end

  def file_path
    File.join(FILE_UPLOAD_PATH,self.filename)
  end

  # Validatable calls id on the object which gives a deprecation warning
  # This is a simple way to get around that
  def id
    self.object_id
  end

  def save!
    Rails.logger.info "about to upload a new app!"
    begin
      if !File.exist?(FILE_UPLOAD_PATH)
        FileUtils.mkdir_p FILE_UPLOAD_PATH
      end
      Rails.logger.info "trying to write file #{file_path}"
      File.open(file_path, "wb") { |f| f.write(self.file_data.read) }
      true
    rescue Errno::ENOENT => e
      Rails.logger.error("Unable to save file #{file_path}, error #{exception.clean_backtrace.join("\n")}")
      false
    end
  end

  def upload_app email
    # Sanitize the email address so there is no funny buisness
    email.gsub!(/[^[:alnum:]\.\-@_]/,'')
    keyname = get_keyname

    result = ""
    begin
      Timeout.timeout(180) do
        command = "#{TOOLS_PATH}/bin/appscale-upload-app --file #{self.file_path} --email #{email} --keyname #{keyname} 2>&1;"
        Rails.logger.info("Uploading application: #{command}")
        result = `#{command}`
        result.chomp!
        Rails.logger.info("upload-app returned #{result}")
      end
    rescue Timeout::Error
      result = "The request has timed out. Large applications should be uploaded using the appscale tools"
      Rails.logger.error result
    end
    success = result.include?("uploaded successfully") #&& !result.include?("[unexpected]")

    { :success => success, :message => result }
  end

  def self.remove_app appname
    # Sanitize the appname so there is no funny business
    appname.gsub!(/[^[:alnum:]\.\-@]/,'')

    db_info_path = "/etc/appscale/database_info.yaml"
    tree = YAML.load_file(db_info_path)
    keyname = tree[:keyname]

    result = ""
    begin 
      Timeout::timeout(30) do
        command = "#{TOOLS_PATH}/bin/appscale-remove-app --appname #{appname} --keyname #{keyname} --confirm 2>&1"
        Rails.logger.error("Removing application: #{command}")
        result = `#{command}`
        result.chomp!
      end
    rescue Timeout::Error
      result = "The request has timed out."
    end
    success = result.include?("successfully removed")
    { :success => success, :message => result }
  end

  private
  def valid_tar?
    return false if file_data.nil?
    return false if !GZIP_MIME_TYPES.include?(file_data.content_type)
    return false if (file_data.original_filename =~ /[.]tar[.]gz$/).nil?
    true
  end

  def get_keyname
    db_info_path = "/etc/appscale/database_info.yaml"
    tree = YAML.load_file(db_info_path)
    tree[:keyname]
  end
end
