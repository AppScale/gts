Copyright 2008 Google Inc.
All rights reserved.

App Engine SDK - Development tools for Google App Engine

CONTENTS
========

   * Installing on Mac OSX
   * Installing on Windows
   * Installing on Linux and other platforms
   * Running the SDK
   * Using the SDK
   * Using the App Engine Launcher


INSTALLING ON Mac OSX
=====================
1) Download and install Python 2.7 from http://www.python.org/download/
2) Download the SDK installer from
https://developers.google.com/appengine/downloads
3) Install the SDK by double-clicking on the GoogleAppEngine.dmg file and
running the installer.


INSTALLING ON WINDOWS
=====================
1) Download and install Python 2.7 from http://www.python.org/download/
2) Download the SDK installer from
https://developers.google.com/appengine/downloads
3) Install the SDK by double-clicking on the GoogleAppEngine.msi file and
running the installer.


INSTALLING ON LINUX AND OTHER PLATFORMS
===============================
1) Download and install Python 2.7 from http://www.python.org/download/
2) Download the SDK zip file from
https://developers.google.com/appengine/downloads
3) Unpack the zip file.


RUNNING THE SDK
=========================
You can run the SDK with the following command:

dev_appserver.py [options] <application root>

Application root must be the path to the application to run in this server.
Must contain a valid app.yaml or app.yml file.

Options:
  --address=ADDRESS, -a ADDRESS
                             Address to which this server should bind. (Default
                             localhost).
  --clear_datastore, -c      Clear the Datastore on startup. (Default false)
  --debug, -d                Use debug logging. (Default false)
  --help, -h                 View this helpful message.
  --port=PORT, -p PORT       Port for the server to run on. (Default 8080)

  --allow_skipped_files      Allow access to files matched by app.yaml's
                             skipped_files (default False)
  --auth_domain              Authorization domain that this app runs in.
                             (Default gmail.com)
  --auto_id_policy=POLICY    Dictate how automatic IDs are assigned by the
                             datastore stub, "sequential" or "scattered".
                             (Default sequential)
  --backends                 Run the dev_appserver with backends support
                             (multiprocess mode).
  --blobstore_path=DIR       Path to directory to use for storing Blobstore
                             file stub data.
  --clear_prospective_search Clear the Prospective Search subscription index
                             (Default false).
  --clear_search_indexes     Clear the Full Text Search indexes (Default false).
  --datastore_path=DS_FILE   Path to file to use for storing Datastore file
                             stub data.
                             (Default /tmp/dev_appserver.datastore)
  --debug_imports            Enables debug logging for module imports, showing
                             search paths used for finding modules and any
                             errors encountered during the import process.
  --default_partition        Default partition to use in the APPLICATION_ID.
                             (Default dev)
  --disable_static_caching   Never allow the browser to cache static files.
                             (Default enable if expiration set in app.yaml)
  --disable_task_running     When supplied, tasks will not be automatically
                             run after submission and must be run manually
                             in the local admin console.
  --enable_sendmail          Enable sendmail when SMTP not configured.
                             (Default false)
  --high_replication         Use the high replication datastore consistency
                             model. (Default false).
  --history_path=PATH        Path to use for storing Datastore history.
                             (Default /tmp/dev_appserver.datastore.history)
  --persist_logs             Enables storage of all request and application
                             logs to enable later access. (Default false).
  --logs_path=LOGS_FILE      Path to use for storing request logs. If this is
                             set, logs will be persisted to the given path. If
                             this is not set and --persist_logs is true, logs
                             are stored in /tmp/dev_appserver.logs.
  --multiprocess_min_port    When running in multiprocess mode, specifies the
                             lowest port value to use when choosing ports. If
                             set to 0, select random ports.
                             (Default 9000)
  --mysql_host=HOSTNAME      MySQL database host that the rdbms API will use.
                             (Default localhost)
  --mysql_port=PORT          MySQL port to connect to.
                             (Default 3306)
  --mysql_user=USER          MySQL user to connect as.
                             (Default '')
  --mysql_password=PASSWORD  MySQL password to use.
                             (Default '')
  --mysql_socket=PATH        MySQL Unix socket file path.
                             (Default '%(mysql_socket)s')
  --require_indexes          Disallows queries that require composite indexes
                             not defined in index.yaml.
  --search_indexes_path=PATH Path to file to use for storing Full Text Search
                             indexes (Default %(search_indexes_path)s).
  --show_mail_body           Log the body of emails in mail stub.
                             (Default false)
  --skip_sdk_update_check    Skip checking for SDK updates. If false, fall back
                             to opt_in setting specified in .appcfg_nag
                             (Default false)
  --smtp_host=HOSTNAME       SMTP host to send test mail to.  Leaving this
                             unset will disable SMTP mail sending.
                             (Default '')
  --smtp_port=PORT           SMTP port to send test mail to.
                             (Default 25)
  --smtp_user=USER           SMTP user to connect as.  Stub will only attempt
                             to login if this field is non-empty.
                             (Default '').
  --smtp_password=PASSWORD   Password for SMTP server.
                             (Default '')
  --task_retry_seconds       How long to wait in seconds before retrying a
                             task after it fails during execution.
                             (Default '30')
  --use_sqlite               Use the new, SQLite based datastore stub.
                             (Default false)
  --port_sqlite_data         Converts the data from the file based datastore
                             stub to the new SQLite stub, one time use only.
                             Requires enough RAM to hold all of the entities.
                             (Default false)
  --[enable|disable]_console Enables/disables the interactive console.
                             (Default enabled if --address is unset,
                              disabled if --address is set)


USING THE SDK
=======================
For instructions on getting started with Google App Engine, please see the
Google App Engine Getting Started Guide

https://developers.google.com/appengine/docs/python/gettingstarted


USING THE APP ENGINE LAUNCHER
=============================
The Windows and Mac OSX Python SDKs include an additional development tool
called the App Engine Launcher.  This tool provides a simple graphical
interface to create projects, run them locally, and deploy them to Google's App
Engine servers. It can be used in place of the dev_appserver and appcfg
command-line tools.

The Windows SDK can optionally install a desktop short-cut during
installation. If you are missing the short-cut, you can find the launcher in
the launcher subdirectory of your App Engine installation. The default
location is
C:\Program Files\Google\google_appengine\launcher\GoogleAppEngineLauncher.exe

In Mac OSX, the Launcher is installed by dragging it out of the .dmg to a
location specified by the user. The Launcher contains the SDK inside of it.
A typical drag-install destination for the Launcher and SDK is
/Applications/GoogleAppEngineLauncher.app
