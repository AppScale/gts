class Service < ActiveRecord::Base
  belongs_to :machine
  has_many :rrd_databases
  validates_presence_of :name
  validates_uniqueness_of :name, :scope => [:machine_id]

  def display_name
    self.pretty_name || self.name
  end

  def path
    File.join(RRD_DATA_PATH, self.machine.name, self.name)
  end

  def refresh!
    database_names = Dir.entries(self.path)
    # Only want files with the rrd extension
    database_names = database_names.map { |db| db if File.file?(File.join(self.path,db)) && File.extname(db) == RRD_EXTENSION }.compact
    
    database_names.each do |database_name|
      database = RrdDatabase.find_or_initialize_by_name_and_service_id(database_name, self.id)
      # strip off the rrd extension so that the name is prettier
      clean_name = database.name.gsub(RRD_EXTENSION,"")
      database.pretty_name = clean_name.gsub(/[-_]/, ' ')

      prefix = clean_name.rindex(/[-_]/) || clean_name.length
      database.group = clean_name[0..prefix-1]

      if database.save
        Rails.logger.info "Saved #{self.machine.name} #{self.name} #{database.name}"
      else
        Rails.logger.info "Save failed! #{self.machine.name} #{self.name} #{database.name}"
      end
      database.refresh!
    end
  end
end
