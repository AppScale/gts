require 'test_helper'

class UsersControllerTest < ActionController::TestCase
  context "on a GET to :new" do
    setup do
      assume_valid_session
      get :new
    end
    
    should_assign_to :user
    should_respond_with :success
    should_render_template :new
    should_not_set_the_flash
  end

  context "on a POST to :create with an invalid user" do
    setup do
      assume_valid_session
      user = { :email => "invalid@emailaddress", :password => "bar", :password_confirmation => "passw0rd" }
      post :create, user
    end
    should_assign_to :user
    should_respond_with :success
    should_render_template :new
    should_set_the_flash_to "There was an error with your submission"

    should "be an invalid user" do
      assert !assigns(:user).valid?
    end
  end

  context "on a POST to :create with an error creating the user" do
    setup do
      assume_valid_session
      params = { "email" => "valid@email.com", "password" => "passw0rd", "password_confirmation" => "passw0rd" }
      @mocked_user = User.new(params)
      flexmock(User).should_receive("new").once.with(params).and_return(@mocked_user)
      flexmock(@mocked_user).should_receive("create_account").once.and_return({ :success => false, :message => "The provided email address is taken. Please choose another one." })
      post :create, { :user => params }
    end
    should_assign_to :user
    should_respond_with :success
    should_render_template :new
    should_set_the_flash_to "The provided email address is taken. Please choose another one."

    should "be an valid user" do
      assert assigns(:user).valid?
    end
  end

  context "on a POST to :create with a valid user" do
    setup do
      assume_valid_session
      params = { "email" => "valid@email.com", "password" => "passw0rd", "password_confirmation" => "passw0rd" }
      @mocked_user = User.new(params)
      flexmock(User).should_receive("new").once.with(params).and_return(@mocked_user)
      flexmock(@mocked_user).should_receive("create_account").once.and_return({ :success => true, :message => "User successfully created. Welcome!" })
      @controller.should_receive(:create_token).once.and_return(true)
      @controller.should_receive(:set_appserver_cookie).once.and_return(true)
      post :create, { :user => params }
    end
    should_assign_to :user
    should_respond_with :redirect
    should_redirect_to("the main page"){ root_path }
    should_set_the_flash_to "Your account has been successfully created"

    should "be an valid user" do
      assert assigns(:user).valid?
    end
  end

  context "on a GET to :login without a continue parameter or valid token" do
    setup do
      assume_valid_session
      flexmock(@controller).should_receive("should_be_redirected?").once.and_return(false)
      flexmock(@controller).should_receive("has_valid_token?").once.and_return(false)
      get :login
    end
    
    should_assign_to :user
    should_respond_with :success
    should_render_template :login
    should_not_set_the_flash
  end


  context "on a GET to :login with a valid continue parameter" do
    setup do
      assume_valid_session
      @destination_url = "http://destination.com/:1234"
      flexmock(@controller).should_receive("should_be_redirected?").once.and_return(true)
      flexmock(@controller).should_receive("get_redirect_url").once.and_return(@destination_url)
      flexmock(@controller).should_receive("has_valid_token?").once.and_return(false)
      get :login
    end
    
    should_assign_to :user
    should_respond_with :redirect
    should_redirect_to("the destination url") { "http://destination.com/:1234" }
    should_not_set_the_flash
  end

  context "on a GET to :login with a valid token" do
    setup do
      assume_valid_session
      flexmock(@controller).should_receive("should_be_redirected?").once.and_return(false)
      flexmock(@controller).should_receive("has_valid_token?").once.and_return(true)
      get :login
    end
    
    should_assign_to :user
    should_respond_with :success
    should_render_template :confirm
    should_not_set_the_flash
  end

  context "on a POST to :authenticate with an invalid user" do
    setup do
      assume_valid_session
      user = { :email => "user@email.com" }
      post :authenticate, user
    end
    should_assign_to :user
    should_respond_with :success
    should_render_template :login
    should_set_the_flash_to "There was an error with your submission"

    should "be an invalid user" do
      assert !assigns(:user).valid?
    end

    should "not be logged in" do
      assert !session[:logged_in]
    end
  end

  context "on a POST to :authenticate where the user failed to authenticate" do
    setup do
      assume_valid_session
      params = { "email" => "valid@email.com", "password" => "passw0rd" }
      @mocked_user = User.new(params)
      flexmock(User).should_receive("new").once.with(params).and_return(@mocked_user)
      flexmock(@mocked_user).should_receive("authenticate!").once.and_return({ :success => false, :message => "The database appears to be down right now. Please contact your cloud administrator."})
      post :authenticate, { :user => params }
    end
    should_assign_to :user
    should_respond_with :success
    should_render_template :login
    should_set_the_flash_to "The database appears to be down right now. Please contact your cloud administrator."

    should "be an valid user" do
      assert assigns(:user).valid?
    end
    should "not be logged in" do
      assert !session[:logged_in]
    end
  end

  context "on a POST to :authenticate where the user does not get a token" do
    setup do
      assume_valid_session
      params = { "email" => "valid@email.com", "password" => "passw0rd" }
      @mocked_user = User.new(params)
      flexmock(User).should_receive("new").once.with(params).and_return(@mocked_user)
      flexmock(@mocked_user).should_receive("authenticate!").once.and_return({ :success => true })
      flexmock(@controller).should_receive("create_token").once.and_return(nil)

      post :authenticate, { :user => params }
    end
    should_assign_to :user
    should_respond_with :success
    should_render_template :login
    should_set_the_flash_to "The database appears to be down right now. Please contact your cloud administrator."

    should "be an valid user" do
      assert assigns(:user).valid?
    end
    should "not be logged in" do
      assert !session[:logged_in]
    end
  end

  context "on a POST to :authenticate where the user gets a token and should be redirected" do
    setup do
      assume_valid_session
      params = { "email" => "valid@email.com", "password" => "passw0rd" }
      @mocked_user = User.new(params)
      flexmock(User).should_receive("new").once.with(params).and_return(@mocked_user)
      flexmock(@mocked_user).should_receive("authenticate!").once.and_return({ :success => true })
      flexmock(@controller).should_receive("create_token").once.and_return("TOKEN")
      flexmock(@controller).should_receive("should_be_redirected?").once.and_return(true)
      flexmock(UserTools).should_receive("get_cookie_value").once.and_return("COOKIE_VALUE")
      flexmock(UserTools).should_receive("public_ip").once.and_return("PUBLIC_IP")

      post :authenticate, { :user => params }
    end
    should_assign_to :user
    should_redirect_to("the confirmation page") { confirm_path }

    should "be an valid user" do
      assert assigns(:user).valid?
    end
    should "be logged in" do
      assert session[:logged_in]
    end
    should "set the users cookie" do
      assert !@response.cookies["dev_appserver_login"].nil?
    end
  end

  context "on a POST to :authenticate where the user gets a token and should not be redirected" do
    setup do
      assume_valid_session
      params = { "email" => "valid@email.com", "password" => "passw0rd" }
      @mocked_user = User.new(params)
      flexmock(User).should_receive("new").once.with(params).and_return(@mocked_user)
      flexmock(@mocked_user).should_receive("authenticate!").once.and_return({ :success => true })
      flexmock(@controller).should_receive("create_token").once.and_return("TOKEN")
      flexmock(@controller).should_receive("should_be_redirected?").once.and_return(false)
      flexmock(UserTools).should_receive("get_cookie_value").once.and_return("COOKIE_VALUE")
      flexmock(UserTools).should_receive(:public_ip).once.and_return("PUBLIC_IP")

      post :authenticate, { :user => params }
    end
    should_assign_to :user
    should_redirect_to("the main page") { root_path }

    should "be an valid user" do
      assert assigns(:user).valid?
    end
    should "be logged in" do
      assert session[:logged_in]
    end
    should "set the users cookie" do
      assert !@response.cookies["dev_appserver_login"].nil?
    end
  end

  context "on a POST to :verify when the user selects no" do
    setup do
      assume_valid_session
      post :verify, { :commit => "No" }
    end
    should_redirect_to("the main page") { root_path }
  end

  context "on a POST to :verify when the user selects yes but has not destination url" do
    setup do
      assume_valid_session
      flexmock(@controller).should_receive("get_destination_url").once.and_return(nil)
      post :verify, { :commit => "Yes" }
    end
    should_redirect_to("the main page") { root_path }
    should_set_the_flash_to "Destination URL not set. Unable to redirect."
  end

  context "on a POST to :verify when the user selects yes and has a destination url" do
    setup do
      assume_valid_session
      flexmock(@controller).should_receive("get_destination_url").once.and_return("http://destination.com")
      post :verify, { :commit => "Yes" }
    end
    should_redirect_to("the destination url") { "http://destination.com" }
  end

  context "on a GET to :confirm" do
    setup do
      assume_valid_session
      get :confirm
    end

    should_respond_with :success
    should_render_template :confirm
  end

  context "on a POST to :logout" do
    setup do
      assume_valid_session
      post :logout
    end
    should_redirect_to("the main page") { root_path }

    should "clear sesion variables (except flash messages)" do
      session_variables = session
      session_variables.delete("flash")
      assert session_variables.empty?
    end
  end
end

