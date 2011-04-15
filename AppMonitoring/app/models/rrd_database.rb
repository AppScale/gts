class RrdDatabase < ActiveRecord::Base
  belongs_to :service
  has_many :data_sources
  validates_presence_of :name
  validates_uniqueness_of :name, :scope => [:service_id]

  named_scope :group, lambda { |group| { :conditions => { :group => group } } }

  def path
    File.join(RRD_DATA_PATH, self.service.machine.name, self.service.name, self.name)
  end

  def display_name
    self.pretty_name || self.name
  end

  def metric_name
    self.name.gsub("#{self.group}-","").gsub(RRD_EXTENSION,'')
  end

  # TODO: find a cleaner and faster implementation of this
  def fetch_data_sources
    data_sources = []
    command = "#{RRD_TOOL} info #{self.path}"
    results = `#{command}`

    results.each do |result|
      # How did this perl end up in here...
      name = result.match /^ds\[([\w_\-]+)\]/
      if name && name.length > 0
        data_sources << name[1]
      end
    end
    
    data_sources.sort.uniq
  end

  def refresh!
    if self.data_sources.length > 0
      # No need to refresh the database if the data sources have already been found. They shouldn't change.
      Rails.logger.info("#{self.name} has already been setup, skipping update")
      return
    end

    data_source_names = self.fetch_data_sources

    data_source_names.each do |data_source_name|
      data_source = DataSource.find_or_initialize_by_name_and_rrd_database_id(data_source_name, self.id)
      data_source.pretty_name = data_source.name.gsub(/[-_]/, ' ')

      if data_source.save
        Rails.logger.info "Saved #{self.name} #{data_source.name}"
      else
        Rails.logger.info "Save failed #{self.name} #{data_source.name}"
      end
    end
  end
end
