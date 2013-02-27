class AuthorizeController < ApplicationController
  include AuthorizeHelper

  def cloud
    if is_slave_node
      redirect_to head_node_url
    else
      if is_user_cloud_admin
        render :action => :cloud
      else
        redirect_to head_node_url
      end
    end
  end

  def update
    Rails.logger.info "received these params: [#{params.inspect}]"
    ip = get_head_node_ip
    get_all_users.each { |user|
      next if user =~ /@#{ip}\Z/ # skip XMPP accounts

      capabilities = []
      ALL_CAPABILITIES.each { |cap|
        checkbox_name = "#{user}-#{cap}"
        val = params[checkbox_name]
        Rails.logger.info "is #{checkbox_name} checked? [#{val}], of class #{val.class}"

        if val
          capabilities << cap
          Rails.logger.info "adding capability #{cap}"
        else
          Rails.logger.info "removing capability #{cap}"
        end
      }

      capabilities = capabilities.join(":")
      Rails.logger.info "setting #{user}'s capabilities to #{capabilities}"
      DBFrontend.set_capabilities(user, capabilities)
    }

    flash[:notice] = "Capabilities successfully updated!"
    render :action => :cloud
  end
end
