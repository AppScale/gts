#!/usr/bin/ruby -w


# Imports within Ruby's standard libraries
require 'openssl'


module HelperFunctions


  def self.read_file(location, chomp=true)
    file = File.open(location) { |f| f.read }
    if chomp
      return file.chomp
    else
      return file
    end
  end

  
  def self.get_cert(filename)
    return nil unless File.exists?(filename)
    OpenSSL::X509::Certificate.new(File.open(filename) { |f|
      f.read
    })
  end
  

  def self.get_key(filename)
    return nil unless File.exists?(filename)
    OpenSSL::PKey::RSA.new(File.open(filename) { |f|
      f.read
    })
  end
  

  def self.get_secret(filename="/etc/appscale/secret.key")
    return self.read_file(File.expand_path(filename), chomp=true)
  end

  
end
