require 'dbfrontend'

ALL_CAPABILITIES = ["upload_app", "mr_api", "ec2_api", "neptune_api"]

module AuthorizeHelper
  include ApplicationHelper

  def is_slave_node
    head_node_ip = get_head_node_ip
    my_ip = get_my_ip

    (head_node_ip != my_ip) && get_neptune_jobs.empty?
  end

  def head_node_url
    head_node_ip = get_head_node_ip

    if head_node_ip == get_my_ip
      "http://#{head_node_ip}"
    else
      "http://#{head_node_ip}/status"
    end
  end

  def get_all_users
    DBFrontend.get_all_users().split(":") - ["____"] # remove dummy entry
  end

  def get_authorization_info
    all_users = get_all_users
    Rails.logger.info("oi! all_users is of class #{all_users.class} and contains [#{all_users.join(', ')}]")

    info = {}
    ip = get_head_node_ip

    all_users.each { |user|
      next if user =~ /@#{ip}\Z/ # skip the XMPP user accounts
      capabilities = DBFrontend.get_capabilities(user).split(":")
      info[user] = capabilities
      Rails.logger.info("oi! found user #{user} with capabilities #{capabilities.join(', ')}")
    }

    return info
  end

  def user_has_ability?(cap, caps)
    return caps.include?(cap)
  end
end
