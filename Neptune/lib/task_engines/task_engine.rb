# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..", "..")
require 'neptune_manager'


class TaskEngine
  def initialize(credentials)
    raise NotImplementedError
  end


  def push(job_data)
    dir = nil
    uploaded_app = false

    if app_needs_uploading?(job_data)
      dir = NeptuneManager.create_temp_dir()
      NeptuneManager.copy_code_to_dir(job_data, dir)
      app_location = build_app_via_oration(job_data, dir)
      upload_app(job_data, app_location)
      uploaded_app = true
    end

    job_data['@host'] = get_app_url(job_data)
    start_time = Time.now.to_f
    task_id = run_task(job_data)
    wait_for_task_to_finish(job_data, task_id)
    end_time = Time.now.to_f
    output = save_output_to_local_fs(job_data)
    nothing = "/tmp/baz"
    HelperFunctions.write_file(nothing, "")
    add_metadata_to_job(job_data, start_time, end_time)
    NeptuneManager.write_babel_outputs(output, nothing, job_data)

    if uploaded_app
      NeptuneManager.cleanup(dir)
    end
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
    HelperFunctions.shell("oration --file #{file} --function #{@function} " +
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


  def save_output_to_local_fs(job_data)
    NeptuneManager.log("copying output from #{engine_name()} to remote datastore")
   
    host = job_data['@host']
    output_location = job_data['@output']
    output = NeptuneManager.get_output(host, output_location)

    NeptuneManager.log("got output from #{engine_name()} app at [#{host}], " +
      "stored at [#{output_location}], storing to remote datastore")
    
    local_output = "/tmp/babel-#{rand()}.txt"
    HelperFunctions.write_file(local_output, output)
    NeptuneManager.save_output(output_location, local_output, job_data)
    return local_output
  end


  def add_metadata_to_job(job_data, start_time, end_time)
    NeptuneManager.log("Adding metadata to job data")
    job_data['@metadata_info']['start_time'] = start_time
    job_data['@metadata_info']['end_time'] = end_time
    total = end_time - start_time
    job_data['@metadata_info']['total_execution_time'] = total
    NeptuneManager.log("Done adding metadata to job data")
  end


  def to_s()
    return "Engine type: #{engine_name()}"
  end

  
  def engine_name()
    raise NotImplementedError
  end
end
