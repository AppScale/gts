# Programmer: Chris Bunch


require 'datastore_repo'
require 'helperfunctions'
require 'repo'


# An implementation of the Repository app that assumes it is running
# within AppScale. AppScale is assumed to start it up on its own.
class DatastoreRepoOnAppScale < DatastoreRepo

  
  # The host (IP, colon, port) that the Repo app is hosted at.
  attr_accessor :host


  # The name of this datastore, which we call AppDB since Neptune jobs
  # basically use it as an interface to AppScale's database agnostic
  # layer.
  NAME = "appdb"

  
  # Creates a new connection to the Repo running on AppScale. Since AppScale
  # starts the Repo automatically, this initialization does not start it.
  def initialize(credentials)
    repo_ip = Repo.get_public_ip()

    @host = "#{repo_ip}:#{Repo::SERVER_PORT}"
    HelperFunctions.sleep_until_port_is_open(repo_ip, Repo::SERVER_PORT,
      HelperFunctions::DONT_USE_SSL)
  end


end
