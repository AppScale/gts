require 'json'
require 'usertools'

SERVICE_NAMES = %w{ blobstore datastore images memcache taskqueue urlfetch users xmpp }

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
      raw_contents = (File.open(filename) { |f| f.read })
      server = {}

      begin
        JSON.load(raw_contents).each { |k, v|
          key = k.to_sym
          if v.class == String
            server[key] = v
          elsif v.class == Array
            server[key] = v.join(', ')
          else
            server[key] = "#{v}"
          end
        }
      rescue Exception => e
      end

      servers << server
    }

    return servers
  end

  def get_database_information
    db_info_path = "/etc/appscale/database_info.yaml"    
    tree = YAML.load_file(db_info_path)
    table = tree[:table]
    replication = tree[:replication]
    { :database => table, :replication => replication }
  end

  def get_service_info
    health_info = "/etc/appscale/health.json"
    return {} unless File.exists?(health_info)

    contents = (File.open(health_info) { |f| f.read }).chomp
    return JSON.load(contents)
  end
end
