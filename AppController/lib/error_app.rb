#!/usr/bin/ruby -w

require 'fileutils'

$:.unshift File.join(File.dirname(__FILE__))
require 'custom_exceptions'
require 'helperfunctions'

$:.unshift File.join(File.dirname(__FILE__), "..")
require 'djinn'


# This class generates a Python or Java Google App Engine application that 
# relays an error message to the user as to why their app failed to come up.
class ErrorApp
 
  #
  # Constructor 
  #
  # Args: 
  #   app_name: Name of the application to construct an error application for.
  #   error_msg: A String message that will be displayed as the reason 
  #              why we couldn't start their application.
  def initialize(app_name, error_msg)
    @app_name = app_name
    @error_msg = error_msg
    @dir_path = "/var/apps/#{app_name}/app/"
  end

  # High level for generating an error application.
  # 
  # Args: Language to generate for.
  def generate(language)
    if language == "java"
      return generate_java()
    else
      return generate_python()
    end
  end

  # This function places a generic java error application.
  def generate_java()
    Djinn.log_run("cp -r /root/appscale/AppServer_Java/error_app/* #{@dir_path}")
    app_xml =<<CONFIG
<?xml version="1.0" encoding="utf-8"?>
<appengine-web-app xmlns="http://appengine.google.com/ns/1.0">
  <application>#{@app_name}</application>
  <version>badversion</version>
  <threadsafe>true</threadsafe>

</appengine-web-app>
CONFIG
     
    HelperFunctions.write_file("#{@dir_path}/war/WEB-INF/appengine-web.xml",
      app_xml)
    app_tar = "/opt/appscale/apps/#{@app_name}.tar.gz"
    Djinn.log_run("rm #{app_tar}")
    Dir.chdir(@dir_path) do
      Djinn.log_run("tar zcvf #{app_tar} ./*")
    end

    return true
  end

  # This function places an updated app.yaml and error.py into the application
  # and retars the application file.
  def generate_python()
    app_yaml = <<CONFIG
application: #{@app_name}
version: 1
runtime: python27
api_version: 1
threadsafe: true

handlers:
- url: /.*
  script: #{@app_name}.application
CONFIG

    script = <<SCRIPT
import webapp2
class MainPage(webapp2.RequestHandler):
  def get(self):
    self.response.out.write('<html><body>')
    self.response.out.write("""<p>Your application failed to start</p>""")
    self.response.out.write("""<p>#{@error_msg}</p>""")
    self.response.out.write("""<p>If this is an AppScale issue please report it on <a href="https://github.com/AppScale/appscale/issues">http://github.com/AppScale/appscale/issues</a></p>""")
    self.response.out.write('</body></html>')

application = webapp2.WSGIApplication([
  ('/', MainPage),
], debug=True)

SCRIPT

    HelperFunctions.write_file("#{@dir_path}app.yaml", app_yaml)
    HelperFunctions.write_file("#{@dir_path}#{@app_name}.py", script)

    app_tar = "/opt/appscale/apps/#{@app_name}.tar.gz"
    Djinn.log_run("rm #{app_tar}")
    Dir.chdir(@dir_path) do
      Djinn.log_run("tar zcvf #{app_tar} app.yaml #{@app_name}.py")
    end

    return true
  end

end

