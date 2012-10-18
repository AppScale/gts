#!/usr/bin/ruby -w

require 'fileutils'
require 'custom_exceptions'

$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'


$:.unshift File.join(File.dirname(__FILE__), "..")
require 'djinn'


# This class generates an application that relays an error message to 
# the user as to why their app failed to come up
class ErrorApp

  def initialize(app_name, error_msg)
    @app_name = app_name
    @error_msg = error_msg
    @dir_path = "/var/apps/#{app_name}/app/"
  end

  # This function places an updated app.yaml and error.py into the application
  # and retars the application file 
  def generate()
    app_yaml = <<CONFIG
application: #{@app_name}
version: 1
runtime: python
api_version: 1

handlers:
- url: .*
  script: #{@app_name}.py
CONFIG

    script = <<SCRIPT
from google.appengine.ext import webapp
import cgi
import datetime
import wsgiref.handlers
class MainPage(webapp.RequestHandler):
  def get(self):
    self.response.out.write('<html><body>')
    self.response.out.write("""<p>Your application failed to start</p>""")
    self.response.out.write("""<p>#{@error_msg}</p>""")
    self.response.out.write("""<p>If this is an AppScale issue please report it on <a href="https://github.com/AppScale/appscale/issues">http://github.com/AppScale/appscale/issues</a></p>""")
    self.response.out.write('</body></html>')

application = webapp.WSGIApplication([
  ('/', MainPage),
], debug=True)


def main():
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()

SCRIPT
    File.open(@dir_path + 'app.yaml', "w+") { |dest_file| dest_file.write(app_yaml) }
    File.open(@dir_path + "#{@app_name}.py", "w+") { |dest_file| dest_file.write(script) }
     
    puts "Running: tar zcvf #{@dir_path}/#{@app_name}.tar.gz #{@dir_path}"
    run_shell("rm #{@dir_path}/#{@app_name}.tar.gz")
    ret = 0
    Dir.chdir(@dir_path) do
      run_shell("tar zcvf #{@app_name}.tar.gz app.yaml #{@app_name}.py")
    end

#    if ret != 0
#      puts "Received a return value of #{ret}"
#      raise FailedShellExec.new("Taring of error app failed for #{@app_name}")
#    else
    return true
   # end
  end

  # Wrapper for a shell command. Allows for mocking. 
  def run_shell(cmd)
    puts cmd
    return `#{cmd}`
  end
end

