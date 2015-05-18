#!/usr/bin/ruby -w


$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'monit_interface'


# Starts and stops the backup and recovery service.
module BackupRecoveryService

  BR_PORT = '8423'

  # Starts the BR Service on this machine. We don't want to monitor
  # it ourselves, so just tell monit to start it and watch it.
  def self.start()
    start_cmd = "/usr/bin/python /root/appscale/AppDB/backup/backup_recovery_service.py"
    # The stop command doesn't work and relies on terminate.rb.
    stop_cmd = "/usr/bin/pkill -9 backup_recovery_service"
    MonitInterface.start(:backup_recovery_service, start_cmd, stop_cmd, BR_PORT,
     {})
  end

  # Stops the backup/recovery service running on this machine. Since it's
  # managed by monit, just tell monit to shut it down.
  def self.stop()
     MonitInterface.stop(:backup_recovery_service)
  end

end

