# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..", "..")
require 'neptune_manager'


class TaskEngine
  def initialize(credentials)
    raise NotImplementedError
  end


  def push(job_data)
    dir = NeptuneManager.create_temp_dir()
    NeptuneManager.copy_code_to_dir(job_data, dir)

    if app_needs_uploading?(job_data)
      app_location = build_app_via_oration(job_data, dir)
      upload_app(job_data, app_location)
    end

    job_data['@host'] = get_app_url(job_data)
    task_id = run_task(job_data)
    wait_for_task_to_finish(job_data, task_id)
    save_output_to_datastore(job_data)
    NeptuneManager.cleanup(dir)
  end


  def app_needs_uploading?(job_data)
    raise NotImplementedError
  end


  def build_app_via_oration(job_data, dir)
    NeptuneManager.log("building app via oration")
    NeptuneManager.log("job data is #{job_data.inspect}")
    file = job_data['@code']
    output = dir + "/appengine-app"

    # TODO(cgb) - definitely check the return val here
    NeptuneManager.log_run("oration --file #{file} --function #{@function} " +
      "--appid #{@appid} --output #{output}")
    return output
  end


  def upload_app(job_data, app_location)
    raise NotImplementedError
  end


  def get_app_url(job_data)
    raise NotImplementedError
  end


  def run_task(job_data)
    NeptuneManager.log("running a task in #{engine_name()}")
    host = job_data['@host']

    if job_data['@argv'].nil? or job_data['@argv'].empty?
      inputs = []
    else
      inputs = job_data['@argv']
    end

    return NeptuneManager.execute_task(host, job_data['@function'], inputs, 
      job_data['@output'])
  end


  def wait_for_task_to_finish(job_data, task_id)
    NeptuneManager.log("waiting for #{engine_name()} task to finish")
    host = job_data['@host']
    NeptuneManager.wait_for_task_to_complete(host, task_id)
  end


  def save_output_to_datastore(job_data)
    NeptuneManager.log("copying output from #{engine_name()} to remote datastore")
   
    host = job_data['@host']
    output_location = job_data['@output']
    output = NeptuneManager.get_output(host, output_location)

    NeptuneManager.log("got output from #{engine_name()} app at [#{host}], " +
      "stored at [#{output_location}], storing to remote datastore")
    
    local_output = "/tmp/babel-#{rand()}.txt"
    HelperFunctions.write_file(local_output, output)
    NeptuneManager.save_output(output_location, local_output, job_data)

    return if DEBUG
    NeptuneManager.log("cleaning up local output at #{local_output}")
    FileUtils.rm_f(local_output)
  end


  def to_s()
    return "Engine type: #{engine_name()}"
  end

  
  def engine_name()
    raise NotImplementedError
  end
end
