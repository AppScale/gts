#!/usr/bin/ruby -w

require 'json'
require 'net/http'

require 'helperfunctions'


module HermesClient

  # The port that Hermes binds to.
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
    rescue Errno::ETIMEDOUT, Timeout::Error
      raise FailedNodeException.new("Failed to call Hermes: timed out")
    rescue Errno::EHOSTUNREACH
      raise FailedNodeException.new("Failed to call Hermes: host unreachable")
    rescue Errno::ECONNREFUSED
      raise FailedNodeException.new("Failed to call Hermes: connection refused")
    end
  end

  def self.get_cpu_count(node_ip, secret)
    node_info = HermesClient.make_call(node_ip, secret, '/stats/local/node', {})
    return node_info['cpu']['count']
  end

  # Gets haproxy statistics from Hermes located on load balancer node.
  #
  # Args:
  #   lb_ip: IP address of load balancer node.
  #   secret: Deployment secret.
  #   fetch_servers: Determines if backend servers list should be fetched
  # Returns:
  #   a list of hashes describing proxy stats.
  #
  def self.get_proxies_stats(lb_ip, secret, fetch_servers=true)
    data = {
      'include_lists' => {
        'proxy' => ['name', 'accurate_frontend_scur', 'backend',
                    'frontend', 'servers'],
        'proxy.frontend' => ['req_tot'],
        'proxy.backend' => ['qcur']
      },
      'max_age' => 5
    }
    if fetch_servers
      data['include_lists']['proxy.server'] = [
        'private_ip', 'port', 'status'
      ]
    end
    proxies_list = HermesClient.make_call(
      lb_ip, secret, '/stats/local/proxies', data
    )
    return proxies_list['proxies_stats']
  end

  # Gets haproxy statistics for a specific proxy
  # from Hermes located on load balancer node.
  #
  # Args:
  #   lb_ip: IP address of load balancer node.
  #   secret: Deployment secret.
  #   proxy_name: Name of proxy to return.
  #   fetch_servers: Determines if backend servers list should be fetched
  # Returns:
  #   a hash containing proxy stats.
  #
  def self.get_proxy_stats(lb_ip, secret, proxy_name, fetch_servers=true)
    proxies = HermesClient.get_proxies_stats(lb_ip, secret, fetch_servers)
    proxy = proxies.detect{|item| item['name'] == proxy_name}
    return proxy unless proxy.nil?
    raise AppScaleException.new("Proxy #{proxy_name} was not found at #{lb_ip}")
  end

  # Gets total_requests, total_req_in_queue and current_sessions
  # for a specific proxy from Hermes located on load balancer node.
  #
  # Args:
  #   lb_ip: IP address of load balancer node.
  #   secret: Deployment secret.
  #   proxy_name: Name of proxy to return.
  # Returns:
  #   The total requests for the proxy, the requests enqueued and current sessions.
  #
  def self.get_proxy_load_stats(lb_ip, secret, proxy_name)
    proxy = HermesClient.get_proxy_stats(lb_ip, secret, proxy_name, false)
    total_requests_seen = proxy['frontend']['req_tot']
    total_req_in_queue = proxy['backend']['qcur']
    current_sessions = proxy['accurate_frontend_scur']
    Djinn.log_debug("HAProxy load stats for #{proxy_name} at #{lb_ip}: " \
      "req_tot=#{total_requests_seen}, qcur=#{total_req_in_queue}, " \
      "scur=#{current_sessions}")
    return total_requests_seen, total_req_in_queue, current_sessions
  end

  # Gets node cpu, memory, loadavg, and disk information from Hermes located on
  # the local node.
  #
  # Args:
  #   ip: IP address of the local node.
  #   secret: Deployment secret.
  #   proxy_name: Name of proxy to return.
  # Returns:
  #   The system stats for the local node.
  #
  def self.get_system_stats(ip, secret)
    data = {
      'include_lists' => {
        'node'=> ['memory', 'loadavg', 'partitions_dict', 'cpu', 'swap'],
        'node.cpu'=> ['idle', 'system', 'user', 'count', 'percent'],
        'node.partition'=> ['used', 'total', 'free'],
        'node.memory' => ['total', 'available', 'used'],
        'node.swap' => ['total', 'used', 'free'],
        'node.loadavg'=> ['last_1min', 'last_5min', 'last_15min']
      },
      'max_age' => 5
    }
    node_stats_list = HermesClient.make_call(
      ip, secret, '/stats/local/node', data
    )
    Djinn.log_debug("Received #{node_stats_list}")
    return node_stats_list
  end
end
