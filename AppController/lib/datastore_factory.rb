# Programmer: Chris Bunch


require 'datastore_repo_on_appscale'
require 'datastore_repo_on_app_engine'
require 'datastore_s3'


# DatastoreFactory provides Neptune jobs with a single method that can be used
# to gain access to one of many distributed datastores.
class DatastoreFactory


  # Creates and returns the specified Datastore, with the given credentials.
  def self.get_datastore(name, credentials)
    case name
    when DatastoreS3::NAME
      s3_creds = {:EC2_ACCESS_KEY => credentials['@EC2_ACCESS_KEY'], 
        :EC2_SECRET_KEY => credentials['@EC2_SECRET_KEY'],
        :S3_URL => credentials['@S3_URL']}
      return DatastoreS3.new(s3_creds)
    when DatastoreRepoOnAppEngine::NAME
      return DatastoreRepoOnAppEngine.new(credentials)
    when DatastoreRepoOnAppScale::NAME
      # Since Repo in AppScale is authenticated w / the secret that we
      # can get at anytime, we don't need to give it any credentials.
      return DatastoreRepoOnAppScale.new({})
    else
      raise NotImplementedError
    end
  end


end
