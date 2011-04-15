# Be sure to restart your server when you modify this file.

# Your secret key for verifying cookie session data integrity.
# If you change this key, all old sessions will become invalid!
# Make sure the secret is at least 30 characters and all random, 
# no regular words or you'll be exposed to dictionary attacks.
ActionController::Base.session = {
  :key         => '_AppLoadBalancerRedo_session',
  :secret      => 'c13737f076eee480bd76084300a0c73c987d6816041592f58e6c39ec1880d84fb15b3029837b2fe2f17cde36664f8efbad002f561502a0728a3056fb61097e18'
}

# Use the database for sessions instead of the cookie-based default,
# which shouldn't be used to store highly confidential information
# (create the session table with "rake db:sessions:create")
# ActionController::Base.session_store = :active_record_store
