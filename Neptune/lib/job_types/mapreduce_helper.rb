#!/usr/bin/ruby
# Programmer: Chris Bunch


$:.unshift File.join(File.dirname(__FILE__), "..", "..")
require 'neptune_manager'


$:.unshift File.join(File.dirname(__FILE__), "..", "AppController", "lib")
require 'datastore_factory'


BAD_TABLE_MSG = "The currently running database isn't running Hadoop, so MapReduce jobs cannot be run."


DBS_W_HADOOP = ["hbase", "hypertable"]


APPSCALE_HOME = ENV['APPSCALE_HOME']


NO_OUTPUT = false


class NeptuneManager


  HADOOP_VERSION = "0.20.2-cdh3u3"


  HADOOP_DIR = "#{APPSCALE_HOME}/AppDB/hadoop-#{HADOOP_VERSION}"


  HADOOP_EXECUTABLE = "#{HADOOP_DIR}/bin/hadoop"


  HADOOP_STREAMING_JAR = "#{HADOOP_DIR}/contrib/streaming/" +
    "hadoop-streaming-#{HADOOP_VERSION}.jar"


  def mapreduce_run_job(nodes, jobs, secret)
    return BAD_SECRET_MSG unless valid_secret?(secret)
    NeptuneManager.log("MapReduce - run job")

    job_data = jobs[0]

    Thread.new {
      nodes = nodes.map { |node| DjinnJobData.deserialize(node) }
      NeptuneManager.log("Converted node data is #{nodes}")

      storage = job_data["@storage"]
      datastore = DatastoreFactory.get_datastore(storage, job_data)

      mapreducejar = job_data["@mapreducejar"]
      main = job_data["@main"]

      map = job_data["@map"]
      reduce = job_data["@reduce"]

      input = job_data["@input"]
      output = job_data["@output"]

      NeptuneManager.log("MR: Copying mapper and reducer to all boxes")
      # TODO: get files from shadow first if in cloud

      if mapreducejar
        NeptuneManager.log("need to get mr jar located at #{mapreducejar}")
        mr_file = mapreducejar.split('/')[-1]
        my_mrjar = "/tmp/#{mr_file}"
        datastore.get_output_and_save_to_fs(mapreducejar, my_mrjar)

        nodes.each { |node|
          HelperFunctions.scp_file(my_mrjar, my_mrjar, node.private_ip, node.ssh_key)
        }

        NeptuneManager.log("Copying MapReduce jar to db_master node")
        db_master = get_node_with_role("db_master")
        ip = db_master.private_ip
        ssh_key = db_master.ssh_key
        HelperFunctions.scp_file(my_mrjar, my_mrjar, ip, ssh_key)

        run_mr_command = "#{HADOOP_EXECUTABLE} jar #{my_mrjar} #{main} " +
          "#{input} #{output}"
      else
        NeptuneManager.log("Need to get Map code located at #{map}, and " +
          "Reduce code located at #{reduce}")

        map_file = map.split('/')[-1]
        red_file = reduce.split('/')[-1]

        my_map = "/tmp/#{map_file}"
        my_red = "/tmp/#{red_file}"

        FileUtils.rm_rf(my_map)
        FileUtils.rm_rf(my_red)

        datastore.get_single_file_and_save_to_fs(map, my_map)
        datastore.get_single_file_and_save_to_fs(reduce, my_red)

        # since the db master is the initiator of the mapreduce job, it needs
        # to have both the mapper and reducer files handy

        NeptuneManager.log("Copying Mapper and Reducer to db_master node, " +
          "since it runs the MapReduce job")

        db_master = get_node_with_role("db_master")
        ip = db_master.private_ip
        ssh_key = db_master.ssh_key
        HelperFunctions.scp_file(my_map, my_map, ip, ssh_key)
        HelperFunctions.scp_file(my_red, my_red, ip, ssh_key)

        NeptuneManager.log("Copying Mapper and Reducer to all nodes used " +
          "for this MapReduce job")

        nodes.each { |node|
          HelperFunctions.scp_file(my_map, my_map, node.private_ip, node.ssh_key)
          HelperFunctions.scp_file(my_red, my_red, node.private_ip, node.ssh_key)
        }


        map_cmd = "\"" + get_language(my_map) + " " + my_map + "\""
        reduce_cmd = "\"" + get_language(my_red) + " " + my_red + "\""

        run_mr_command = "#{HADOOP_EXECUTABLE} jar #{HADOOP_STREAMING_JAR} " +
          "-input #{input} -output #{output} -mapper #{map_cmd} " +
          "-reducer #{reduce_cmd}"
        NeptuneManager.log("Running MapReduce job, with command " +
          "[#{run_mr_command}]")
      end

      NeptuneManager.log("waiting for input file #{input} to exist in HDFS")
      wait_for_hdfs_file(input)

      # run mr job
      start = Time.now

      NeptuneManager.log("MR: Running job")
      NeptuneManager.log("MR: Command is #{run_mr_command}")
      HelperFunctions.shell(run_mr_command)

      wait_for_hdfs_file(output)
      NeptuneManager.log("MR: Done running job!")

      fin = Time.now
      NeptuneManager.log("TIMING: Total time is #{fin - start} seconds")

      # TODO: check if no part-* files exist - if so, there's an error
      # that we should funnel to the user somehow

      output_cmd = "#{HADOOP_EXECUTABLE} fs -cat #{output}/part-*"
      NeptuneManager.log("MR: Retrieving job output with command #{output_cmd}")
      output_str = HelperFunctions.shell(output_cmd)
      write_job_output_str(job_data, output_str)

      remove_lock_file(job_data)
    }

    return "OK"
  end


  private


  def mapreduce_get_output(job_data)
    output = job_data["@output"]
    output_location = "/tmp/#{output}"

    HelperFunctions.shell("rm -rf #{output_location}")
    run_on_db_master("rm -rf #{output_location}") 
    run_on_db_master("#{HADOOP_EXECUTABLE} fs -get #{output} #{output_location}")
    unless my_node.is_db_master?
      NeptuneManager.log("hey by the way output is [#{output}]")

      db_master = get_node_with_role("db_master")
      ip = db_master.public_ip
      ssh_key = db_master.ssh_key

      HelperFunctions.shell("scp -i #{ssh_key} -o StrictHostkeyChecking=no -r #{ip}:#{output_location} #{output_location}")
    end

    return output_location
  end

  def start_mapreduce_master()
    NeptuneManager.log("start mapreduce master - starting up hadoop first")
    #start_db_master
    #start_hadoop_slave
  end

  def start_mapreduce_slave()
    NeptuneManager.log("start mapreduce slave - starting up hadoop first")
    #start_db_slave
    #start_hadoop_slave
  end

  def stop_mapreduce_master()
    NeptuneManager.log("stop mapreduce master - stopping hadoop")
    #stop_db_master
    #stop_hadoop_slave
  end

  def stop_mapreduce_slave()
    NeptuneManager.log("stop mapreduce slave - stopping hadoop")
    #stop_db_slave
    #stop_hadoop_slave
  end

  def wait_for_hdfs_file(location)
    command = "#{HADOOP_EXECUTABLE} fs -ls #{location}"
    db_master = get_node_with_role("db_master")
    ip = db_master.public_ip
    ssh_key = db_master.ssh_key
    loop {
      cmd = "ssh -o StrictHostkeyChecking=no -i #{ssh_key} #{ip} '#{command}'"
      NeptuneManager.log(cmd)
      result = HelperFunctions.shell(cmd)
      NeptuneManager.log("oi: result was [#{result}]")
      break if result.match(/Found/) # this shows up when ls returns files
      sleep(5)
    }
  end

  def get_language(filename)
    return "ruby"
  end

  def run_on_db_master(command)
    db_master = get_node_with_role("db_master")
    ip = db_master.public_ip
    ssh_key = db_master.ssh_key  
    HelperFunctions.run_remote_command(ip, command, ssh_key, NO_OUTPUT) 
  end


end
