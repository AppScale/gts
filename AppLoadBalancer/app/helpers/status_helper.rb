require 'usertools'

module StatusHelper
  include ApplicationHelper
  # TODO: Add test coverage to this helper when it has been cleaned up

  def is_slave_node
    head_node_ip = get_head_node_ip
    my_ip = get_my_ip

    (head_node_ip != my_ip) && get_status_files.empty?
  end

  def head_node_url
    head_node_ip = get_head_node_ip

    if head_node_ip == get_my_ip
      "http://#{head_node_ip}"
    else
      "http://#{head_node_ip}/status"
    end
  end

  def get_status_information
    status_files = get_status_files 
    
    servers = []
    status_files.each { |filename|
      #cached_server = CACHE.get("status-#{filename}")
      cached_server = nil
      if cached_server.nil?
        contents = (File.open(filename) { |f| f.read }).chomp
        server = {}
        server[:ip] = filename.scan(/status-(.*)\.log/).flatten.to_s
        server[:cpu] = contents.scan(/(\d+\.\d+) Percent CPU/).flatten.to_s
        server[:memory] = contents.scan(/(\d+\.\d+) Percent Memory/).flatten.to_s
        server[:disk] = contents.scan(/Hard disk is (\d+) Percent full/).flatten.to_s
        server[:vms_up] = contents.scan(/\d+\.\d+\.\d+\.\d+/).uniq.join(",")
        server[:cloud] = contents.scan(/Is in cloud:(.*)/).flatten.to_s
        server[:roles] = contents.scan(/Is currently: (.*)/).flatten.to_s

        #CACHE.set("status-#{filename}", server.to_a.join("|||"), 10)
      else
        server = Hash[*cached_server.split("|||")]
        # TODO: find a better way to do this - converting hash -> array -> string
        # and back causes us to lose the symbols
        server.each_pair { |k, v|
          server[k.to_sym] = v
        }
      end

      servers << server
    }

    return servers
  end

  def get_database_information
    table = CACHE.get("database")
    replication = CACHE.get("replication")

    if table.nil? or replication.nil?    
      db_info_path = "#{APPSCALE_HOME}/.appscale/database_info.yaml"    
      tree = YAML.load_file(db_info_path)
      table = tree[:table]
      replication = tree[:replication]

      CACHE.set("database", table, 60)
      CACHE.set("replication", replication, 60)
    end

    { :database => table, :replication => replication }
  end

end
