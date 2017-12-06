#!/usr/bin/ruby -w

require 'json'
require 'net/http'
require 'helperfunctions'


module HermesClient

  # The port that the Hermes binds to.
  SERVER_PORT = 4378

  def self.make_call(node_ip, secret, endpoint, body_hash)
    uri = URI("http://#{node_ip}:#{SERVER_PORT}#{endpoint}")
    headers = {'Content-Type' => 'application/json',
               'Appscale-Secret' => secret}
    request = Net::HTTP::Get.new(uri.path, headers)
    request.body = JSON.dump(body_hash)
    begin
      response = Net::HTTP.start(uri.hostname, uri.port,
                                 :read_timeout => 30) do |http|
        http.request(request)
      end
      if response.code != '200'
        raise FailedNodeException.new("Failed to call Hermes: " \
           "#{response.code} #{response.msg}\n#{response.body}")
      end
      return JSON.load(response.body)
    rescue Errno::ETIMEDOUT
      raise FailedNodeException.new("Failed to call Hermes: timed out")
    end
    rescue Errno::ECONNREFUSED
      raise FailedNodeException.new("Failed to call Hermes: connection refused")
    end
  end

  # Gets haproxy statistics from Hermes located on load balancer node.
  #
  # Args:
  #   lb_ip: IP address of load balancer node.
  #   secret: Deployment secret.
  #   fetch_servers: Determins if backend servers list should be fetched
  #
  def self.get_proxies_stats(lb_ip, secret, fetch_servers=true)
    data = {
      'include_lists' => {
        'proxy' => ['name', 'accurate_frontend_scur', 'frontend', 'servers'],
        'proxy.frontend' => ['req_tot'],
        'proxy.backend' => ['qcur']
      },
      'max_age' => 0
    }
    data['include_lists']['proxy.servers'] = [
      'private_ip', 'port', 'status'
    ]
    proxies_list = HermesClient.make_call(
      lb_ip, secret, '/stats/local/proxies', data
    )
    return proxies_list
  end

  # Gets haproxy statistics for a specific proxy
  # from Hermes located on load balancer node.
  #
  # Args:
  #   lb_ip: IP address of load balancer node.
  #   secret: Deployment secret.
  #   proxy_name: Name of proxy to return.
  #   fetch_servers: Determins if backend servers list should be fetched
  #
  def self.get_proxy_stats(lb_ip, secret, proxy_name, fetch_servers=true)
    proxies = HermesClient.get_proxies_stats(lb_ip, secret, fetch_servers)
    return proxies.detect{|item| item['name'] == proxy_name}
  end

  # Gets total_requests, total_req_in_queue and current_sessions 
  # for a specific proxy from Hermes located on load balancer node.
  #
  # Args:
  #   lb_ip: IP address of load balancer node.
  #   secret: Deployment secret.
  #   proxy_name: Name of proxy to return.
  #
  def self.get_proxy_load_stats(lb_ip, secret, proxy_name)
    proxy = HermesClient.get_proxy_stats(lb_ip, secret, proxy_name, false)
    total_requests_seen = proxy['frontend']['req_tot']
    total_req_in_queue = proxy['backend']['qcur']
    current_sessions = proxy['accurate_frontend_scur']
    return total_requests_seen, total_req_in_queue
  end

  # Gets running and failed backend servers for a specific proxy.
  #
  # Args:
  #   lb_ip: IP address of load balancer node.
  #   secret: Deployment secret.
  #   proxy_name: Name of proxy to return.
  #
  def self.get_backend_servers(lb_ip, secret, proxy_name)
    proxy = HermesClient.get_proxy_stats(lb_ip, secret, proxy_name, true)

    running = proxy['servers'] \
      .select{|server| server['status'] != 'DOWN'} \
      .map{|server| "#{server['private_ip']}:#{server['port']}"}
      
    failed = proxy['servers'] \
      .select{|server| server['status'] == 'DOWN'} \
      .map{|server| "#{server['private_ip']}:#{server['port']}"}

    if running.length > HelperFunctions::NUM_ENTRIES_TO_PRINT
      Djinn.log_debug("Haproxy: found #{running.length} running AppServers " \
                      "for #{proxy_name}.")
    else
      Djinn.log_debug('Haproxy: found these running AppServers for ' \
                      "#{proxy_name}: #{running}.")
    end
    if failed.length > HelperFunctions::NUM_ENTRIES_TO_PRINT
      Djinn.log_debug("Haproxy: found #{failed.length} failed AppServers " \
                      "for #{proxy_name}.")
    else
      Djinn.log_debug('Haproxy: found these failed AppServers for ' \
                      "#{proxy_name}: #{failed}.")
    end
    return running, failed
  end

end
