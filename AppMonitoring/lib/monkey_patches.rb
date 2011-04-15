class Dir
  def self.sub_dirs folder
    entries = Dir.entries(folder) - [".",".."]
    entries.map! {|entry| entry if File.directory?(File.join(folder,entry))}.compact
  end
end
