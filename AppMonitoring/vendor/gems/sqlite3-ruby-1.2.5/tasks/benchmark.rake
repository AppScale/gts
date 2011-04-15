desc "Run benchmarks vs. sqlite-ruby"
task :benchmark do
  ruby "test/bm.rb"
end

desc "Run benchmarks dl vs. native"
task :benchmark2 do
  ruby "test/native-vs-dl.rb"
end
