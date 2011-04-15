class DataSource < ActiveRecord::Base
  belongs_to :rrd_database
  validates_presence_of :name
  validates_uniqueness_of :name, :scope => [:rrd_database_id]

  def display_name
    self.pretty_name || self.name
  end
end
