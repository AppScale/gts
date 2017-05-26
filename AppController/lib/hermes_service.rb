#!/usr/bin/ruby -w

$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'monit_interface'

# Starts and stops the Hermes (messenger) service.
module HermesService

  # Starts the Hermes service on this machine. We don't want to monitor
  # it ourselves, so just tell monit to start it and watch it.
  def self.start(verbose, write_nodes_stats_log,
                 write_processes_stats_log, write_proxies_stats_log,
                 write_detailed_processes_stats_log,
                 write_detailed_proxies_stats_log)
    script = `which appscale-hermes`.chomp
    start_cmd = "/usr/bin/python2 #{script}"
    start_cmd << ' --verbose' if verbose
    start_cmd << ' --write-nodes-log' if write_nodes_stats_log
    start_cmd << ' --write-processes-log' if write_processes_stats_log
    start_cmd << ' --write-proxies-log' if write_proxies_stats_log
    start_cmd << ' --write-detailed-processes-log' if write_detailed_processes_stats_log
    start_cmd << ' --write-detailed-proxies-log' if write_detailed_proxies_stats_log
    MonitInterface.start(:hermes, start_cmd)
  end

  # Stops the Hermes service running on this machine. Since it's
  # managed by monit, just tell monit to shut it down.
  def self.stop()
    MonitInterface.stop(:hermes)
  end

end
