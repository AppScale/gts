# Methods added to this helper will be available to all templates in the application.
require 'usertools'

module ApplicationHelper
  def is_user_cloud_admin
    return false unless logged_in?
    return false if user_email.nil?
    return UserTools.is_user_cloud_admin?(user_email, UserTools.get_database_location)
  end

  def logged_in?
    return !cookies[:dev_appserver_login].nil?
  end

  def user_email
    return nil if cookies[:dev_appserver_login].nil?

    cookie_val = cookies[:dev_appserver_login]
    tokens = cookie_val.split(":")
    if tokens.length != 4
      # guard against user-crafted cookies
      Rails.logger.info "saw a malformed cookie: [#{cookie_val}] - clearing it out"
      cookies[:dev_appserver_login] = { :value => nil, :domain => UserTools.local_ip, :expires => Time.at(0) }
      return nil
    end

    email, nick, admin, hash = tokens

    return email
  end

  def page_title page_title
    content_for(:page_title) { page_title.to_s }
  end

  def display_flash_messages
    return if flash.empty?
    # if the only flash message is a notice, display a green flash instead of red
    display_id = ((flash.has_key?(:notice) && flash.one?) ? "noticeExplanation" : "errorExplanation")
    content_tag :ul, :id => display_id do
      [:error, :warning, :notice].map do |level|
        content_tag :li, flash[level], :class => "flash #{level}" if flash[level]
      end
    end
  end

  def graph_tag(graph)
    image_tag graph.image_path(true)
  end

  # Creates the html necessary to use the auroramenu
  def sidebar_header content
    [
     content_tag(:a, content_tag(:span, content, :class => "header"), :href => "#"),
     content_tag(:a, nil, { :href => "#", :class => "aurorashow", :style => "display: none;" }),
     content_tag(:a, nil, { :href => "#", :class => "aurorahide", :style => "display: inline;"}),
    ].join("")
  end

  # Provides the intervals that graph data can be viewed at
  # In order to provide more options, simply add them to this hash
  @@duration_hash = {
    "5 Minutes" => 5.minutes, 
    "1 Hour" => 1.hour,
    "6 Hours" => 6.hours,
    "1 Day" => 1.day,
  }.sort_by { |k,v| v }

  def duration_hash
    @@duration_hash
  end
end
