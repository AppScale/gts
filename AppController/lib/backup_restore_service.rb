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
    bk_service = self.scriptname()
    start_cmd = "/usr/bin/python2 #{bk_service}"
    stop_cmd = "/usr/bin/python2 #{APPSCALE_HOME}/scripts/stop_service.py " +
          "#{bk_service} /usr/bin/python2"
    MonitInterface.start(:backup_recovery_service, start_cmd, stop_cmd, BR_PORT,
     {})
  end

  # Stops the backup/recovery service running on this machine. Since it's
  # managed by monit, just tell monit to shut it down.
  def self.stop()
     MonitInterface.stop(:backup_recovery_service)
  end

  def self.scriptname()
    return "#{APPSCALE_HOME}/AppDB/backup/backup_recovery_service.py"
  end
end

