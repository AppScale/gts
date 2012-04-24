# Programmer: Chris Bunch


# Imports for InfrastructureManager libraries
$:.unshift File.join(File.dirname(__FILE__), "lib")
require 'helperfunctions'


# InfrastructureManager provides callers with the ability to acquire and
# release virtual machines from cloud infrastructures without needing to know
# how to interact with them.
class InfrastructureManager


  # The shared secret that is used to authenticate remote callers.
  attr_accessor :secret


  def initialize
    @secret = HelperFunctions.get_secret()
  end


end
