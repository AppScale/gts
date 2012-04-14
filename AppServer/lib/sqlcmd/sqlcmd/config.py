#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# $Id: 3146e78057582e96c2d0ea9f276166badd9668fe $

"""
Configuration classes for *sqlcmd*.

COPYRIGHT AND LICENSE

Copyright © 2008 Brian M. Clapper

This is free software, released under the following BSD-like license:

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

2. The end-user documentation included with the redistribution, if any,
   must include the following acknowlegement:

      This product includes software developed by Brian M. Clapper
      (bmc@clapper.org, http://www.clapper.org/bmc/). That software is
      copyright © 2008 Brian M. Clapper.

    Alternately, this acknowlegement may appear in the software itself, if
    and wherever such third-party acknowlegements normally appear.

THIS SOFTWARE IS PROVIDED ``AS IS'' AND ANY EXPRESSED OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
EVENT SHALL BRIAN M. CLAPPER BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

$Id: 3146e78057582e96c2d0ea9f276166badd9668fe $
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import logging
import os
import re
import sys

from grizzled import db, system
from grizzled.config import Configuration

from sqlcmd.exception import *

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['SQLCmdConfig']

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

log = logging.getLogger('sqlcmd.config')

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class DBInstanceConfigItem(object):
    """
    Captures information about a database configuration item read from the
    .sqlcmd file in the user's home directory.
    """
    def __init__(self,
                 section,
                 aliases,
                 host,
                 database,
                 user,
                 password,
                 type,
                 port,
                 on_connect,
                 config_dir):
        self.section = section
        self.aliases = aliases
        self.primary_alias = aliases[0]
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.port = port
        self.db_type = type
        self.on_connect = None

        if on_connect:
            if on_connect[0] == '~':
                on_connect = os.path.expanduser(on_connect)

            if not os.path.isabs(on_connect):
                on_connect = os.path.abspath(os.path.join(config_dir,
                                                          on_connect))
            if not os.access(on_connect, os.R_OK|os.F_OK):
                log.warning('Database "%s": on-connect script "%s" either '
                            'does not exist, is not readable, or is not a '
                            'file.' % (database, on_connect))
                on_connect = None

            self.on_connect = on_connect

    @property
    def db_key(self):
        port = self.port if self.port else ''
        return '%s|%s|%s|%s' %\
               (self.host, self.db_type, self.port, self.database)

    def __hash__(self):
        return self.primary_alias.__hash__()

    def __str__(self):
        return 'host=%s, db=%s, type=%s' %\
               (self.host, self.database, self.db_type)

    def __repr__(self):
        return self.__str__()

class SQLCmdConfig(object):
    """ Data from the .sqlcmd file in the user's home directory"""

    def __init__(self, config_dir):
        self.__config = {}
        self.__config_dir = config_dir
        self.settings = {}

    def total_databases(self):
        return len(self.__config.keys())

    def load_file(self, path):
        self.path = path
        if os.access(path, os.R_OK|os.F_OK):
            cfg = Configuration()
            cfg.read(path)

            handler_table = (
                # section name regex       function
                # --------------------------------------------------
                (re.compile('^db\.'),      self.__config_db),
                (re.compile('^driver\.'),  self.__config_driver),
                (re.compile('^settings$'), self.__set_vars),
            )

            for section in cfg.sections:
                for regex, handler in handler_table:
                    if regex.match(section):
                        handler(cfg, section)

    def __config_db(self, cfg, section):
        primary_name = section[3:] # assumes it starts with 'db.'
        if len(primary_name) == 0:
            raise ConfigurationError('Bad database section name "%s"' % section)

        aliases = cfg.getlist(section, 'aliases', sep=',', optional=True)
        if aliases:
            aliases = [primary_name] + [a.strip() for a in aliases]
        else:
            aliases = []

        host = cfg.get(section, 'host', optional=True)
        port = cfg.get(section, 'port', optional=True)
        db_name = cfg.get(section, 'database')
        user = cfg.get(section, 'user', optional=True)
        password = cfg.get(section, 'password', optional=True)
        db_type = cfg.get(section, 'type')
        on_connect = cfg.get(section, 'onconnect', optional=True)

        aliases += [db_name]
        try:
            cfg_item = DBInstanceConfigItem(section,
                                            aliases,
                                            host,
                                            db_name,
                                            user,
                                            password,
                                            db_type,
                                            port,
                                            on_connect,
                                            self.__config_dir)
        except ValueError, msg:
            raise ConfigurationError(
                  'Configuration section [%s]: %s' % (section, msg)
            )

        for alias in aliases:
            self.__config[alias] = cfg_item

    def __config_driver(self, cfg, section):
        class_name = cfg.get(section, 'class')
        cls = system.class_for_name(class_name)
        name = cfg.get(section, 'name')
        db.add_driver(name, cls)

    def __set_vars(self, cfg, section):
        self.settings_section = section
        for option in cfg.options(section):
            self.settings[option] = cfg.get(section, option)

    def add(self, section, alias, host, port, database, type, user, password):
        try:
            self.__config[alias]
            raise ConfigurationError(
                'Alias "%s" is already in the configuration' % alias
            )

        except KeyError:
            try:
                cfg = DBInstanceConfigItem(section,
                                           [alias],
                                           host,
                                           database,
                                           user,
                                           password,
                                           type,
                                           port,
                                           None,
                                           self.__config_dir)
            except ValueError, msg:
                raise ConfigurationError(
                    'Error in configuration for alias "%s": %s' % (alias, msg)
                )
            self.__config[alias] = cfg

    def get(self, alias):
        return self.__config[alias]

    def get_aliases(self):
        aliases = self.__config.keys()
        aliases.sort()
        return aliases

    def find_match(self, alias):
        try:
            config_item = self.__config[alias]
            # Exact match. Use that one.
        except KeyError:
            # No match. Try to find one or more that come close.
            matches = {}
            for a in self.__config.keys():
                if a.startswith(alias):
                    config_item = self.__config[a]
                    matches[config_item.db_key] = config_item

            total_matches = len(matches)
            if total_matches == 0:
                raise ConfigurationError(
                    'No configuration item for database "%s"' % alias)
            if total_matches > 1:
                raise ConfigurationError(
                    '%d databases match partial alias "%s": %s' %\
                    (total_matches, alias, \
                     ', '.join([cfg.section for cfg in matches.values()]))
                )
            config_item = matches.values()[0]

        return config_item
