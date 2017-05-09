#!/usr/bin/ruby -w


require 'fileutils'


$:.unshift File.join(File.dirname(__FILE__))
require 'djinn_job_data'
require 'helperfunctions'
require 'monit_interface'


# Our implementation of the Google App Engine XMPP and Channel APIs uses the
# open source ejabberd server. This module provides convenience methods to
# start and stop ejabberd, and write its configuration files.
module Ejabberd


  EJABBERD_PATH = File.join("/", "etc", "ejabberd")
  
  
  AUTH_SCRIPT_LOCATION = "#{EJABBERD_PATH}/ejabberd_auth.py"
  
  
  ONLINE_USERS_FILE = "/etc/appscale/online_xmpp_users"


  def self.start
    service = `which service`.chomp
    start_cmd = "#{service} ejabberd start"
    stop_cmd = "#{service} ejabberd stop"
    pidfile = '/var/run/ejabberd/ejabberd.pid'
    MonitInterface.start_daemon(:ejabberd, start_cmd, stop_cmd, pidfile)
  end

  def self.stop
    MonitInterface.stop(:ejabberd)
  end

  def self.clear_online_users
    Djinn.log_run("rm #{ONLINE_USERS_FILE}")
  end

  def self.does_app_need_receive?(app, runtime)
    if ["python27", "go", "php"].include?(runtime)
      app_yaml_file = "#{HelperFunctions::APPLICATIONS_DIR}/#{app}/app/app.yaml"
      app_yaml = YAML.load_file(app_yaml_file)["inbound_services"]
      if !app_yaml.nil? and app_yaml.include?("xmpp_message")
        return true
      else
        return false
      end
    elsif runtime == "java"
      appengine_web_xml_file = HelperFunctions.get_appengine_web_xml(app)
      xml_contents = HelperFunctions.read_file(appengine_web_xml_file).force_encoding 'utf-8'

      begin
        if xml_contents =~ /<inbound-services>.*<service>xmpp.*<\/inbound-services>/m
          return true
        else
          return false
        end
      rescue => exception
        backtrace = exception.backtrace.join("\n")
        Djinn.log_warn("Exception while parsing xml contents: #{exception.message}. Backtrace: \n#{backtrace}")
        return false
      end
    else
      HelperFunctions.log_and_crash("xmpp: runtime was not " +
        "python27, go, java, php but was [#{runtime}]")
    end
  end

  def self.write_online_users_list(nodes)
    online_users = `ejabberdctl connected-users`
    HelperFunctions.write_file(ONLINE_USERS_FILE, online_users)

    return if nodes.nil?
    nodes.each { |node|
      next if node.is_shadow? # don't copy the file to itself
      ip = node.private_ip
      ssh_key = node.ssh_key
      HelperFunctions.scp_file(ONLINE_USERS_FILE, ONLINE_USERS_FILE, ip, ssh_key)
    }
  end

  def self.write_config_file(my_private_ip)
    config = <<CONFIG
%%%
%%%     Debian ejabberd configuration file
%%%     This config must be in UTF-8 encoding
%%%
%%% The parameters used in this configuration file are explained in more detail
%%% in the ejabberd Installation and Operation Guide.
%%% Please consult the Guide in case of doubts, it is available at
%%% /usr/share/doc/ejabberd/guide.html

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% Options which are set by Debconf and managed by ucf

%% Admin user
{acl, admin, {user, "admin", "#{my_private_ip}"}}.

%% Hostname
{hosts, ["#{my_private_ip}"]}.

{loglevel, 4}.

%%%   ===============
%%%   LISTENING PORTS

%%
%% listen: Which ports will ejabberd listen, which service handles it
%% and what options to start it with.
%%
{listen,
 [
  {5222, ejabberd_c2s, [
			{access, c2s},
			{shaper, c2s_shaper},
			{max_stanza_size, 65536},
			starttls, {certfile, "#{Djinn::APPSCALE_CONFIG_DIR}/ejabberd.pem"}
		       ]},

  {5269, ejabberd_s2s_in, [
			   {shaper, s2s_shaper},
			   {max_stanza_size, 131072}
			  ]},

  {5280, ejabberd_http, [
                         http_bind,
			 http_poll,
			 web_admin
			]}

 ]}.

{s2s_use_starttls, true}.
{s2s_certfile, "#{Djinn::APPSCALE_CONFIG_DIR}/ejabberd.pem"}.

%%%   ==============
%%%   AUTHENTICATION

%% Authentication using external script
%% Make sure the script is executable by ejabberd.
%%
{auth_method, external}.
{extauth_program, "#{AUTH_SCRIPT_LOCATION}"}.

%%%   ===============
%%%   TRAFFIC SHAPERS

%%
%% The "normal" shaper limits traffic speed to 1.000 B/s
%%
{shaper, normal, {maxrate, 1000}}.

%%
%% The "fast" shaper limits traffic speed to 50.000 B/s
%%
{shaper, fast, {maxrate, 50000}}.


%%
%% Local users: don't modify this line.
%%
{acl, local, {user_regexp, ""}}.

%%%   ============
%%%   ACCESS RULES

%% Define the maximum number of time a single user is allowed to connect:
{access, max_user_sessions, [{10, all}]}.

%% This rule allows access only for local users:
{access, local, [{allow, local}]}.

%% Only non-blocked users can use c2s connections:
{access, c2s, [{deny, blocked},
	       {allow, all}]}.

%% For all users except admins used "normal" shaper
{access, c2s_shaper, [{none, admin},
		      {normal, all}]}.

%% For all S2S connections used "fast" shaper
{access, s2s_shaper, [{fast, all}]}.

%% Only admins can send announcement messages:
{access, announce, [{allow, admin}]}.

%% Only admins can use configuration interface:
{access, configure, [{allow, admin}]}.

%% Admins of this server are also admins of MUC service:
{access, muc_admin, [{allow, admin}]}.

%% All users are allowed to use MUC service:
{access, muc, [{allow, all}]}.

%% No username can be registered via in-band registration:
%% To enable in-band registration, replace 'deny' with 'allow'
% (note that if you remove mod_register from modules list then users will not
% be able to change their password as well as register).
% This setting is default because it's more safe.
{access, register, [{deny, all}]}.

%% Everybody can create pubsub nodes
{access, pubsub_createnode, [{allow, all}]}.


%%%   ================
%%%   DEFAULT LANGUAGE

%%
%% language: Default language used for server messages.
%%
{language, "en"}.


%%%   =======
%%%   MODULES

%%
%% Modules enabled in all ejabberd virtual hosts.
%%
{modules,
 [
  {mod_adhoc,    []},
  {mod_announce, [{access, announce}]}, % requires mod_adhoc
  {mod_caps,     []},
  {mod_configure,[]}, % requires mod_adhoc
  {mod_admin_extra, []},
  {mod_disco,    []},
  %%{mod_echo,   [{host, "echo.localhost"}]},
  {mod_irc,      []},
  {mod_last,     []},
  {mod_muc,      [
		  %%{host, "conference.@HOST@"},
		  {access, muc},
		  {access_create, muc},
		  {access_persistent, muc},
		  {access_admin, muc_admin},
		  {max_users, 500}
		 ]},
  %%{mod_muc_log,[]},
  {mod_offline,  []},
  {mod_privacy,  []},
  {mod_private,  []},
  {mod_proxy65,  [
		  {access, local},
		  {shaper, c2s_shaper}
		 ]},
  {mod_pubsub,   [ % requires mod_caps
		  {access_createnode, pubsub_createnode},
		  {plugins, ["default", "pep"]}
		 ]},
  {mod_register, [
		  %%
		  %% After successful registration, the user receives
		  %% a message with this subject and body.
		  %%
		  %%{welcome_message, {"Welcome!",
		  %%		     "Welcome to a Jabber service powered by Debian. "
		  %%		     "For information about Jabber visit "
		  %%		     "http://www.jabber.org"}},
		  %% Replace it with 'none' if you don't want to send such message:
		  {welcome_message, none},

		  %%
		  %% When a user registers, send a notification to
		  %% these Jabber accounts.
		  %%
		  %%{registration_watchers, ["admin1@example.org"]},

		  {access, register}
		 ]},
  {mod_roster,   []},
  %%{mod_service_log,[]},
  %%{mod_shared_roster,[]},
  {mod_stats,    []},
  {mod_time,     []},
  {mod_vcard,    []},
  {mod_version,  []},
  {mod_http_bind,  []}
 ]}.

CONFIG

    config_path = "/etc/ejabberd/ejabberd.cfg"
    HelperFunctions.write_file(config_path, config)
    Djinn.log_run("chown ejabberd #{config_path}")
  end
end
