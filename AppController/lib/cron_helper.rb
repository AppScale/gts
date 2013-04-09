require 'rexml/document'
include REXML


# A module that abstracts away interactions with our implementation of the
# Google App Engine Cron API. It lets users write specifications for how
# often URLs in their web app should be accessed, and turns that into
# standard cron jobs.
module CronHelper

  NTP_SYNC_CRON = "*/5 * * * * /root/appscale/ntp.sh"
  NO_EMAIL_CRON = 'MAILTO=\"\"'
  
  def self.update_cron(ip, port, lang, app)
    Djinn.log_debug("saw a cron request with args [#{ip}][#{lang}][#{app}]") 

    if lang == "python" or lang == "python27" or lang == "go"
      cron_file = "/var/apps/#{app}/app/cron.yaml"
      return unless File.exists?(cron_file)
      cron_yaml = YAML.load_file(cron_file)["cron"]
      return if cron_yaml.nil?
      cron_yaml.each { |item|
        description = item["description"]
        # since url gets put at end of curl, need to ensure it
        # is of the form /baz to prevent malicious urls
        url = item["url"].scan(/\A(\/[\/\d\w]+)/).flatten.to_s
        schedule = item["schedule"]
        timezone = item["timezone"] # will add support later for this
        cron_scheds = convert_schedule_to_cron(schedule, url, ip, port, app)
        cron_scheds.each { |line|
        #  cron_info = <<CRON
        #  Description: #{description}
        #  URL: #{url}
        #  Schedule: #{schedule}
        #  TimeZone: #{timezone}
        #  Cron Schedule: #{line}
        #CRON
        #  Djinn.log_debug(cron_info)
          Djinn.log_debug("Adding cron line: [#{line}]")
          add_line_to_crontab(line)
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
        #  cron_info = <<CRON
        #  Description: #{description}
        #  URL: #{url}
        #  Schedule: #{schedule}
        #  TimeZone: #{timezone}
        #  Cron Schedule: #{line}
        #CRON
        #  Djinn.log_debug(cron_info)
          Djinn.log_debug("Adding cron line: [#{line}]")
          add_line_to_crontab(line)
        }
      }
    else
      Djinn.log_debug("ERROR: lang was neither python, go, nor java but was [#{lang}] (cron)")
    end
  end

  def self.clear_crontab
    `crontab -r`
    #After clearing, make sure we still have our time sync job
    self.add_line_to_crontab(NO_EMAIL_CRON)
    self.add_line_to_crontab(NTP_SYNC_CRON)  
  end

  private

  def self.add_line_to_crontab(line)
    `rm crontab.tmp`
    `crontab -l >> crontab.tmp`
    `echo "#{line}" >> crontab.tmp`
    `crontab crontab.tmp`
    `rm crontab.tmp`
  end

  def self.fix_ords(ords)
    # implement this
    return ords
  end

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

  def self.convert_messy_format(schedule)
    cron = ""
    splitted = schedule.split

    unless splitted.length == 3 or splitted.length == 5
      Djinn.log_debug("bad format, length = #{splitted.length}")
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
      Djinn.log_debug("ERROR: not implemented yet (cron)")
      return ""
    end

    return cron_lines
  end

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
      cron << " curl -H \"X-Appengine-Cron:true\" -H \"X-AppEngine-Fake-Is-Admin:#{secret_hash}\" -k -L http://#{ip}:#{port}#{url} 2>&1 >> /var/apps/#{app}/log/cron.log"
    }
  end

  def self.get_from_xml(xml, tag)
    begin
      xml.elements[tag].text
    rescue NoMethodError
      nil
    end
  end

end
