# Programmer: Chris Bunch


# Imports for InfrastructureManager libraries
$:.unshift File.join(File.dirname(__FILE__), "lib")
require 'helperfunctions'


# InfrastructureManager provides callers with the ability to acquire and
# release virtual machines from cloud infrastructures without needing to know
# how to interact with them.
class InfrastructureManager

  
  # The port that the InfrastructureManager runs on, by default.
  SERVER_PORT = 17444


  # The response that callers receive if they call any SOAP-exposed method
  # with an invalid secret.
  BAD_SECRET_RESPONSE = {"success" => false, "reason" => "bad secret"}


  # The standard response that will be returned to users calling
  # describe_instances without passing in the reservation ID to inquire about.
  RESERVATION_NOT_FOUND_RESPONSE = {"success" => false, "reason" => 
    "reservation_id not found"}


  # A list of the parameters required to start virtual machines via a cloud
  # infrastructure.
  RUN_INSTANCES_REQUIRED_PARAMS = %w{credentials group image_id infrastructure 
    instance_type keyname num_vms spot}
  

  # A list of the parameters required to query the InfrastructureManager about
  # the state of a run_instances request.
  DESCRIBE_INSTANCES_REQUIRED_PARAMS = %w{reservation_id}


  # A list of the parameters required to terminate machines previously started
  # via run_instances.
  TERMINATE_INSTANCES_REQUIRED_PARAMS = %w{credentials infrastructure 
    instance_ids}


  # A Hash of reservations (keyed by reservation ID) that correspond to
  # requests for virtual machines from cloud infrastructures.
  # TODO(cgb): We should probably garbage collect old reservations.
  attr_accessor :reservations


  # The shared secret that is used to authenticate remote callers.
  attr_accessor :secret


  # Creates a new InfrastructureManager, which keeps track of the reservations
  # made thus far, and reads a shared secret to authenticate callers.
  def initialize
    @reservations = {}
    @secret = HelperFunctions.get_secret()
  end


  # Acquires machines via a cloud infrastructure. As this process could take
  # longer than the timeout for SOAP calls, we return to the user a reservation
  # ID that can be passed to describe_instances to poll for the state of the
  # new machines.
  def run_instances(parameters, secret)
    if @secret != secret
      return BAD_SECRET_RESPONSE
    end

    RUN_INSTANCES_REQUIRED_PARAMS.each { |required_param|
      if parameters[required_param].nil? or parameters[required_param].empty?
        return {"success" => false, "reason" => "no #{required_param}"}
      end
    }

    reservation_id = HelperFunctions.get_random_alphanumeric()

    @reservations[reservation_id] = {
      "success" => true,
      "reason" => "received run request",
      "state" => "pending",
      "vm_info" => nil
    }

    #Thread.new {
      HelperFunctions.set_creds_in_env(parameters['credentials'], "1")
      public_ips, private_ips, ids = HelperFunctions.spawn_vms(parameters)
      @reservations[reservation_id]["state"] = "running"
      @reservations[reservation_id]["vm_info"] = {
        "public_ips" => public_ips,
        "private_ips" => private_ips,
        "instance_ids" => ids
      }
    #}

    return {"success" => true, "reservation_id" => reservation_id, 
      "reason" => "none"}
  end


  # Queries our internal list of reservations to see if the virtual machines
  # corresponding to the given reservation ID have been started up.
  def describe_instances(parameters, secret)
    if @secret != secret
      return BAD_SECRET_RESPONSE
    end

    DESCRIBE_INSTANCES_REQUIRED_PARAMS.each { |required_param|
      if parameters[required_param].nil? or parameters[required_param].empty?
        return {"success" => false, "reason" => "no #{required_param}"}
      end
    }

    reservation_id = parameters["reservation_id"]
    if @reservations[reservation_id].nil?
      return RESERVATION_NOT_FOUND_RESPONSE
    end
  end


  # Uses the credentials given to terminate machines spawned via a cloud
  # infrastructure.
  def terminate_instances(parameters, secret)
    if @secret != secret
      return BAD_SECRET_RESPONSE
    end

    TERMINATE_INSTANCES_REQUIRED_PARAMS.each { |required_param|
      if parameters[required_param].nil? or parameters[required_param].empty?
        return {"success" => false, "reason" => "no #{required_param}"}
      end
    }
  end


end
