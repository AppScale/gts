#!/usr/bin/ruby -w


require 'fileutils'


$:.unshift File.join(File.dirname(__FILE__))
require 'djinn_job_data'
require 'helperfunctions'


# Our implementation of the Google App Engine XMPP and Channel APIs uses the
# open source ejabberd server. This module provides convenience methods to
# start and stop ejabberd, and write its configuration files.
module Ejabberd


  EJABBERD_PATH = File.join("/", "etc", "ejabberd")
  
  
  AUTH_SCRIPT_LOCATION = "#{EJABBERD_PATH}/ejabberd_auth.py"
  
  
  ONLINE_USERS_FILE = "/etc/appscale/online_xmpp_users"


  # We need some additional logic for the start command hence using 
  # a script.
  START_EJABBERD_SCRIPT = File.dirname(__FILE__) + "/../" + \
                          "/scripts/start_ejabberd.sh"

  def self.start
    start_cmd = "bash #{START_EJABBERD_SCRIPT}"
    stop_cmd = "/etc/init.d/ejabberd stop"
    port = 4369
    GodInterface.start(:ejabberd, start_cmd, stop_cmd, port)
  end

  def self.stop
    GodInterface.stop(:ejabberd)
  end

  def self.clear_online_users
    Djinn.log_run("rm #{ONLINE_USERS_FILE}")
  end

  def self.does_app_need_receive?(app, runtime)
    if ["python", "python27", "go"].include?(runtime)
      app_yaml_file = "/var/apps/#{app}/app/app.yaml"
      app_yaml = YAML.load_file(app_yaml_file)["inbound_services"]
      if !app_yaml.nil? and app_yaml.include?("xmpp_message")
        return true
      else
        return false
      end
    elsif runtime == "java"
      appengine_web_xml_file = "/var/apps/#{app}/app/war/WEB-INF/appengine-web.xml"
      xml_contents = HelperFunctions.read_file(appengine_web_xml_file)
      if xml_contents =~ /<inbound-services>.*<service>xmpp.*<\/inbound-services>/
        return true
      else
        return false
      end
    else
      abort("xmpp: runtime was neither python, python27, go, java but was [#{runtime}]")
    end
  end

  def self.write_online_users_list(nodes)
    online_users = `ejabberdctl connected-users`
    HelperFunctions.write_file(ONLINE_USERS_FILE, online_users)

    return if nodes.nil?
    nodes.each { |node|
      next if node.is_login? # don't copy the file to itself
      ip = node.private_ip
      ssh_key = node.ssh_key
      HelperFunctions.scp_file(ONLINE_USERS_FILE, ONLINE_USERS_FILE, ip, ssh_key)
    }
  end

  def self.write_auth_script(login_ip, uaserver_ip, secret)
    auth_script = <<SCRIPT
#!/usr/bin/python

import sys, logging, struct, hashlib, re, SOAPpy, socket, time
from struct import *

# logging initialization

sys.stderr = open("/var/log/ejabberd/extauth_err.log", 'a')
logging.basicConfig(level=logging.INFO,
  format='%(asctime)s %(levelname)s %(message)s',
  filename='/var/log/ejabberd/extauth.log',
  filemode='a')

logging.info("extauth script started, waiting for ejabberd requests")

# db initialization

login_ip = "#{login_ip}"
uaserver_ip = "#{uaserver_ip}"
secret = "#{secret}"

uaserver_address = "https://" + uaserver_ip + ":4343"
server = SOAPpy.SOAPProxy(uaserver_address)

# helper functions

class EjabberdInputError(Exception):
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return repr(self.value)

def ejabberd_in():
  logging.debug("trying to read 2 bytes from ejabberd:")
  try:
    input_length = sys.stdin.read(2)
  except IOError:
    logging.debug("ioerror")

  if len(input_length) is not 2:
    logging.debug("ejabberd sent us wrong things!")
    raise EjabberdInputError('Wrong input from ejabberd!')

  logging.debug('got 2 bytes via stdin: %s'%input_length)
  (size,) = unpack('>h', input_length)

  logging.debug('size of data: %i'%size)
  income = sys.stdin.read(size).split(':')

  logging.debug("incoming data: %s"%income)
  return income

def ejabberd_out(bool):
  logging.debug("Ejabberd gets: %s" % bool)
  token = genanswer(bool)
  logging.debug("sent bytes: %#x %#x %#x %#x" % (ord(token[0]), ord(token[1]), ord(token[2]), ord(token[3])))
  sys.stdout.write(token)
  sys.stdout.flush()

def genanswer(bool):
  answer = 0
  if bool:
    answer = 1

  token = pack('>hh', 2, answer)
  return token

def isuser(in_user, in_host):
  return True
  #username = in_user + "@" + in_host
  #userdata = server.get_user_data(username, secret)

  #if userdata == 'Error: Bad length of user schema vs user result'
  #  return True
  #else:
  #  return False

def auth(in_user, in_host, password):
  #return True
  username = in_user + "@" + in_host

  logging.info("trying to authenticate user [%s]" % (username))

  if not isuser(in_user, in_host):
    return False

  userdata = ""
  while True:
    try:
      userdata = server.get_user_data(username, secret)
      break
    except socket.error:
      time.sleep(1)

  logging.info("userdata for [%s] is [%s]" % (username, str(userdata)))
  matchdata = re.search('password:(.*)', userdata)

  if matchdata is None:
    logging.info("matchdata for [%s] was none" % (username))
    return False

  remote_password = matchdata.group(1)

  salted = username + password
  local_password = hashlib.sha1(salted).hexdigest()

  logging.info("local  password: [%s]" % (local_password))
  logging.info("remote password: [%s]" % (remote_password))

  if local_password == remote_password:
    return True
  else:
    return False

def log_result(op, in_user, bool):
  if bool:
    logging.info("%s successful for %s"%(op, in_user))
  else:
    logging.info("%s unsuccessful for %s"%(op, in_user))

# main loop

while True:
  logging.info("start of infinite loop")
  try: 
    ejab_request = ejabberd_in()
  except EjabberdInputError, inst:
    logging.info("Exception occurred: %s", inst)
    break

  logging.debug('operation: %s'%(ejab_request[0]))
  op_result = False

  if ejab_request[0] == "auth":
    op_result = auth(ejab_request[1], ejab_request[2], ejab_request[3])
    ejabberd_out(op_result)
    log_result(ejab_request[0], ejab_request[1], op_result)
  elif ejab_request[0] == "isuser":
    op_result = isuser(ejab_request[1], ejab_request[2])
    ejabberd_out(op_result)
    log_result(ejab_request[0], ejab_request[1], op_result)
  elif ejab_request[0] == "setpass":
    op_result=False
    ejabberd_out(op_result)
    log_result(ejab_request[0], ejab_request[1], op_result)

logging.info("extauth script terminating")

SCRIPT

    HelperFunctions.write_file(AUTH_SCRIPT_LOCATION, auth_script)
    Djinn.log_run("chown ejabberd #{AUTH_SCRIPT_LOCATION}")
    Djinn.log_run("chmod +x #{AUTH_SCRIPT_LOCATION}")
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
			starttls, {certfile, "/etc/ejabberd/ejabberd.pem"}
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
{s2s_certfile, "/etc/ejabberd/ejabberd.pem"}.

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
  {mod_ctlextra, []},
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
