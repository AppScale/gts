class CreateDataSources < ActiveRecord::Migration
  def self.up
    create_table :data_sources do |t|
      t.string :name
      t.string :pretty_name
      t.belongs_to :rrd_database
      t.timestamps
    end
  end

  def self.down
    drop_table :data_sources
  end
end
