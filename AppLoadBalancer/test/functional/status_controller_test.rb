require 'test_helper'

class StatusControllerTest < ActionController::TestCase
  context "on a GET to :cloud from a slave node" do
    setup do
      assume_valid_session
      @head_node_url = "http://192.168.1.1"
      flexmock(@controller).should_receive("is_slave_node").once.and_return(true)
      flexmock(@controller).should_receive("head_node_url").once.and_return(@head_node_url)
      get :cloud
    end
    
    should_respond_with :redirect
    should_redirect_to("the head node") { @head_node_url }
    should_not_set_the_flash
  end

  context "on a GET to :cloud from a head node" do
    setup do
      assume_valid_session
      flexmock(@controller).should_receive("is_slave_node").once.and_return(false)
      get :cloud
    end
    
    should_respond_with :success
    should_render_template :cloud
    should_not_set_the_flash
  end
end
