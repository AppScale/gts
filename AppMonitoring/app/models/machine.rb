class Machine < ActiveRecord::Base
  has_many :services
  validates_presence_of :name
  validates_uniqueness_of :name

  named_scope :include_all, :include => { :services => { :rrd_databases => :data_sources } }

  def display_name
    self.pretty_name || self.name
  end

  def path
    File.join(RRD_DATA_PATH, self.name)
  end

  def refresh!
    service_names = Dir.sub_dirs(self.path)
    
    service_names.each do |service_name|
      service = Service.find_or_initialize_by_name_and_machine_id(service_name,self.id)
      service.pretty_name = service.name.gsub(/[-_]/, ' ')
      if service.save
        Rails.logger.info "Saved #{service.machine.id} #{service.machine.name} #{service.name}"
      else
        Rails.logger.info "Save failed! #{service.machine.id} #{service.machine.name} #{service.name}"
      end
      service.refresh!
    end
  end
end
