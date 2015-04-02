require 'rexml/document'
include REXML


# A module that abstracts away interactions with our implementation of the
# Google App Engine Cron API. It lets users write specifications for how
# often URLs in their web app should be accessed, and turns that into
# standard cron jobs.
module CronHelper


  # A String that tells cron not to e-mail anyone about updates.
  NO_EMAIL_CRON = 'MAILTO=\"\"'


  # Reads the cron configuration file for the given application, and converts
  # any YAML or XML-specified cron jobs to standard cron format.
  #
  # Args:
  #   ip: A String that points to the IP address or FQDN where the login node is
  #     running, and thus is the location where cron web requests should be sent
  #     to.
  #   port: An Integer that indicates what port number the given Google App
  #     Engine application runs on, so that we send cron web requests to the
  #     correct application.
  #   lang: A String that indicates if this Google App Engine application's
  #     runtime is Python 2.7, Java, PHP, or Go, which indicates which
  #     cron configuration file to look for.
  #   app: A String that names the appid of this application, used to find the
  #     cron configuration file on the local filesystem.
  def self.update_cron(ip, port, lang, app)
    Djinn.log_debug("saw a cron request with args [#{ip}][#{lang}][#{app}]")
    app_crontab = NO_EMAIL_CRON + "\n"

    if lang == "python27" or lang == "go" or lang == "php"
      cron_file = "/var/apps/#{app}/app/cron.yaml"

      begin
        yaml_file = YAML.load_file(cron_file)
        unless yaml_file:
          clear_app_crontab(app)
          return
        end
      rescue ArgumentError
        Djinn.log_error("Was not able to update cron for app #{app}")
        return
      rescue Errno::ENOENT
        clear_app_crontab(app)
        return
      end

      cron_routes = yaml_file["cron"]
      if cron_routes.nil?
        clear_app_crontab(app)
        return
      end

      cron_routes.each { |item|
        next if item['url'].nil?
        description = item["description"]
        # since url gets put at end of curl, need to ensure it
        # is of the form /baz to prevent malicious urls
        url = item["url"].scan(/\A(\/[\/\d\w]+)/).flatten.to_s
        schedule = item["schedule"]
        timezone = item["timezone"] # will add support later for this
        cron_scheds = convert_schedule_to_cron(schedule, url, ip, port, app)
        cron_scheds.each { |line|
          cron_info = <<CRON
          Description: #{description}
          URL: #{url}
          Schedule: #{schedule}
          Timezone: #{timezone}
          Cron Schedule: #{line}
CRON
          Djinn.log_debug(cron_info)
          app_crontab << line + "\n"
        }
      }

    elsif lang == "java"
      cron_file = "/var/apps/#{app}/app/war/WEB-INF/cron.xml"
      return unless File.exists?(cron_file)
      cron_xml = Document.new(File.new(cron_file)).root
      return if cron_xml.nil?

      cron_xml.each_element('//cron') { |item|
        description = get_from_xml(item, "description")
        # since url gets put at end of curl, need to ensure it
        # is of the form /baz to prevent malicious urls
        url = get_from_xml(item, "url").scan(/\A(\/[\/\d\w]+)/).flatten.to_s
        schedule = get_from_xml(item, "schedule")
        timezone = get_from_xml(item, "timezone") # will add support later for this
        cron_scheds = convert_schedule_to_cron(schedule, url, ip, port, app)
        cron_scheds.each { |line|
          cron_info = <<CRON
          Description: #{description}
          URL: #{url}
          Schedule: #{schedule}
          Timezone: #{timezone}
          Cron Schedule: #{line}
CRON
          Djinn.log_debug(cron_info)
          app_crontab << line + "\n"
        }
      }
    else
      Djinn.log_error("ERROR: lang was neither python27, go, php, nor java but was [#{lang}] (cron)")
    end

    write_app_crontab(app_crontab, app)
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
    Djinn.log_run("rm -f /etc/cron.d/appscale-#{app}")
  end


  private


  # Checks if a crontab line is valid.
  #
  # Args:
  #   line: A String that contains a crontab line.
  # Returns:
  #   A boolean that expresses the validity of the line.
  def self.valid_crontab_line(line)
    crontab_exists = system('crontab -l')
    if crontab_exists
      `crontab -l > crontab.backup`
    end

    `echo "#{line}" > crontab.tmp`
    line_is_valid = system('crontab crontab.tmp')
    `rm crontab.tmp`

    if crontab_exists
      `crontab crontab.backup`
      `rm crontab.backup`
    else
      `crontab -r`
    end

    return line_is_valid
  end


  # Creates or overwrites an app's crontab.
  #
  # Args:
  #   crontab: A String that contains the entirety of the crontab.
  #   app: A String that names the appid of this application.
  def self.write_app_crontab(crontab, app)
    Djinn.log_info("Writing crontab for [#{app}]:\n#{crontab}")
    `echo "#{crontab}" > /etc/cron.d/appscale-#{app}`
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
    return ords
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
    table = { "sunday" => "sun", "monday" => "mon", "tuesday" => "tue",
              "wednesday" => "wed", "thursday" => "thu", "friday" => "fri",
              "saturday" => "sat", "day" => "*" }
    result = []
    day_list = days.split(",")
    day_list.each{ |day|
      result << (table[day] || day)
    }
    return result.join(',')
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
    table = { "january" => "jan", "february" => "feb", "march" => "mar",
              "april" => "apr", "may" => "may", "june" => "jun",
              "july" => "jul", "august" => "aug", "september" => "sep",
              "october" => "oct", "november" => "nov",
              "december" => "dec", "every" => "*" }
    result = []
    month_list = months.split(",")
    month_list.each{ |month|
      result << (table[month] || month)
    }
    return result.join(',')
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
    cron = ""
    splitted = schedule.split

    unless splitted.length == 3 or splitted.length == 5
      Djinn.log_error("bad format, length = #{splitted.length}")
      return ""
    end

    ord = splitted[0]
    days_of_week = splitted[1]
    months_of_year = ""
    time = ""

    if splitted.length == 3
      months_of_year = "every"
      time = splitted[2]
    else
      months_of_year = splitted[3]
      time = splitted[4]
    end

    ord = fix_ords(ord)
    days_of_week = fix_days(days_of_week)
    months_of_year = fix_months(months_of_year)
    hour, min = time.split(":")

    if ord == "every" # simple case
      cron_lines = ["#{min} #{hour} * #{months_of_year} #{days_of_week}"]
    else # complex case, not implemented yet
      Djinn.log_error("Cannot set up cron route with ordinals, as AppScale" +
        " does not support it. Ordinal was: #{ord}")
      return [""]
    end

    return cron_lines
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
    cron_lines = []
    simple_format = schedule.scan(/\Aevery (\d+) (hours|mins|minutes)\Z/)

    if simple_format.length.zero? # not simple format
      cron_lines = convert_messy_format(schedule)
    else # simple format
      num = $1
      time = $2

      if time == "hours"
        cron_lines = ["0 */#{num} * * *"]
      else # must be minutes / mins
        cron_lines = ["*/#{num} * * * *"]
      end
    end

    secret_hash = Digest::SHA1.hexdigest("#{app}/#{HelperFunctions.get_secret}")
    cron_lines.each { |cron|
      cron << " root curl -H \"X-Appengine-Cron:true\" "\
              "-H \"X-AppEngine-Fake-Is-Admin:#{secret_hash}\" -k "\
              "-L http://#{ip}:#{port}#{url} "\
              "2>&1 >> /var/apps/#{app}/log/cron.log"
    }

    valid_cron_lines = []
    cron_lines.each { |line|
      if valid_crontab_line(line)
        valid_cron_lines << line
      else
        Djinn.log_error("Invalid cron line [#{line}] produced for schedule " +
          "[#{schedule}]")
      end
    }

    return valid_cron_lines
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
