class MetaData
  # Looks over the graphs and adds any new graphs that weren't previously available
  def self.refresh_available_graphs
    machine_names = Dir.sub_dirs(RRD_DATA_PATH)
    machine_names.each do |machine_name|
      machine = Machine.find_or_create_by_name(machine_name)
      machine.refresh!
    end
  end

  # Empties out all meta-data stored in the db and
  # then refetches it. Good for when the underlying data/files
  # have changed significantly.
  def self.hard_refresh_available_graphs
    # Flush out all the meta-data tables
    Machine.delete_all
    Service.delete_all
    RrdDatabase.delete_all
    DataSource.delete_all
    refresh_available_graphs
  end

  class ConfigurationError < StandardError; end

  def self.check_rrd_tool
    unless File.executable?(RRD_TOOL)
      message = "The specified RRD_TOOL is not executable: #{RRD_TOOL.to_s}. The path of RRD_TOOL can be changed in config/environment.rb."
      raise ConfigurationError, message
    end
  end

  def self.check_rrd_data_path
    unless File.directory?(RRD_DATA_PATH)
      message = "The specified RRD_DATA_PATH does not exist: #{RRD_DATA_PATH.to_s}. The path of RRD_DATA_PATH can be changed in config/environment.rb."
      raise ConfigurationError, message
    end
  end
end
