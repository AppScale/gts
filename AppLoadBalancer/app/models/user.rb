class User
  include Validatable
  validates_presence_of :email, :password
  validates_length_of :password, :minimum => 6, :message => "Password must be at least 6 characters long"
  validates_confirmation_of :password
  validates_format_of :email, :with => /[0-9a-zA-Z\-\.]+@[0-9a-zA-Z\-\.]+\.[0-9a-zA-Z\-\.]+/, :message => "Format must be foo@boo.goo"

  attr_accessor :email
  attr_accessor :password
  attr_accessor :password_confirmation

  def initialize(options={})
    if options.kind_of?(Hash)
      options.each do |k,v|
        method = "#{k}="
        self.send(method,v) if self.respond_to?(method)
      end
    end
  end

  # Validatable calls id on the object which gives a deprecation warning
  # This is a simple way to get around that
  def id
    self.object_id
  end

  def create_account
    conn = DBFrontend.get_instance
    secret = UserTools.get_secret_key
    
    begin
      if conn.does_user_exist(self.email,secret) == "true"
        return unsuccessful("The provided email address is taken. Please choose another one.")
      end
      
      encr_passwd = UserTools.encrypt_password(self.email, self.password)
      result = conn.commit_new_user(self.email, encr_passwd, "user", secret)
      
      if result != "true" && result != "None" # replace later by checking for error at beginning
        return unsuccessful("There was a problem creating your user account. The error message is: [#{result}]")
      end

      # create xmpp account
      # for user a@a.a, this translates to a@login_ip

      pre = self.email.scan(/\A(.*)@/).flatten.to_s
      xmpp_user = "#{pre}@#{UserTools.login_ip}"
      xmpp_pass = UserTools.encrypt_password(xmpp_user, self.password)
      result = conn.commit_new_user(xmpp_user, xmpp_pass, "xmpp_user", secret)

      if result != "true" && result != "None" # replace later by checking for error at beginning
        return unsuccessful("There was a problem creating your XMPP account. The error message is: [#{result}]")
      end

      return successful("User successfully created. Welcome!")
    rescue Errno::ECONNREFUSED
      return unsuccessful("The database appears to be down right now. Please contact your cloud administrator.")
    end
  end


  def authenticate!
    conn = DBFrontend.get_instance
    secret = UserTools.get_secret_key
    
    begin
      user_data = conn.get_user_data(self.email, secret)
    rescue Errno::ECONNREFUSED
      return unsuccessful("The database appears to be down right now. Please contact your cloud administrator.")
    rescue Errno::EHOSTUNREACH
      return unsuccessful("The database was unable to be reached. DB Connection to #{DBFrontend.hsoaploc}")
    end
    
    if user_data == "Error: user not found"
      return unsuccessful("Incorrect username / password combination. Please try again.")
    end
    
    server_pwd = user_data.scan(/password:([0-9a-f]+)/).to_s
    client_pwd = UserTools.encrypt_password(self.email, self.password)
    if server_pwd != client_pwd
      return unsuccessful("Incorrect username / password combination. Please try again.")
    end
  
    return successful
  end

  def create_token(email)
    return nil if email.nil?

    conn = DBFrontend.get_instance
    secret = UserTools.get_secret_key

    # next release: use / enforce token_exp
    # token for now contains just email address
    # will later need to contain a list of apps the user is admin on
    token = "#{self.email}"
    token_exp = User.get_token_expiration_date
    begin
      token_inserted = conn.commit_new_token(email, token, token_exp, secret)
    rescue Errno::ECONNREFUSED
      return nil
    end
    
    #TODO: we should probably be checking that the token was inserted before returning it --jkupferman
    
    return token
  end

  private
  def unsuccessful message=""
    { :success => false, :message => message }
  end

  def successful message=""
    { :success => true, :message => message }
  end

  def self.get_token_expiration_date
    # could this be something more sensible like (Time.now + 4.years)? --jkupferman
    "20121231120000"    
  end
end
