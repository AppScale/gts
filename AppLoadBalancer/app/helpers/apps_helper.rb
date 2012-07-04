DB_DOWN_MSG = "The database appears to be down right now. Please see your cloud administrator."
APP_NOT_FOUND_MSG = "We were not able to find any data for your application. If you just uploaded your application, please wait a moment and try again."
APP_NOT_RUNNING_MSG = "Your application is not running right now. If you just uploaded your application, please wait a moment and try again. Otherwise, please see your cloud administrator."
APP_FAILED_MSG = "All the servers hosting your application have failed. Please contact your cloud administrator for more information."

module AppsHelper
  include ApplicationHelper

  def get_application_path app_name, suffix
    return not_exists("Application not found.") if app_name.nil? || app_name.empty?
    return not_exists("Suffix cannot be nil.") if suffix.nil?

    app_data = DBFrontend.get_app_data(app_name)

    Rails.logger.info("oi! app data for #{app_name} was [#{app_data}]")

    return not_exists(DB_DOWN_MSG) if app_data.nil?

    if app_data == "Error: App not found"
      return not_exists(APP_NOT_FOUND_MSG) 
    end

    if app_data.include?("DB_ERROR")
      return not_exists(app_data)
    end

    num_ports = get_num_ports app_data

    if num_ports.nil? || num_ports == 0
      return not_exists(APP_NOT_RUNNING_MSG)
    end

    port = parse_app_data(app_data, app_name)
    destination = "http://#{get_head_node_ip}:#{port}"
    message = "redirect to #{destination}"

    exists(message, destination)
  end

  private

  def parse_app_data(app_data, app_name)
    data = {}
    data[:hosts] = app_data.scan(/num_hosts:\d+\s+hosts:(.*)\s+num_ports/).flatten[0].split(":")
    data[:ports] = app_data.scan(/ports: ([\d:]+)/).flatten[0].split(":")

    # TODO: validate that hosts.length == ports.length
    locations = []
    data[:hosts].each_index { |i|
      locations << "#{data[:hosts][i].gsub(/[\s\n]/, "")}:#{data[:ports][i]}"
    }
    data[:ports][0]
  end

  def get_num_ports app_data
    if app_data =~ /num_ports:(\d+)/
      begin
        return Integer($1) 
      rescue ArgumentError
      end
    end
    nil
  end

  def not_exists message=""
    { :exists => false, :message => message }
  end

  def exists(message, path)
    { :exists => true, :message => message, :path => path }
  end  
end
