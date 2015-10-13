#!/usr/bin/ruby -w

$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'monit_interface'

# Starts and stops the Hermes (messenger) service.
module HermesService

  HERMES_PORT = '4378'

  # Starts the Hermes service on this machine. We don't want to monitor
  # it ourselves, so just tell monit to start it and watch it.
  def self.start()
    start_cmd = "/usr/bin/python /root/appscale/Hermes/hermes.py"
    stop_cmd = "/usr/bin/python /root/appscale/scripts/stop_service.py hermes.py python"
    MonitInterface.start(:hermes, start_cmd, stop_cmd, HERMES_PORT, {})
  end

  # Stops the Hermes service running on this machine. Since it's
  # managed by monit, just tell monit to shut it down.
  def self.stop()
    MonitInterface.stop(:hermes)
  end

end
