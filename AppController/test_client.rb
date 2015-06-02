require 'openssl'
require 'soap/rpc/driver'
require 'webrick/https'
require 'net/http'
require "rubygems"
require "highline/import"

$:.unshift File.join(File.dirname(__FILE__), "lib")
require 'helperfunctions'

URL = 'https://localhost:17443/'

begin
  secret = HelperFunctions.get_secret()
  driver = SOAP::RPC::Driver.new(URL)
  driver.options["protocol.http.ssl_config.verify_mode"] = nil 
  # Add remote sevice methods
  driver.add_method('status', 'secret')
  driver.add_method('is_done_initializing','secret')
  driver.add_method('is_done_loading','secret')
  driver.add_method('get_role_info','secret')
  loop do
    choose do |menu|
      menu.layout = :menu_only

      menu.shell  = true

      menu.choice(:status,"Status") do | command |
        say("Invoking status")
        puts driver.status(secret)
      end
      menu.choice(:done, "Done") do | command |
        say("Invoking is_done_initializing")
        puts driver.is_done_initializing(secret)
        say("Invoking is_done_loading") 
        puts driver.is_done_loading(secret)
      end
      menu.choice(:role,"Role") do | command |
        say("Invoking get_role_info")
        puts driver.get_role_info(secret)
      end
      


      menu.choice(:quit, "Exit program.") { exit }
    end
  end


end
