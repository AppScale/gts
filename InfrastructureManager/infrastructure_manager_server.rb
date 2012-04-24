#!/usr/bin/ruby -w


# Imports within Ruby's standard libraries
require 'soap/rpc/httpserver'
require 'webrick/https'
require 'logger'
require 'soap/rpc/driver'


# Import for InfrastructureManager
$:.unshift File.join(File.dirname(__FILE__))
require 'infrastructure_manager'


$VERBOSE = nil # to supress excessive SSL cert warnings


# InfrastructureManagerServer is a wrapper around InfrastructureManager that 
# gives it the ability to respond to SOAP requests.
class InfrastructureManagerServer < SOAP::RPC::HTTPServer


  # The InfrastructureManager that this SOAP server wraps around.
  attr_reader :infrastructure_manager


  # When the InfrastructureManagerServer starts, this method will expose only
  # the necessary methods via SOAP to the AppController (and eventually the
  # NeptuneManager).
  def on_init
    @infrastructure_manager = InfrastructureManager.new

    # Expose InfrastructureManager methods to the outside world
    add_method(@djinn, "run_instances", "parameters", "secret")
    add_method(@djinn, "describe_instances", "parameters", "secret")
    add_method(@djinn, "terminate_instances", "parameters", "secret")
  end


end

# AppScale components authenticate via a shared secret, stored in a
# predetermined location. As the AppController is in charge of making sure
# this file exists, wait for it to write that file.
appscale_dir = "/etc/appscale/"

secret = nil
loop {
  secret = HelperFunctions.get_secret(appscale_dir + "secret.key")
  break unless secret.nil?
  Djinn.log_debug("Still waiting for that secret key...")
  sleep(5)
}


# SOAP services running via SSL need a X509 certificate/key pair to operate,
# so wait for the AppController to write them to the local file system.
server_cert = nil
server_key = nil
loop {
  server_cert = HelperFunctions.get_cert(appscale_dir + "certs/mycert.pem")
  server_key = HelperFunctions.get_key(appscale_dir + "certs/mykey.pem")
  break if !server_cert.nil? && !server_key.nil?
  Djinn.log_debug("Waiting on certs")
  sleep(5)
}


# Finally, start the InfrastructureManagerServer now that we have the
# X509 certs.
server = InfrastructureManagerServer.new(
  :BindAddress => "0.0.0.0",
  :Port => InfrastructureManager::SERVER_PORT,
  :AccessLog => [],
  :SSLEnable => true,
  :SSLCertificate => server_cert,
  :SSLPrivateKey => server_key,
  :SSLVerifyClient => nil,
  :SSLCertName => nil
)


trap('INT') {
  server.shutdown()
}


server.start()
