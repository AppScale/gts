require 'usertools'

class GraphsController < ApplicationController
  include ApplicationHelper

  def index
    unless is_user_cloud_admin
      redirect_to "http://#{UserTools.public_ip}"
    end
  end

  def view
    unless is_user_cloud_admin
      redirect_to "http://#{UserTools.public_ip}"
    end

    machine_id = params[:machine]
    service_id = params[:service]
    rrd_database_id = params[:rrd_database]
    group = params[:group]
    time_window = params[:time]

    @graph = RrdGraph.new(machine_id, service_id, rrd_database_id, group, time_window)

    if !@graph.valid?
      flash[:error] = "Uh oh, an error occured when generating the graph. Please try a different graph or refresh the available graphs."
      redirect_to :action => :index
    end
  end

  def help
    unless is_user_cloud_admin
      redirect_to "http://#{UserTools.public_ip}"
    end
  end

  def refresh
    unless is_user_cloud_admin
      redirect_to "http://#{UserTools.public_ip}"
    end

    if params[:force]
      MetaData.hard_refresh_available_graphs
    else
      MetaData.refresh_available_graphs
    end

    redirect_to :controller => :graphs, :action => :index
  end
end
