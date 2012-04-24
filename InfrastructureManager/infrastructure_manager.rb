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


  RESERVATION_NOT_FOUND_RESPONSE = {"success" => false, "reason" => 
    "reservation_id not found"}


  RUN_INSTANCES_REQUIRED_PARAMS = %w{credentials group image_id infrastructure 
    instance_type keyname num_vms}
  

  DESCRIBE_INSTANCES_REQUIRED_PARAMS = %w{reservation_id}


  # A Hash of reservations (keyed by reservation ID) that correspond to
  # requests for virtual machines from cloud infrastructures.
  # TODO(cgb): We should probably garbage collect old reservations
  attr_accessor :reservations


  # The shared secret that is used to authenticate remote callers.
  attr_accessor :secret


  def initialize
    @reservations = {}
    @secret = HelperFunctions.get_secret()
  end


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
      "state" => "scheduling",
      "vm_info" => nil
    }

    Thread.new {
      # TODO(cgb): start the VMs
    }

    return {"success" => true, "reservation_id" => reservation_id, 
      "reason" => "none"}
  end


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


  def terminate_instances(parameters, secret)
    if @secret != secret
      return BAD_SECRET_RESPONSE
    end

  end


end
