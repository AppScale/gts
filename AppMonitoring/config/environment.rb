# Be sure to restart your server when you modify this file

# Specifies gem version of Rails to use when vendor/rails is not present
RAILS_GEM_VERSION = '2.3.4' unless defined? RAILS_GEM_VERSION

# Bootstrap the Rails environment, frameworks, and default configuration
require File.join(File.dirname(__FILE__), 'boot')
require File.join(RAILS_ROOT, 'lib', "monkey_patches.rb")

RRD_EXTENSION = ".rrd"

# Specifies the folder which stores the RRD data.
# This folder should contain a sub-folder for each machine being monitored.
RRD_DATA_PATH = File.join("/","var","lib","collectd","rrd")

# The location of the rrdtool executable
RRD_TOOL = File.join("/","usr", "bin", "rrdtool")

# Where the generated graph images are stored. Note this folder can get large.
GRAPH_IMAGES_FOLDER = "graphs"
GRAPH_IMAGES_PATH = File.join("public","images", GRAPH_IMAGES_FOLDER)

# If the folder for storing the graphs doesn't exist, create it
unless File.exists?(GRAPH_IMAGES_PATH)
  require 'fileutils'
  FileUtils.mkdir_p GRAPH_IMAGES_PATH
end

Rails::Initializer.run do |config|
  # Settings in config/environments/* take precedence over those specified here.
  # Application configuration should go into files in config/initializers
  # -- all .rb files in that directory are automatically loaded.

  # Add additional load paths for your own custom dirs
  # config.load_paths += %W( #{RAILS_ROOT}/extras )

  # Specify gems that this application depends on and have them installed with rake gems:install
  config.gem "sqlite3-ruby", :lib => "sqlite3"

  # Only load the plugins named here, in the order given (default is alphabetical).
  # :all can be used as a placeholder for all plugins not explicitly named
  # config.plugins = [ :exception_notification, :ssl_requirement, :all ]

  # Skip frameworks you're not going to use. To use Rails without a database,
  # you must remove the Active Record framework.
  # config.frameworks -= [ :active_record, :active_resource, :action_mailer ]

  # Activate observers that should always be running
  # config.active_record.observers = :cacher, :garbage_collector, :forum_observer

  # Set Time.zone default to the specified zone and make Active Record auto-convert to this zone.
  # Run "rake -D time" for a list of tasks for finding time zone names.
  config.time_zone = 'UTC'

  # The default locale is :en and all translations from config/locales/*.rb,yml are auto loaded.
  # config.i18n.load_path += Dir[Rails.root.join('my', 'locales', '*.{rb,yml}')]
  # config.i18n.default_locale = :de

  if RAILS_ENV != "test"
    config.after_initialize do
      # Check that the machine table exists, otherwise they need to migrate the db
      if Machine.table_exists?
        MetaData.check_rrd_tool
        MetaData.check_rrd_data_path
        MetaData.refresh_available_graphs
      end
    end
  end
end
