#!/usr/bin/ruby -w

$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'monit_interface'

# Starts and stops the Hermes (messenger) service.
module HermesService
  # Starts the Hermes service on this machine. We don't want to monitor
  # it ourselves, so just tell monit to start it and watch it.
  def self.start(verbose)
    script = `which appscale-hermes`.chomp
    start_cmd = "/usr/bin/python2 #{script}"
    start_cmd << ' --verbose' if verbose
    MonitInterface.start(:hermes, start_cmd)
  end
end
