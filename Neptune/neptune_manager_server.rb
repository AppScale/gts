#!/usr/bin/ruby -w


# Imports within Ruby's standard libraries
require 'soap/rpc/httpserver'
require 'webrick/https'
require 'logger'
require 'soap/rpc/driver'


# Import for NeptuneManager
$:.unshift File.join(File.dirname(__FILE__))
require 'neptune_manager'

# A list of the Neptune jobs that AppScale will not automatically spawn up
# nodes for. Babel (our distributed task execution system) is in this list
# because it does not use the standard AppScale mechanism to acquire nodes,
# and acquires nodes via specialized scaling techniques.
SINGLE_NODE_COMPUTE_JOBS = %w{babel compile erlang go r}


# A list of the Neptune jobs that AppScale will automatically spawn up more
# nodes for.
MULTI_NODE_COMPUTE_JOBS = %w{cicero mpi mapreduce ssa}


# A list of Neptune jobs that are not considered to be computation jobs, and
# relate to storage or pre-computation in some way.
NONCOMPUTE_JOBS = %w{acl appscale compile input output}


# A list of all the Neptune jobs that we support in AppScale.
NEPTUNE_JOBS = SINGLE_NODE_COMPUTE_JOBS + MULTI_NODE_COMPUTE_JOBS + 
  NONCOMPUTE_JOBS


# NeptuneManagerServer is a wrapper around NeptuneManager that 
# gives it the ability to respond to SOAP requests.
class NeptuneManagerServer < SOAP::RPC::HTTPServer


  # The NeptuneManager that this SOAP server wraps around.
  attr_reader :neptune_manager


  # When the NeptuneManagerServer starts, this method will expose only
  # the necessary methods via SOAP to the AppController (and eventually the
  # NeptuneManager).
  def on_init
    @manager = NeptuneManager.new()

    # Expose NeptuneManager methods to the outside world
    add_method(@manager, "start_job", 'jobs', 'secret')
    add_method(@manager, "is_job_running", "job_data", "secret")
    add_method(@manager, "put_input", "job_data", "secret")
    add_method(@manager, "get_output", "job_data", "secret")
    add_method(@manager, "get_acl", "job_data", "secret")
    add_method(@manager, "set_acl", "job_data", "secret")
    add_method(@manager, "compile_code", "job_data", "secret")
    add_method(@manager, "does_file_exist", "file", "job_data", "secret")
    add_method(@manager, "get_supported_babel_engines", "job_data", "secret")
    add_method(@manager, "get_queues_in_use", "secret")
    
    # Finally, since all Neptune jobs define
    NEPTUNE_JOBS.each { |name|
      add_method(@manager, "#{name}_run_job", "nodes", "jobs", "secret")
    }
  end


end

NeptuneManager.log("Starting NeptuneManager")

# AppScale components authenticate via a shared secret, stored in a
# predetermined location. As the AppController is in charge of making sure
# this file exists, wait for it to write that file.
appscale_dir = "/etc/appscale/"

NeptuneManager.log("Checking for the secret key file")
secret = nil
loop {
  secret = HelperFunctions.get_secret(appscale_dir + "secret.key")
  break unless secret.nil?
  NeptuneManager.log("Still waiting for that secret key...")
  Kernel.sleep(5)
}
NeptuneManager.log("Found a secret set to #{secret}")


# SOAP services running via SSL need a X509 certificate/key pair to operate,
# so wait for the AppController to write them to the local file system.
NeptuneManager.log("Checking for the certificate and private key")
server_cert = nil
server_key = nil
loop {
  server_cert = HelperFunctions.get_cert(appscale_dir + "certs/mycert.pem")
  server_key = HelperFunctions.get_key(appscale_dir + "certs/mykey.pem")
  break if !server_cert.nil? && !server_key.nil?
  NeptuneManager.log("Waiting on certs")
  Kernel.sleep(5)
}


# Finally, start the NeptuneManagerServer now that we have the
# X509 certs.
NeptuneManager.log("Starting up SOAP frontend for NeptuneManager")
server = NeptuneManagerServer.new(
  :BindAddress => "0.0.0.0",
  :Port => NeptuneManager::SERVER_PORT,
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
