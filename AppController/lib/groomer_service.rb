#!/usr/bin/ruby -w


$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'monit_interface'


# Starts and stops the datastore groomer service.
module GroomerService

  # Starts the Groomer Service on this machine. We don't want to monitor
  # it ourselves, so just tell monit to start it and watch it.
  def self.start()
    start_cmd = "/usr/bin/python /root/appscale/AppDB/groomer_service.py"
    # The stop command doesn't work and relies on terminate.rb.
    stop_cmd = "/usr/bin/pkill -9 groomer_service"
    MonitInterface.start(:groomer_service, start_cmd, stop_cmd, "9999", {})
  end

  # Stops the groomer service running on this machine. Since it's
  # managed by monit, just tell monit to shut it down.
  def self.stop()
     MonitInterface.stop(:groomer_service)
  end

end

