require 'yaml'

class StatusController < ApplicationController
  include StatusHelper

  def cloud
    if is_slave_node
      redirect_to head_node_url
    else
      render :action => :cloud
    end
  end
end
