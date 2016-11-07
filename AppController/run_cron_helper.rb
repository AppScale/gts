# you should run this script from appscale/AppController

$:.unshift File.join(File.dirname(__FILE__), "lib")
$:.unshift File.join(File.dirname(__FILE__), ".")

require 'tempfile'
require 'djinn'
require 'cron_helper'

djinn_test = Djinn.new
CronHelper.update_cron('172.17.0.2', 8080, 'python27', 'blitztinyarmypanoramic')
