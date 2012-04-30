# Programmer: Chris Bunch


require 'datastore_repo'
require 'helperfunctions'


# An implementation of the Repository app that assumes it is running
# within AppScale. AppScale is assumed to start it up on its own.
class DatastoreRepoOnAppScale < DatastoreRepo

  
  # The host (IP, colon, port) that the Repo app is hosted at.
  attr_accessor :host


  # The name of this datastore, which we call AppDB since Neptune jobs
  # basically use it as an interface to AppScale's database agnostic
  # layer.
  NAME = "appdb"


  # The port that the repo runs on, by default.
  SERVER_PORT = 8079

  
  # Creates a new connection to the Repo running on AppScale. Since AppScale
  # starts the Repo automatically, this initialization does not start it.
  # TODO(cgb): The Repo isn't guaranteed to be running locally - either
  # ask the AppController or read it from a file.
  def initialize(credentials)
    repo_ip = "127.0.0.1"

    @host = "#{repo_ip}:#{SERVER_PORT}"
    HelperFunctions.sleep_until_port_is_open(repo_ip, SERVER_PORT,
      HelperFunctions::DONT_USE_SSL)
  end


end
