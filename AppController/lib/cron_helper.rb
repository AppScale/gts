require 'digest/sha1'
require 'rexml/document'
require 'uri'

require 'custom_exceptions'
require 'helperfunctions'
require 'zkinterface'

include REXML

# A module that abstracts away interactions with our implementation of the
# Google App Engine Cron API. It lets users write specifications for how
# often URLs in their web app should be accessed, and turns that into
# standard cron jobs.
module CronHelper
  # A String that tells cron not to e-mail anyone about updates.
  NO_EMAIL_CRON = 'MAILTO=""'.freeze

  # Cron.d folder
  CRON_CONFIG_DIR = '/etc/cron.d/'.freeze

  # Application capture regex.
  PROJECT_ID_REGEX = /appscale-(.*)/

  # Reads the cron configuration file for the given application, and converts
  # any YAML or XML-specified cron jobs to standard cron format.
  #
  # Args:
  #   ip: A String that points to the IP address or FQDN where the login node is
  #     running, and thus is the location where cron web requests should be sent
  #     to.
  #   app: A String that names the appid of this application.
  # Raises:
  #   VersionNotFound if a port cannot be found for a cron entry's target.
  def self.update_cron(ip, app)
    app_crontab = NO_EMAIL_CRON + "\n"
    parsing_log = "saw a cron request with args [#{ip}][#{app}]\n"

    begin
      yaml_file = ZKInterface.get_cron_config(app)
    rescue ConfigNotFound
      clear_app_crontab(app)
      return
    end

    cron_routes = yaml_file['cron']
    if cron_routes.nil?
      clear_app_crontab(app)
      return
    end

    # Keep track of ports to minimize ZooKeeper requests.
    ports = {}
    cron_routes.each { |item|
      next if item['url'].nil?
      description = item['description']

      begin
        # Parse URL to prevent malicious code from being appended.
        url = URI.parse(item['url']).to_s
        parsing_log += "Parsed cron URL: #{url}\n"
      rescue URI::InvalidURIError
        Djinn.log_warn("Invalid cron URL: #{item['url']}. Skipping entry.")
        next
      end

      # Determine the port from the target. Use the default service if the
      # target is not defined or does not exist.
      target = item.fetch('target', Djinn::DEFAULT_SERVICE)
      unless ports.key?(target)
        begin
          version_details = ZKInterface.get_version_details(
            app, target, Djinn::DEFAULT_VERSION)
        rescue VersionNotFound
          Djinn.log_warn(
            "Invalid target: #{target}. Using #{Djinn::DEFAULT_SERVICE}.")
          target = Djinn::DEFAULT_SERVICE
          version_details = ZKInterface.get_version_details(
            app, target, Djinn::DEFAULT_VERSION)
        end
        ports[target] = version_details['appscaleExtensions']['httpPort']
      end
      port = ports[target]

      schedule = item['schedule']
      cron_scheds = convert_schedule_to_cron(schedule, url, ip, port, app)
      parsing_log += "Schedule: #{schedule}\n"
      cron_scheds.each { |line|
        cron_info = <<CRON
        Description: #{description}
        URL: #{url}
        Schedule: #{schedule}
        Cron Schedule: #{line}
CRON
        parsing_log += "#{cron_info}\n"
        app_crontab << line + "\n"
      }
    }

    Djinn.log_debug(parsing_log) if write_app_crontab(app_crontab, app)
  end

  # Erases all cron jobs for all applications.
  def self.clear_app_crontabs
    Djinn.log_run('rm -f /etc/cron.d/appscale-*')
  end

  # Erases all cron jobs for application.
  #
  # Args:
  #   app: A String that names the appid of this application.
  def self.clear_app_crontab(app)
    cron_file = "/etc/cron.d/appscale-#{app}"
    Djinn.log_run("rm -f #{cron_file}") if File.exists?(cron_file)
  end

  def self.list_app_crontabs
    dir_app_regex = "appscale-*"
    return Dir.glob(File.join(CRON_CONFIG_DIR, dir_app_regex))
  end

  # Checks if a crontab line is valid.
  #
  # Args:
  #   line: A String that contains a crontab line.
  # Returns:
  #   A boolean that expresses the validity of the line.
  def self.valid_crontab_line(line)
    crontab_exists = system('crontab -l 2> /dev/null')
    `crontab -l > crontab.backup` if crontab_exists

    temp_cron_file = Tempfile.new('crontab')
    temp_cron_file.write(line + "\n")
    temp_cron_file.close
    line_is_valid = system("crontab #{temp_cron_file.path}")
    temp_cron_file.unlink

    if crontab_exists
      `crontab crontab.backup`
      `rm crontab.backup`
    else
      `crontab -r`
    end

    line_is_valid
  end

  # Creates or overwrites an app's crontab.
  #
  # Args:
  #   crontab: A String that contains the entirety of the crontab.
  #   app: A String that names the appid of this application.
  # Returns:
  #   A Boolean indicating if the crontab was written.
  def self.write_app_crontab(crontab, app)
    app_cron_file = "/etc/cron.d/appscale-#{app}"
    current = ''
    current = File.read(app_cron_file) if File.exists?(app_cron_file)
    if current != crontab
      File.open(app_cron_file, 'w') { |file| file.write(crontab) }
      Djinn.log_info("Written crontab for #{app}.")
      Djinn.log_debug("Crontab for #{app}:\n#{crontab}.")
    else
      Djinn.log_debug("No need to write crontab for #{app}.")
      return false
    end

    true
  end

  # Gets an application cron info.
  #
  # Args:
  #   app_name: A String that names the appid of this application.
  def self.get_application_cron_info(app_name)
    etc_crond_filename = "/etc/cron.d/appscale-#{app_name}"
    etc_crond_file = File.exists?(etc_crond_filename) ? File.read(etc_crond_filename) : ''

    begin
      cron_config = ZKInterface.get_cron_config(app_name)
    rescue ConfigNotFound
      cron_config = ''
    end

    { 'etc_crond_file' => etc_crond_file, 'cron_yaml_file' => cron_config }
  end

  # Converts the frequency of how often a Google App Engine cron job should run
  # to a format that cron understands.
  # TODO: This method does not correctly parse ordinals, as the ordinal
  # can result in a drastically different cron line being produced. It works
  # fine if the user specifies "every 1 <time period>", as this is the same as
  # "every <time period>", but not in other cases. The reason why we haven't
  # implemented support for ordinals yet is that they aren't something we've
  # commonly seen in App Engine apps - but fix this if we do run into an app
  # that uses it.
  #
  # Args:
  #   ords: A list of Strings, that specify how frequently a job runs (e.g.,
  #     in "every 2 days", the ordinal is "2".
  # Returns:
  #   ords, since this method isn't actually implemented correctly.
  def self.fix_ords(ords)
    ords
  end

  # Converts the list of days given in either the Google App Engine Python or
  # Java format to a format that cron understands.
  #
  # Args:
  #   days: An Array of Strings, where each String is either the full name of
  #     a day of the week, or the special character 'day', which indicates that
  #     the job should run every single day.
  # Returns:
  #   An Array of Strings, where each String is now in cron format.
  def self.fix_days(days)
    table = { 'sunday' => 'sun', 'monday' => 'mon', 'tuesday' => 'tue',
              'wednesday' => 'wed', 'thursday' => 'thu', 'friday' => 'fri',
              'saturday' => 'sat', 'day' => '*' }
    result = []
    day_list = days.split(',')
    day_list.each { |day|
      result << (table[day] || day)
    }
    result.join(',')
  end

  # Converts the list of months given in either the Google App Engine Python or
  # Java format to a format that cron understands.
  #
  # Args:
  #   days: An Array of Strings, where each String is either the full name of
  #     a month of the year, or the special character 'every', which indicates
  #     that the job should run every single month.
  # Returns:
  #   An Array of Strings, where each String is now in cron format.
  def self.fix_months(months)
    table = { 'january' => 'jan', 'february' => 'feb', 'march' => 'mar',
              'april' => 'apr', 'may' => 'may', 'june' => 'jun',
              'july' => 'jul', 'august' => 'aug', 'september' => 'sep',
              'october' => 'oct', 'november' => 'nov',
              'december' => 'dec', 'every' => '*', 'month' => '*' }
    result = []
    month_list = months.split(',')
    month_list.each { |month|
      result << (table[month] || month)
    }
    result.join(',')
  end

  # Takes a single cron line specified in the Google App Engine cron format
  # and converts it to one or more cron lines in standard cron format.
  # In contrast to the next method, this method is concerned with the 'messy'
  # format, where the user has not specified something like "every X days",
  # but something more messy, like "the 2nd Sunday of November, at 2PM EST".
  #
  # Args:
  #   schedule: A String containing the Google App Engine cron job to run
  #     (e.g., "every 5 minutes").
  # Returns:
  #   An Array of Strings, where each String is part of a cron line in
  #   standard cron format. It cannot be applied to a crontab because it only
  #   specifies the frequency of the job, and not the action to perform.
  def self.convert_messy_format(schedule)
    splitted = schedule.gsub(/[[:space:]]*,[[:space:]]*/, ',').split

    # Only 3, 4, 5 or 7-token schedules are supported.
    # Examples:
    # every day 00:00
    # every monday 09:00
    # 1 of month 00:00
    # every monday of sep,oct,nov 17:00
    # every 5 minutes from 10:00 to 14:00
    unless splitted.length == 3 || splitted.length == 4 || splitted.length == 5 || splitted.length == 7
      Djinn.log_error("bad format, length = #{splitted.length}")
      return ['']
    end

    ord = splitted[0]
    days_of_week = splitted[1]
    day_of_month = '*'

    multiple_cron_entries = false
    crons = []

    if splitted.length == 3
      months_of_year = 'every'
      time = splitted[2]
      hour, min = time.split(":").map(&:to_i)
    elsif splitted.length == 4
      days_of_week = 'day'
      day_of_month = ord
      months_of_year = splitted[2]
      time = splitted[3]
      hour, min = time.split(':').map(&:to_i)
    elsif splitted.length == 5
      months_of_year = splitted[3]
      time = splitted[4]
      hour, min = time.split(":").map(&:to_i)
    else    # schedule length = 7, e.g. every 7 minutes from 10:00 to 14:00
      months_of_year = 'every'
      days_of_week = 'day'

      increment = splitted[1].to_i
      increment_type = splitted[2]

      # Split hour and minute and trim leading zeros.
      # Start time is represented as t1 = h1:m1.
      # End time is represented as t2 = h2:m2.
      h1, m1 = splitted[4].split(':').map(&:to_i)
      h2, m2 = splitted[6].split(':').map(&:to_i)

      if h1 == h2 && m1 == m2   # e.g. every 5 minutes from 12:05 to 12:05
        return []
      elsif increment_type == 'hours'
        if increment > 24       # Invalid increment for this type of schedule.
          return []
        elsif increment == 24   # e.g. every 24 hours from 01:30 to 01:29
          hour = h1
          min = m1
        elsif h1 < h2
          if m1 <= m2   # hours, h1 < h2, m1 <= m2
            hour = "#{h1}-#{h2}/#{increment}"
            min = "#{m1}"
          else          # hours, h1 < h2, m1 > m2
            hour = "#{h1}-#{h2-1}/#{increment}"
            min = "#{m1}"
          end
        elsif h1 >= h2   # hours, h1 >= h2
          multiple_cron_entries = true

          # Batch 1 - before midnight
          hour = "#{h1}-23/#{increment}"
          min = "#{m1}"
          crons.push({"hour" => hour, "min" => min})

          # Batch 2 - after midnight
          remainder = (24 - h1) % increment
          first_hour = (increment-remainder)
          min = "#{m1}"
          if m1 < m2    # hours, h1 >= h2, m1 < m2
            last_hour = h2
          else          # hours, h1 >= h2, m1 >= m2
            last_hour = h2-1
          end

          # If the next occurrence after midnight is past h2,
          # there won't be a batch 2.
          if first_hour < last_hour
            hour = "#{first_hour}-#{last_hour}/#{increment}"
            crons.push({"hour" => hour, "min" => min})
          elsif first_hour == last_hour
            hour = "#{first_hour}"
            crons.push({"hour" => hour, "min" => min})
          end
        end
      else    # increment_type == minutes
        multiple_cron_entries = true
        first_of_hour = m1    # First occurrence of the hour.
        if h1 < h2            # minutes, h1 < h2
          for h in (h1..h2)
            remainder  = (60 - first_of_hour) % increment
            if h == h2
              last_of_hour = m2
            else
              last_of_hour = 60 - remainder
            end

            # Start the next entry at '0' since '60' is not a valid minute.
            if last_of_hour == 60
              last_of_hour = 59
              remainder = increment
            end

            mins = (first_of_hour..last_of_hour).step(increment).to_a.join(',')
            crons.push({"hour" => "#{h}", "min" => mins}) unless mins.empty?
            first_of_hour = increment - remainder
          end
        elsif h1 >= h2        # minutes, h1 >= h2
          [{"fh" => h1, "lh" => 23},   # Batch 1 - before midnight
           {"fh" => 0, "lh" => h2},    # Batch 2 - after midnight
          ].each do |batch|
            for h in (batch["fh"]..batch["lh"])
              remainder = (60 - first_of_hour) % increment
              last_of_hour = 60 - remainder
              if last_of_hour == 60
                last_of_hour = 59
              end
              if batch["fh"] == 0 && h == batch["lh"]
                last_of_hour = m2
              end

              mins = (first_of_hour..last_of_hour).step(increment).to_a.join(',')
              crons.push({"hour" => "#{h}", "min" => mins}) unless mins.empty?

              # Set up next loop.
              first_of_hour = 0   # If no remainder, start at the top.
              if remainder != 0
                first_of_hour = increment - remainder
              end
            end
          end
        end
      end
    end

    ord = fix_ords(ord)
    days_of_week = fix_days(days_of_week)
    months_of_year = fix_months(months_of_year)

    cron_lines = Array.new
    if ord == "every" && !multiple_cron_entries
      cron_lines.push("#{min} #{hour} * #{months_of_year} #{days_of_week}")
    elsif ord == "every" && multiple_cron_entries
      crons.each { |cron|
        cron_lines.push("#{cron["min"]} #{cron["hour"]} * #{months_of_year} #{days_of_week}")
      }
    elsif ord != "every" && !multiple_cron_entries
      cron_lines.push("#{min} #{hour} #{day_of_month} #{months_of_year} #{days_of_week}")
    else    # Complex case, not implemented yet.
      Djinn.log_error("Cannot set up cron route with ordinals, as AppScale" +
        " does not support it. Ordinal was: #{ord}")
      return ['']
    end

    cron_lines
  end

  # Generates one or more cron lines in standard cron format for an interval
  # of the given minutes or hours.
  #
  # Where values do not repeat evenly in a 24 hour period the last run for the
  # day is dropped to avoid a short interval.
  #
  # Args:
  #   num: The interval length.
  #   time: The interval units (mins, minutes, hours)
  # Returns:
  #   An Array of Strings, where each String is a cron line in standard cron
  #   format, that can be applied to a crontab.
  def self.simple_cron_lines(num, time)
    time_in_minutes = num * (time == 'hours' ? 60 : 1)

    if time_in_minutes % 60 == 0 and 1440 % time_in_minutes == 0 and time_in_minutes < 1440
      cron_lines = ["0 */#{time_in_minutes/60} * * *"]
    elsif 60 % time_in_minutes == 0 and time_in_minutes < 60
      cron_lines = ["*/#{time_in_minutes} * * * *"]
    else
      # break into multiple cron entries, one for each minute past the hour
      cron_hours_by_minute_past = {0 => [0]}
      for minute_of_day in (time_in_minutes..(1440-time_in_minutes)).step(time_in_minutes)
        hours_for_minute_past = cron_hours_by_minute_past[minute_of_day % 60] || []
        hours_for_minute_past << (minute_of_day / 60)
        cron_hours_by_minute_past[minute_of_day % 60] = hours_for_minute_past
      end
      # if there are multiple minutes with the same hours collapse them
      cron_minutes_past_by_hours = cron_hours_by_minute_past.map{|min,hours|
        {hours => [min]}
      }.reduce({}){|hash, single_hash| hash.merge(single_hash){|key, v1, v2|
        [].concat(v1).concat(v2).uniq().sort()
      }}
      cron_lines = cron_minutes_past_by_hours.map{|hours,mins|
        "#{mins.join(",")} #{hours.join(",")} * * *"
      }
    end

    cron_lines
  end

  # Takes a single cron line specified in the Google App Engine cron format
  # and converts it to one or more cron lines in standard cron format.
  #
  # Args:
  #   schedule: A String containing the Google App Engine cron job to run
  #     (e.g., "every 5 minutes").
  #   url: A String containing the relative URL that the cron web task should
  #     access (e.g., '/', '/daily-task')
  #   ip: A String that points to the IP address or FQDN where the login node is
  #     running, and thus is the location where cron web requests should be sent
  #     to.
  #   port: An Integer that indicates what port number the given Google App
  #     Engine application runs on, so that we send cron web requests to the
  #     correct application.
  #   app: A String that names the appid of this application, used to log the
  #     result of the cron job on the local filesystem.
  # Returns:
  #   An Array of Strings, where each String is a cron line in standard cron
  #   format, that can be applied to a crontab.
  def self.convert_schedule_to_cron(schedule, url, ip, port, app)
    # "synchronized" is a synonym for "from 00:00 to 23:59" in the Cron API.
    # Therefore, both are handled as simple format.
    simple_format_regex = /\Aevery (\d+) (hours|mins|minutes)(?:\s+from 00:00 to 23:59|\s+synchronized)?\Z/
    simple_format = schedule.scan(simple_format_regex)

    if simple_format.length.zero? &&
       !schedule.include?("from 00:00 to 23:59")    # not simple format
      Djinn.log_debug('Messy format')
      cron_lines = convert_messy_format(schedule)
    else
      Djinn.log_debug("Simple format: #{simple_format}")
      cron_lines = simple_cron_lines($1.to_i, $2)
    end
    Djinn.log_debug(cron_lines)
    Djinn.log_debug('----------------------')

    secret_hash = Digest::SHA1.hexdigest("#{app}/#{HelperFunctions.get_secret}")
    cron_lines.each { |cron|
      cron << ' root curl -sSH "X-Appengine-Cron:true" '\
              "-H \"X-AppEngine-Fake-Is-Admin:#{secret_hash}\" -k "\
              "-L \"http://#{ip}:#{port}#{url}\" "\
              "2>&1 >> /var/log/appscale/cron-#{app}.log"
    }

    valid_cron_lines = []
    cron_lines.each { |line|
      if valid_crontab_line(line)
        valid_cron_lines << line
      else
        error = "Invalid cron line [#{line}] produced for schedule " \
          "[#{schedule}]. Skipping..."
        Djinn.log_error(error)
        Djinn.log_app_error(app, error)
      end
    }

    valid_cron_lines
  end

  # Searches through the given XML for the text associated with the named tag.
  #
  # Args:
  #   xml: The XML document that we should search through.
  #   tag: A String that names the tag whose value we should find.
  # Returns:
  #   A String containing the value of the given tag, or nil if the tag was not
  #   present in the XML.
  def self.get_from_xml(xml, tag)
    begin
      xml.elements[tag].text
    rescue NoMethodError
      nil
    end
  end
end

