# Be sure to restart your server when you modify this file.

# Your secret key for verifying cookie session data integrity.
# If you change this key, all old sessions will become invalid!
# Make sure the secret is at least 30 characters and all random, 
# no regular words or you'll be exposed to dictionary attacks.
ActionController::Base.session = {
  :key         => '_monitr_session',
  :secret      => 'c9032d5263ca5526514c249bbc0df51747604a11286aeea70a60d5e58d6e8b451da00e677d90787c6a4133ab690533b610a4993108ad4339d0833f3015bf224d'
}

# Use the database for sessions instead of the cookie-based default,
# which shouldn't be used to store highly confidential information
# (create the session table with "rake db:sessions:create")
# ActionController::Base.session_store = :active_record_store
