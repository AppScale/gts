class CreateRrdDatabases < ActiveRecord::Migration
  def self.up
    create_table :rrd_databases do |t|
      t.string :name
      t.string :pretty_name
      t.string :group
      t.belongs_to :service
      t.timestamps
    end
  end

  def self.down
    drop_table :rrd_databases
  end
end
