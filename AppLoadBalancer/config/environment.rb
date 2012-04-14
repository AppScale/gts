
# Be sure to restart your server when you modify this file

# Specifies gem version of Rails to use when vendor/rails is not present
#RAILS_GEM_VERSION = '2.3.4' unless defined? RAILS_GEM_VERSION

# Uncomment below to force Rails into production mode when
# you don't control web/app server and can't set it the proper way
ENV['RAILS_ENV'] ||= 'production'

# Specifies gem version of Rails to use when vendor/rails is not present
APPSCALE_HOME=ENV['APPSCALE_HOME']
RAILS_ROOT  = File.expand_path(File.join(APPSCALE_HOME,"AppLoadBalancer"))

require 'net/http'
require 'open-uri'

# Bootstrap the Rails environment, frameworks, and default configuration
require File.join(File.dirname(__FILE__), 'boot')
require 'dbfrontend'
require 'usertools'

# oddly enough gem.memcache and gem.Ruby-Memcache below dont work
# TODO: fix that
require 'rubygems'
require 'json'

# The directory where uploaded apps will be stored
FILE_UPLOAD_PATH = File.join("/","tmp","uploaded-apps")
if !File.exist? FILE_UPLOAD_PATH
  FileUtils.mkdir_p FILE_UPLOAD_PATH
end

# The directory where the appscale tools are located
TOOLS_PATH = ENV['TOOLS_PATH'] || File.join("/","usr","local", "appscale-tools")

GZIP_MIME_TYPES = ["application/x-gzip","application/x-tar-gz", "application/gzip", "application/x-tar", "application/x-gtar", ]

# Bootstrap the Rails environment, frameworks, and default configuration
require File.join(File.dirname(__FILE__), 'boot')

Rails::Initializer.run do |config|
  # Settings in config/environments/* take precedence over those specified here.
  # Application configuration should go into files in config/initializers
  # -- all .rb files in that directory are automatically loaded.

  # Add additional load paths for your own custom dirs
  # config.load_paths += %W( #{RAILS_ROOT}/extras )

  # Specify gems that this application depends on and have them installed with rake gems:install
  # config.gem "bj"
  # config.gem "hpricot", :version => '0.6', :source => "http://code.whytheluckystiff.net"
  # config.gem "sqlite3-ruby", :lib => "sqlite3"
  config.gem "validatable"
  config.gem "flexmock"

  # Only load the plugins named here, in the order given (default is alphabetical).
  # :all can be used as a placeholder for all plugins not explicitly named
  # config.plugins = [ :exception_notification, :ssl_requirement, :all ]

  # Skip frameworks you're not going to use. To use Rails without a database,
  # you must remove the Active Record framework.
  config.frameworks -= [ :active_record ]

  secret = UserTools.get_secret_key * 2
  config.action_controller.session = {
    :session_key => '_load-balancer_session',
    :secret      => secret
  }

  # Activate observers that should always be running
  # config.active_record.observers = :cacher, :garbage_collector, :forum_observer

  # Set Time.zone default to the specified zone and make Active Record auto-convert to this zone.
  # Run "rake -D time" for a list of tasks for finding time zone names.
  config.time_zone = 'UTC'

  # The default locale is :en and all translations from config/locales/*.rb,yml are auto loaded.
  # config.i18n.load_path += Dir[Rails.root.join('my', 'locales', '*.{rb,yml}')]
  # config.i18n.default_locale = :de

end

