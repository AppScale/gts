#!/usr/bin/ruby -w


$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'service_helper'


# Starts and stops the datastore groomer service.
module GroomerService

  # Groomer service name for use with helper
  SERVICE_NAME_GROOMER = 'appscale-groomer'.freeze

  # Transaction groomer service name for use with helper
  SERVICE_NAME_TX_GROOMER = 'appscale-transaction-groomer'.freeze

  # Starts the Groomer Service on this machine.
  def self.start()
    ServiceHelper.start(SERVICE_NAME_GROOMER)
  end

  # Stops the groomer service running on this machine.
  def self.stop()
    ServiceHelper.stop(SERVICE_NAME_GROOMER)
  end

  def self.start_transaction_groomer(verbose)
    # TODO:STEVE: write out verbose environment setting
    ServiceHelper.start(SERVICE_NAME_TX_GROOMER)
  end

  def self.stop_transaction_groomer
    ServiceHelper.stop(SERVICE_NAME_TX_GROOMER)
  end
end
