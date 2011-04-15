require 'test_helper'
require 'flexmock/test_unit'

class UserTest < ActiveSupport::TestCase
  should "require an email address" do
    @user = User.new
    assert !@user.valid?
    assert_contains @user.errors.on(:email), "can't be empty"
  end

  should "require a password" do
    @user = User.new
    assert !@user.valid?
    assert_contains @user.errors.on(:password), "can't be empty"
  end

  should "require the password to be the same as password confirmation" do
    @user = User.new(:password => "passw0rd", :password_confirmation => "notthesame")
    assert !@user.valid?
    assert_contains @user.errors.on(:password), "doesn't match confirmation"
  end

  should "require a properly formatted email address" do
    @user = User.new(:email => "invalidemail.blah")
    assert !@user.valid?
    assert_contains @user.errors.on(:email), "Format must be foo@boo.goo"

    @user.email = "still@invalid"
    assert !@user.valid?
    assert_contains @user.errors.on(:email), "Format must be foo@boo.goo"
  end

  should "allow properly formatted email addresses" do
    @user = User.new(:email => "valid@good.com")
    assert @user.errors.on(:email).nil?

    @user.email = "Still+1@valid.email.net"
    assert @user.errors.on(:email).nil?
  end

  should "be valid with a good email and password" do
    @user = User.new(:email => "a@valid.user.ca", :password => "passw0rd", :password_confirmation => "passw0rd")
    assert @user.valid?
  end

  context "Create an account" do
    setup do
      @connection = flexmock("conn")
      @secret = flexmock("secret")

      # Mock out the external service so its responses are controlled
      flexmock(DBFrontend).should_receive("get_instance").once.and_return(@connection)
      flexmock(UserTools).should_receive("get_secret_key").once.and_return(@secret)

      @user = User.new(:email => "sample@user.com", 
                       :password => "passw0rd", 
                       :password_confirmation => "passw0rd")
    end

    should "not create an account whose email already exists" do
      @connection.should_receive("does_user_exist").once.with(@user.email, @secret).and_return("true")
      result = @user.create_account
      assert !result[:success]
      assert_equal result[:message], "The provided email address is taken. Please choose another one."
    end

    should "not create an account if the user is not committed" do
      @connection.should_receive("does_user_exist").once.with(@user.email, @secret).and_return("false")
      encrypted_password = "ENCRYPTED_PASSWORD"
      flexmock(UserTools).should_receive("encrypt_password").once.with(@user.email, @user.password).and_return(encrypted_password)

      error_message = "It failed miserably"
      @connection.should_receive("commit_new_user").once.with(@user.email, encrypted_password, "user", @secret).and_return(error_message)

      result = @user.create_account
      
      assert !result[:success]
      assert_equal result[:message], "There was a problem committing the new user. The error message is: [It failed miserably]"
    end

    should "handle a database which returns Errno::ECONNREFUSED" do
      @connection.should_receive("does_user_exist").once.with(@user.email, @secret).and_raise(Errno::ECONNREFUSED)
      result = @user.create_account
      assert !result[:success]
      assert_equal result[:message], "The database appears to be down right now. Please contact your cloud administrator."
    end

    should "return true when a valid user is created" do
      @connection.should_receive("does_user_exist").once.with(@user.email, @secret).and_return("false")
      encrypted_password = "ENCRYPTED_PASSWORD"
      flexmock(UserTools).should_receive("encrypt_password").once.with(@user.email, @user.password).and_return(encrypted_password)

      @connection.should_receive("commit_new_user").once.with(@user.email, encrypted_password, "user", @secret).and_return("true")

      result = @user.create_account
      
      assert result[:success]
      assert_equal result[:message], "User successfully created. Welcome!"
    end
  end

  context "authenticate!" do
    setup do
      @connection = flexmock("conn")
      @secret = flexmock("secret")

      # Mock out the external service so its responses are controlled
      flexmock(DBFrontend).should_receive("get_instance").once.and_return(@connection)
      flexmock(UserTools).should_receive("get_secret_key").once.and_return(@secret)

      @user = User.new(:email => "sample@user.com", 
                       :password => "passw0rd")
                       
    end

    should "fail if the connection was refused" do
      @connection.should_receive("get_user_data").once.with(@user.email, @secret).and_raise(Errno::ECONNREFUSED)
      result = @user.authenticate!
      assert !result[:success]
      assert_equal result[:message], "The database appears to be down right now. Please contact your cloud administrator."
    end

    should "fail if the host was unreachable" do
      @connection.should_receive("get_user_data").once.with(@user.email, @secret).and_raise(Errno::EHOSTUNREACH)
      soaploc = "SOAPLOC"
      flexmock(DBFrontend).should_receive("hsoaploc").once.and_return(soaploc)
      result = @user.authenticate!
      assert !result[:success]
      assert_equal result[:message],"The database was unable to be reached. DB Connection to #{soaploc}"
    end

    should "fail if the username and password are not correct" do 
      @connection.should_receive("get_user_data").once.with(@user.email, @secret).and_return("Error: user not found")
 
      result = @user.authenticate!
      assert !result[:success]
      assert_equal result[:message], "Incorrect username / password combination. Please try again."
    end

    should "fail if the provided password doesn't match the stored one" do
      @connection.should_receive("get_user_data").once.with(@user.email, @secret).and_return("password: Id0ntMatch")
 
      result = @user.authenticate!
      assert !result[:success]
      assert_equal result[:message], "Incorrect username / password combination. Please try again."
    end

    should "succeed with a valid user" do 
      encrypted_password = "abc123"
      @connection.should_receive("get_user_data").once.with(@user.email, @secret).and_return("password:#{encrypted_password}")
      flexmock(UserTools).should_receive("encrypt_password").once.with(@user.email, @user.password).and_return(encrypted_password) 
      result = @user.authenticate!
      assert result[:success]
    end
  end
  
  context "create_token" do
    setup do
      @connection = flexmock("conn")
      @secret = flexmock("secret")

      # Mock out the external service so its responses are controlled
      flexmock(DBFrontend).should_receive("get_instance").once.and_return(@connection)
      flexmock(UserTools).should_receive("get_secret_key").once.and_return(@secret)

      @expiration = "A Long Time From Now"
      flexmock(User).should_receive("get_token_expiration_date").once.and_return(@expiration)
      @ip = "192.168.1.1"

      @user = User.new(:email => "sample@user.com", 
                       :password => "passw0rd")    
    end
    should "return nil if the connection is refused" do
      @connection.should_receive("commit_new_token").once.and_raise(Errno::ECONNREFUSED)
      
      assert @user.create_token(@ip).nil?
    end
    should "return the token upon success" do
      @connection.should_receive("commit_new_token").once.with(@ip, @user.email, @expiration, @secret).and_return(true)
      
      assert_equal @user.create_token(@ip), @user.email
    end
  end
end
