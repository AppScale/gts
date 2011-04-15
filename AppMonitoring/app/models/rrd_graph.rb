# Some of the methods in this class were based of off the Colored plugin http://www.scopeport.org/colored
class RrdGraph
  # The colors of the lines that are drawn on the graphs
  LINE_COLORS = ["#00FF00", "#92FEF9", "#FFFF00", "#99C7FF", "#FFCC00", "#FF79E1", "#73d216", "#B89AFE", "#FF4848"]

  # The colors used to draw the graph (e.g. background, text)
  GRAPH_COLORS = {
    "SHADEA" => "#777777",
    "SHADEB" => "#444444",
    "FONT" => "#FFFFFF",
    "BACK" => "#555555",
    "CANVAS" => "#555555",
    "GRID" => "#AFAFAF",
    "MGRID" => "#CFCFCF",
    "AXIS" => "#FFFFFF",
    "ARROW" => "#CCCCCC" 
  }

  # Options used when creating the graph
  GRAPH_OPTIONS = { 
    :units => 1000,
    :width => 500,
    :height => 150,
    :time_window => 1.hour
  }

  attr_accessor :name, :machine, :service, :rrd_database, :group

  def initialize(machine_id, service_id, rrd_database_id, group, time_window, options="")
    generate(machine_id, service_id, rrd_database_id, group, time_window, options)
  end

  # Relative param specifies whether the generated path should be relative to the public directory or not
  def image_path relative=false
    head = relative ? GRAPH_IMAGES_FOLDER : GRAPH_IMAGES_PATH
    File.join(head, "#{@name}.png")
  end

  # Returns all of the other rrd databases that are in the same group as the current graph
  def in_group
    self.service.rrd_databases.group(self.group).sort_by(&:name)
  end

  def display_name
    name = @group || @rrd_database.display_name
    machine = self.machine.display_name
    "#{name} @ #{machine}"
  end

  def valid?
    !(@machine.nil? || @service.nil?)
  end

  private
  def get_color(index=0)
    LINE_COLORS[index % LINE_COLORS.length]
  end

  # Generates graph images for the provided params
  def generate(machine_id, service_id, rrd_database_id, group, time_window, options="")
    @machine = Machine.find_by_id(machine_id)
    @service = Service.find_by_id(service_id)

    if @machine.nil? || @service.nil?
      return nil
    end

    @group = group
    if @group.nil?
      # Without a group we just look up the particular rrd database
      @rrd_database = RrdDatabase.find_by_id(rrd_database_id)
      rrd_databases = [@rrd_database]
      @name = [@machine.name, @service.name, @rrd_database.name].join("-")
    else
      # When provided with a group we want everything in that group
      rrd_databases = RrdDatabase.find_all_by_service_id_and_group(service_id, group)
      @name = [@machine.name, @service.name, @group].join("-")
    end
   
    definitions = []
    i = 0
    rrd_databases.each do |rrd|
      base_name = rrd.metric_name.gsub(' ','-')

      rrd.data_sources.each do |ds|
        # Generate a name for the line which is unique. Don't include the data source name if its simply 'value'
        suffix = (ds.name == "value" ? "" : "-#{ds.name}")
        line_name = "#{base_name}#{suffix}"

        color = get_color(i)

        # Draw the main line in the graph using line_name as the label on the graph
        definitions << "DEF:#{line_name}=#{rrd.path}:#{ds.name}:AVERAGE "

        # Add a legend entry for the line
        definitions << "LINE:#{line_name}#{color}:#{line_name} "

        num_spacers = (line_name.length > 15 ? 0 : (15-line_name.length))
        spacer = ' ' * num_spacers
        # Add min/avg/max values to the graph
        definitions << "GPRINT:#{line_name}:MIN:'#{spacer}Min %5.1lf%s' GPRINT:#{line_name}:AVERAGE:'Avg %5.1lf%s' GPRINT:#{line_name}:MAX:'Max %5.1lf%s\\j' 'COMMENT:\\n' "
        i+=1
      end
    end

    start_time = time_window || GRAPH_OPTIONS[:time_window].ago.to_i
    end_time = Time.now.to_i
    graph_options = "--units-length 10 " << options 

    update_image start_time, end_time, definitions, @name, GRAPH_OPTIONS[:width], GRAPH_OPTIONS[:height], GRAPH_COLORS, graph_options
  end

  # Build a PNG graph image out of the RRD.
  def update_image(from, to, lines, title, width, height, colors, options)
    command = RRD_TOOL + " graph #{image_path} --start #{from.to_s} --end #{to.to_s} "

    command << lines.join(" ")

    command << " -t '#{title}' -w #{width} -h #{height} "

    # Build the colors string.
    command << colors.map { |a,c| "-c #{a}#{c} " }.join(" ")

    command << " " << options << " "

    Rails.logger.info(command)

    successful = system(command)

    Rails.logger.error("Graph generation failed!") unless successful
    
    successful
  end
end
