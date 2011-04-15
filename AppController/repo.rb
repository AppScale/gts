#!/usr/bin/ruby -w

$:.unshift File.join(File.dirname(__FILE__))
require 'uri'
require 'fileutils'

class Repo
  def self.init(ip, secret)
    @@ip = ip
    @@secret = secret
  end

  def self.start(login_ip, uaserver_ip)
    # its just another app engine app - but since numbering starts
    # at zero, this app has to be app neg one

    # TODO: tell the tools to disallow uploading apps called 'therepo'
    # and start_appengine to do the same

    num_servers = 3
    app_number = -1
    nginx_port = 8079
    start_port = 19997
    app = "therepo"
    app_language = "python"
    app_version = "1"

    app_location = "/var/apps/#{app}/app"
    Djinn.log_run("mkdir -p #{app_location}")
    Djinn.log_run("cp -r #{APPSCALE_HOME}/AppServer/demos/therepo/* #{app_location}")
    HelperFunctions.setup_app(app, untar=false)

    repo_main_code = "#{app_location}/repo.py"
    file_w_o_secret = HelperFunctions.read_file(repo_main_code)
    file_w_secret = file_w_o_secret.gsub("PLACE SECRET HERE", @@secret)
    HelperFunctions.write_file(repo_main_code, file_w_secret)

    static_handlers = HelperFunctions.parse_static_data(app)
    proxy_port = HAProxy.app_listen_port(app_number)
    Nginx.write_app_config(app, app_number, @@ip, proxy_port, static_handlers, login_ip)
    HAProxy.write_app_config(app, app_number, num_servers, @@ip)
    Collectd.write_app_config(app)

    [19997, 19998, 19999].each { |port|
      Djinn.log_debug("Starting #{app_language} app #{app} on #{HelperFunctions.local_ip}:#{port}")
      pid = HelperFunctions.run_app(app, port, uaserver_ip, @@ip, app_version, app_language, nginx_port, login_ip)
      pid_file_name = "#{APPSCALE_HOME}/.appscale/#{app}-#{port}.pid"
      HelperFunctions.write_file(pid_file_name, pid)
    }

    Nginx.reload
    Collectd.restart
  end

  def self.stop
    # TODO: this is a bit of a lazy way - should instead read pid files
    # and only kill those pids
    Djinn.log_debug(`pkill -f dev_appserver`)
    Djinn.log_debug(`pkill -f DevAppServerMain`)
  end

  def self.valid_storage_creds(storage, creds)
    if storage == "appdb"
      valid = true
    elsif storage == "s3"
      conn = self.get_s3_conn(creds)
      begin
        all_buckets = conn.list_all_my_buckets
        Djinn.log_debug("this user owns these buckets: [#{all_buckets.join(', ')}]")
        valid = true
      rescue RightAws::AwsError
        valid = false
      end
    end

    Djinn.log_debug("did user provide valid storage creds? #{valid}")
  end

  def self.set_output(path, output, storage="appdb", creds={})
    return self.set(path, output, :output, storage, creds)
  end

  def self.get_output(path, storage="appdb", creds={})
    return self.get(path, :output, storage, creds)
  end

  def self.set_acl(path, new_acl, storage="appdb", creds={})
    return self.set(path, new_acl, :acl, storage, creds)
  end

  def self.get_acl(path, storage="appdb", creds={})
    return self.get(path, :acl, storage, creds)
  end

  def self.does_file_exist?(path, storage="appdb", creds={})
    if storage == "appdb"
      result = `curl http://#{@@ip}:8079/doesexist -X POST -d 'SECRET=#{@@secret}' -d 'KEY=#{path}'`
    elsif storage == "s3"
      conn = self.get_s3_conn(creds)
      bucket, file = self.parse_s3_key(path)

      if self.does_s3_bucket_exist?(conn, bucket)
        Djinn.log_debug("[does file exist] bucket [#{bucket}] exists")
        begin
          Djinn.log_debug("[does file exist] getting acl for bucket [#{bucket}] and file [#{file}] ")
          conn.get_acl(bucket, file)
          result = "true"
        rescue RightAws::AwsError
          result = "false"
        end
      else
        Djinn.log_debug("[does file exist] bucket [#{bucket}] does not exist")
        result = "false"
      end
    else
      msg = "ERROR - unrecognized storage for does_file_exist via repo - you requested #{storage}"
      Djinn.log_debug(msg)
      abort(msg)
    end
 
    Djinn.log_debug("does key=#{path} exist? #{result}")
    return result == "true"
  end

  private

  def self.get(key, type, storage, creds)
    if storage == "appdb"
      result = `curl http://#{@@ip}:8079/get -X POST -d 'SECRET=#{@@secret}' -d 'KEY=#{key}' -d 'TYPE=#{type}'`
      result = URI.unescape(result)
    elsif storage == "s3"
      conn = self.get_s3_conn(creds)
      bucket, file = self.parse_s3_key(key)

      if type == :output
        result = conn.get(bucket, file)[:object]
      elsif type == :acl
        # TODO: implement me!
        result = "private"
      else
        msg = "type not supported for get operation - #{type} was used"
        abort(msg)
      end
    else
      msg = "ERROR - unrecognized storage for get via repo - you requested #{storage}"
      Djinn.log_debug(msg)
      abort(msg)
    end

    Djinn.log_debug("get key=#{key} type=#{type}")
    return result
  end

  def self.set(key, val, type, storage, creds)
    if storage == "appdb"
      val = URI.escape(val, Regexp.new("[^#{URI::PATTERN::UNRESERVED}]"))
      result = `curl http://#{@@ip}:8079/set -X POST -d 'SECRET=#{@@secret}' -d 'KEY=#{key}' -d 'VALUE=#{val}' -d 'TYPE=#{type}'`
      Djinn.log_debug("set key=#{key} type=#{type} returned #{result}")
      result = true if result == "success"
    elsif storage == "s3"
      conn = self.get_s3_conn(creds)
      bucket, file = self.parse_s3_key(key)

      if type == :output
        # TODO: for now we assume the bucket exists
        #if !self.does_s3_bucket_exist?(conn, bucket)
        #  Djinn.log_debug("bucket #{bucket} does not exist - creating it now")
        #  conn.create_bucket(bucket)

          # bucket creation takes a few moments - wait for it to exist
          # before we start putting things in it 
        #  loop {
        #    Djinn.log_debug("waiting for s3 bucket #{bucket} to exist")
        #    sleep(5)
        #    break if self.does_s3_bucket_exist?(conn, bucket)
        #  }
        #end

        Djinn.log_debug("s3 bucket #{bucket} exists, now storing file #{file}")

        # this throws an exception that gets automatically caught and logged
        # looks like "undefined method `pos' for <String...>"
        # the put operation still succeeds
        result = conn.put(bucket, file, val, headers={"Content-Length" => val.length})

        Djinn.log_debug("done putting result to s3!")
      elsif type == :acl
        # TODO: implement me!
        return false
      else
        msg = "type not supported for get operation - #{type} was used"
        abort(msg)
      end
    else
      msg = "ERROR - unrecognized storage for set via repo - you requested #{storage}"
      Djinn.log_debug(msg)
      abort(msg)
    end

    Djinn.log_debug("set operation returned #{result}")
    return result
  end

  def self.get_s3_conn(creds)
    access_key = creds['EC2_ACCESS_KEY']
    secret_key = creds['EC2_SECRET_KEY']

    s3_url = creds['S3_URL']

    obscured_a_key = HelperFunctions.obscure_string(access_key)
    obscured_s_key = HelperFunctions.obscure_string(secret_key)

    Djinn.log_debug("creating S3 connection with access key [#{obscured_a_key}], secret key [#{obscured_s_key}], and S3 url [#{s3_url}]")

    old_s3_url = ENV['S3_URL']
    ENV['S3_URL'] = s3_url
    conn = RightAws::S3Interface.new(access_key, secret_key)
    ENV['S3_URL'] = old_s3_url

    return conn
  end

  def self.parse_s3_key(key)
    paths = key.split("/")
    bucket = paths[1]
    file = paths[2, paths.length - 1].join("/")
    return bucket, file
  end

  def self.does_s3_bucket_exist?(conn, bucket)
    all_buckets = conn.list_all_my_buckets
    bucket_names = all_buckets.map { |b| b[:name] }
    bucket_exists = bucket_names.include?(bucket)
    Djinn.log_debug("the user owns buckets [#{bucket_names.join(', ')}] - do they own [#{bucket}]? #{bucket_exists}")
    return bucket_exists
  end
end

