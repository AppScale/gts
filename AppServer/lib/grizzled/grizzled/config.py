'''
Introduction
============

Based on the standard Python ``ConfigParser`` module, this module provides an
enhanced configuration parser capabilities. ``Configuration`` is a drop-in
replacement for ``ConfigParser``.

A configuration file is broken into sections, and each section is
introduced by a section name in brackets. For example::

    [main]
    installationDirectory=/usr/local/foo
    programDirectory: /usr/local/foo/programs

    [search]
    searchCommand: find /usr/local/foo -type f -name "*.class"

    [display]
    searchFailedMessage=Search failed, sorry.


Section Name Syntax
===================

A section name can consist of alphabetics, numerics, underscores and
periods. There can be any amount of whitespace before and after the
brackets in a section name; the whitespace is ignored.

Variable Syntax
===============

Each section contains zero or more variable settings.

 - Similar to a Java ``Properties`` file, the variables are specified as
   name/value pairs, separated by an equal sign ("=") or a colon (":").
 - Variable names are case-sensitive and may contain alphabetics, numerics,
   underscores and periods (".").
 - Variable values may contain anything at all. Leading whitespace in the
   value is skipped. The way to include leading whitespace in a value is
   escape the whitespace characters with backslashes.

Variable Substitution
=====================

A variable value can interpolate the values of other variables, using a
variable substitution syntax. The general form of a variable reference is
``${section_name:var_name}``.

  - *section_name* is the name of the section containing the variable to
    substitute; if omitted, it defaults to the current section.
  - *var_name* is the name of the variable to substitute.

Default values
--------------

You can also specify a default value for a variable, using this syntax::

    ${foo?default}
    ${section:foo?default}

That is, the sequence ``?default`` after a variable name specifies the
default value if the variable has no value. (Normally, if a variable has
no value, it is replaced with an empty string.) Defaults can be useful,
for instance, to allow overrides from the environment. The following example
defines a log file directory that defaults to "/tmp", unless environment
variable LOGDIR is set to a non-empty value::

    logDirectory: ${env:LOGDIR?/var/log}

Special section names
---------------------

The section names "env", and "program" are reserved for special
pseudosections.

The ``env`` pseudosection
~~~~~~~~~~~~~~~~~~~~~~~~~

The "env" pseudosection is used to interpolate values from the environment. On
UNIX systems, for instance, ``${env:HOME}`` substitutes home directory of the
current user. On some versions of Windows, ``${env:USERNAME}`` will substitute
the name of the user.

Note: On UNIX systems, environment variable names are typically
case-sensitive; for instance, ``${env:USER}`` and ``${env:user}`` refer to
different environment variables. On Windows systems, environment variable
names are typically case-insensitive; ``${env:USERNAME}`` and
``${env:username}`` are equivalent.

The ``program`` pseudosection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The "program" pseudosection is a placeholder for various special variables
provided by the Configuration class. Those variables are:

``cwd``
    The current working directory. Thus, ``${program:cwd}`` will substitute
    the working directory, using the appropriate system-specific
    file separator (e.g., "/" on Unix, "\\" on Windows).

``name``
    The calling program name. Equivalent to the Python expression
    ``os.path.basename(sys.argv[0])``

``now``
    The current time, formatted using the ``time.strftime()`` format
    ``"%Y-%m-%d %H:%M:%S"`` (e.g., "2008-03-03 16:15:27")

Includes
--------

A special include directive permits inline inclusion of another
configuration file. The include directive takes two forms::

   %include "path"
   %include "URL"

For example::

    %include "/home/bmc/mytools/common.cfg"
    %include "http://configs.example.com/mytools/common.cfg"

The included file may contain any content that is valid for this parser. It
may contain just variable definitions (i.e., the contents of a section,
without the section header), or it may contain a complete configuration
file, with individual sections.

Note: Attempting to include a file from itself, either directly or
indirectly, will cause the parser to throw an exception.

Replacing ``ConfigParser``
==========================

You can use this class anywhere you would use the standard Python
``ConfigParser`` class. Thus, to change a piece of code to use enhanced
configuration, you might change this:

.. python::

    import ConfigParser

    config = ConfigParser.SafeConfigParser()
    config.read(configPath)

to this:

.. python::

    from grizzled.config import Configuration

    config = Configuration()
    config.read(configPath)


Sometimes, however, you have to use an API that expects a path to a
configuration file that can *only* be parsed with the (unenhanced)
``ConfigParser`` class. In that case, you simply use the ``preprocess()``
method:

.. python::

    import logging
    from grizzled import config

    logging.config.fileConfig(config.preprocess(pathToConfig))

That will preprocess the enhanced configuration file, producing a file
that is suitable for parsing by the standard Python ``config`` module.
'''

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import ConfigParser
import logging
import string
import os
import time
import sys
import re

from grizzled.exception import ExceptionWithMessage
from grizzled.collections import OrderedDict

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['Configuration', 'preprocess',
           'NoOptionError', 'NoSectionError', 'NoVariableError']

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

log = logging.getLogger('grizzled.config')
NoOptionError = ConfigParser.NoOptionError
NoSectionError = ConfigParser.NoSectionError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Used with _ConfigDict

SECTION_OPTION_DELIM = r':'

# Section name pattern
SECTION_NAME_PATTERN = r'([_.a-zA-Z][_.a-zA-Z0-9]+)'

# Pattern of an identifier local to a section.
VARIABLE_NAME_PATTERN = r'([_a-zA-Z][_a-zA-Z0-9]+)(\?[^}]+)?'

# Pattern of an identifier matched by our version of string.Template.
# Intended to match:
#
#     ${section:option}         variable 'option' in section 'section'
#     ${section:option?default} variable 'option' in section 'section', default
#                               value 'default'
#     ${option}                 variable 'option' in the current section
#     ${option?default}         variable 'option' in the current section,
#                               default value 'default'
VARIABLE_REF_PATTERN = SECTION_NAME_PATTERN + SECTION_OPTION_DELIM +\
                       VARIABLE_NAME_PATTERN +\
                       r'|' +\
                       VARIABLE_NAME_PATTERN

# Simple variable reference
SIMPLE_VARIABLE_REF_PATTERN = r'\$\{' + VARIABLE_NAME_PATTERN + '\}'

# Special sections
ENV_SECTION = 'env'
PROGRAM_SECTION = 'program'

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class NoVariableError(ExceptionWithMessage):
    """
    Thrown when a configuration file attempts to substitute a nonexistent
    variable, and the ``Configuration`` object was instantiated with
    ``strict_substitution`` set to ``True``.
    """
    pass

class Configuration(ConfigParser.SafeConfigParser):
    """
    Configuration file parser. See the module documentation for details.
    """

    def __init__(self,
                 defaults=None,
                 permit_includes=True,
                 use_ordered_sections=False,
                 strict_substitution=False):
        """
        Construct a new ``Configuration`` object.

        :Parameters:
            defaults : dict
                dictionary of default values
            permit_includes : bool
                whether or not to permit includes
            use_ordered_sections : bool
                whether or not to use an ordered dictionary for the section
                names. If ``True``, then a call to ``sections()`` will return
                the sections in the order they were encountered in the file.
                If ``False``, the order is based on the hash keys for the
                sections' names.
            strict_substitution : bool
                If ``True``, then throw an exception if attempting to
                substitute a non-existent variable. Otherwise, simple
                substitute an empty value.
        """
        ConfigParser.SafeConfigParser.__init__(self, defaults)
        self.__permit_includes = permit_includes
        self.__use_ordered_sections = use_ordered_sections
        self.__strict_substitution = strict_substitution

        if use_ordered_sections:
            self._sections = OrderedDict()

    def defaults(self):
        """
        Returns the instance-wide defaults.

        :rtype:  dict
        :return: the instance-wide defaults, or ``None`` if there aren't any
        """
        return ConfigParser.SafeConfigParser.defaults(self)

    @property
    def sections(self):
        """
        Get the list of available sections, not including ``DEFAULT``. It's
        not really useful to call this method before calling ``read()`` or
        ``readfp()``.
        
        Returns a list of sections.
        """
        return ConfigParser.SafeConfigParser.sections(self)

    def add_section(self, section):
        """
        Add a section named *section* to the instance. If a section by the
        given name already exists, ``DuplicateSectionError`` is raised.

        :Parameters:
            section : str
                name of section to add

        :raise DuplicateSectionError: section already exists
        """
        ConfigParser.SafeConfigParser.add_section(self, section)

    def has_section(self, section):
        """
        Determine whether a section exists in the configuration. Ignores
        the ``DEFAULT`` section.

        :Parameters:
            section : str
                name of section

        :rtype:  bool
        :return: ``True`` if the section exists in the configuration, ``False``
                 if not.
        """
        return ConfigParser.SafeConfigParser.has_section(self, section)

    def options(self, section):
        """
        Get a list of options available in the specified section.

        :Parameters:
            section : str
                name of section

        :rtype:  list
        :return: list of available options. May be empty.

        :raise NoSectionError: no such section
        """
        return ConfigParser.SafeConfigParser.options(self, section)

    def has_option(self, section, option):
        """
        Determine whether a section has a specific option.

        :Parameters:
            section : str
                name of section
            option : str
                name of option to check

        :rtype:  bool
        :return: ``True`` if the section exists in the configuration and
                 has the specified option, ``False`` if not.
        """
        return ConfigParser.SafeConfigParser.has_option(self, section, option)

    def read(self, filenames):
        """
        Attempt to read and parse a list of filenames or URLs, returning a
        list of filenames or URLs which were successfully parsed. If
        *filenames* is a string or Unicode string, it is treated as a single
        filename or URL. If a file or URL named in filenames cannot be opened,
        that file will be ignored. This is designed so that you can specify a
        list of potential configuration file locations (for example, the
        current directory, the user's home directory, and some system-wide
        directory), and all existing configuration files in the list will be
        read. If none of the named files exist, the ``Configuration`` instance
        will contain an empty dataset. An application which requires initial
        values to be loaded from a file should load the required file or files
        using ``readfp()`` before calling ``read()`` for any optional files:

        .. python::

            import Configuration
            import os

            config = Configuration.Configuration()
            config.readfp(open('defaults.cfg'))
            config.read(['site.cfg', os.path.expanduser('~/.myapp.cfg')])

        :Parameters:
            filenames : list or string
                list of file names or URLs, or the string for a single filename
                or URL

        :rtype:  list
        :return: list of successfully parsed filenames or URLs
        """
        if isinstance(filenames, basestring):
            filenames = [filenames]

        newFilenames = []
        for filename in filenames:
            try:
                self.__preprocess(filename, filename)
                newFilenames += [filename]
            except IOError:
                log.exception('Error reading "%s"' % filename)

        return newFilenames

    def readfp(self, fp, filename=None):
        '''
        Read and parse configuration data from a file or file-like object.
        (Only the ``readline()`` moethod is used.)

        :Parameters:
            fp : file
                File-like object with a ``readline()`` method
            filename : str
                Name associated with ``fp``, for error messages. If omitted or
                ``None``, then ``fp.name`` is used. If ``fp`` has no ``name``
                attribute, then ``"<???">`` is used.
        '''
        self.__preprocess(fp, filename)

    def get(self, section, option, optional=False):
        """
        Get an option from a section.

        :Parameters:
            section : str
                name of section
            option : str
                name of option to check
            optional : bool
                ``True`` to return None if the option doesn't exist. ``False``
                to throw an exception if the option doesn't exist.

        :rtype:  str
        :return: the option value

        :raise NoSectionError: no such section
        :raise NoOptionError: no such option in the section
        """
        def do_get(section, option):
            val = ConfigParser.SafeConfigParser.get(self, section, option)
            if len(val.strip()) == 0:
                raise ConfigParser.NoOptionError(option, section)
            return val

        if optional:
            return self.__get_optional(do_get, section, option)
        else:
            return do_get(section, option)

    def getint(self, section, option, optional=False):
        """
        Convenience method that coerces the result of a call to
        ``get()`` to an ``int``.

        :Parameters:
            section : str
                name of section
            option : str
                name of option to check
            optional : bool
                ``True`` to return None if the option doesn't exist. ``False``
                to throw an exception if the option doesn't exist.

        :rtype:  int
        :return: the option value

        :raise NoSectionError: no such section
        :raise NoOptionError: no such option in the section
        """
        def do_get(section, option):
            return ConfigParser.SafeConfigParser.getint(self, section, option)

        if optional:
            return self.__get_optional(do_xget, section, option)
        else:
            return do_get(section, option)

    def getfloat(self, section, option, optional=False):
        """
        Convenience method that coerces the result of a call to ``get()`` to a
        ``float``.

        :Parameters:
            section : str
                name of section
            option : str
                name of option to check
            optional : bool
                ``True`` to return None if the option doesn't exist. ``False``
                to throw an exception if the option doesn't exist.

        :rtype:  float
        :return: the option value

        :raise NoSectionError: no such section
        :raise NoOptionError: no such option in the section
        """
        def do_get(section, option):
            return ConfigParser.SafeConfigParser.getfloat(self, section, option)

        if optional:
            return self.__get_optional(do_get, section, option)
        else:
            return do_get(section, option)

    def getboolean(self, section, option, optional=False):
        '''
        Convenience method that coerces the result of a call to ``get()`` to a
        boolean. Accepted boolean values are "1", "yes", "true", and "on",
        which cause this method to return True, and "0", "no", "false", and
        "off", which cause it to return False. These string values are checked
        in a case-insensitive manner. Any other value will cause it to raise
        ``ValueError``.

        :Parameters:a
            section : str
                name of section
            option : str
                name of option to check
            optional : bool
                ``True`` to return None if the option doesn't exist. ``False``
                to throw an exception if the option doesn't exist.

        :rtype:  bool
        :return: the option value (``True`` or ``False``)

        :raise NoSectionError: no such section
        :raise NoOptionError: no such option in the section
        :raise ValueError: non-boolean value encountered
        '''
        def do_get(section, option):
            return ConfigParser.SafeConfigParser.getboolean(self,
                                                            section,
                                                            option)

        if optional:
            return self.__get_optional(do_get, section, option)
        else:
            return do_get(section, option)

    def getlist(self, section, option, sep=None, optional=False):
        '''
        Convenience method that coerces the result of a call to ``get()`` to a
        list. The value is split using the separator(s) specified by the
        ``sep`` argument. A ``sep`` value of ``None`` uses white space. The
        result is a list of string values.

        :Parameters:
            section : str
                name of section
            option : str
                name of option to check
            sep : str
                list element separator to use. Defaults to white space.
            optional : bool
                ``True`` to return None if the option doesn't exist. ``False``
                to throw an exception if the option doesn't exist.

        :rtype:  bool
        :return: the option value (``True`` or ``False``)

        :raise NoSectionError: no such section
        :raise NoOptionError: no such option in the section
        '''
        def do_get(section, option):
            value = ConfigParser.SafeConfigParser.get(self, section, option)
            return value.split(sep)

        if optional:
            return self.__get_optional(do_get, section, option)
        else:
            return do_get(section, option)

    def get_one_of(self,
                   section,
                   options,
                   optional=False,
                   default=None,
                   value_type=str):
        '''
        Retrieve at most one of a list or set of options from a section. This
        method is useful if there are multiple possible names for a single
        option. For example, suppose you permit either a ``user_name`` or a
        ``login_name`` option, but not both, in a section called
        ``credentials``. You can use the following code to retrieve the
        option value:

        .. python::

            from grizzled.config import Configuration

            config = Configuration()
            config.read('/path/to/config')
            user = config.get_one_of('credentials', ['user_name', 'login_name'])

        If both options exist, ``get_one_of()`` will a ``NoOptionError``. If
        neither option exists, ``get_one_of()`` will throw a ``NoOptionError``
        if ``optional`` is ``False`` and there's no default value; otherwise,
        it will return the default value.

        :Parameters:
            section : str
                name of section
            options : list or set
                list or set of allowable option names
            optional : bool
                ``True`` to return None if the option doesn't exist. ``False``
                to throw an exception if the option doesn't exist.
            default : str
                The default value, if the option does not exist.
            value_type : type
                The type to which to coerce the value. The value is coerced by
                casting.

        :rtype:  str
        :return: the option value, or ``None`` if nonexistent and
                 ``optional`` is ``True``

        :raise NoSectionError: no such section
        :raise NoOptionError: none of the named options are in the section
        '''
        value = None
        if value_type is bool:
            get = self.getboolean
        else:
            get = self.get

        for option in options:
            value = get(section, option, optional=True)
            if value:
                break

        if value is None:
            value = default

        if (value is None) and (not optional):
            raise NoOptionError('Section "%s" must contain exactly one of the '
                                'following options: %s' %
                                (section, ', '.join(list(options))))

        if value is not None:
            if not (value_type in (bool, str)):
                value = eval('%s(%s)' % (value_type.__name__, value))

        return value

    def items(self, section):
        """
        Get all items in a section.

        :Parameters:
            section : str
                name of section

        :rtype:  list
        :return: a list of (*name*, *value*) tuples for each option in
                 in *section*

        :raise NoSectionError: no such section
        """
        return ConfigParser.SafeConfigParser.items(self, section)

    def set(self, section, option, value):
        """
        If the given section exists, set the given option to the specified
        value; otherwise raise ``NoSectionError``.

        :Parameters:
            section : str
                name of section
            option : str
                name of option to check
            value : str
                the value to set

        :raise NoSectionError: no such section
        """
        ConfigParser.SafeConfigParser.set(self, section, option, value)

    def write(self, fileobj):
        """
        Write a representation of the configuration to the specified file-like
        object. This output can be parsed by a future ``read()`` call.

        NOTE: Includes and variable references are ``not`` reconstructed.
        That is, the configuration data is written in *expanded* form.

        :Parameters:
            fileobj : file
                file-like object to which to write the configuration
        """
        ConfigParser.SafeConfigParser.write(self, fileobj)

    def remove_section(self, section):
        """
        Remove a section from the instance. If a section by the given name
        does not exist, ``NoSectionError`` is raised.

        :Parameters:
            section : str
                name of section to remove

        :raise NoSectionError: no such section
        """
        ConfigParser.SafeConfigParser.remove_section(self, section)

    def optionxform(self, option_name):
        """
        Transforms the option name in ``option_name`` as found in an input
        file or as passed in by client code to the form that should be used in
        the internal structures. The default implementation returns a
        lower-case version of ``option_name``; subclasses may override this or
        client code can set an attribute of this name on instances to affect
        this behavior. Setting this to ``str()``, for example, would make
        option names case sensitive.
        """
        return option_name.lower()

    def __get_optional(self, func, section, option):
        try:
            return func(section, option)
        except ConfigParser.NoOptionError:
            return None
        except ConfigParser.NoSectionError:
            return None

    def __preprocess(self, fp, name):

        try:
            fp.name
        except AttributeError:
            try:
                fp.name = name
            except TypeError:
                # Read-only. Oh, well.
                pass
            except AttributeError:
                # Read-only. Oh, well.
                pass

        if self.__permit_includes:
            # Preprocess includes.
            from grizzled.file import includer
            tempFile = includer.preprocess(fp)
            fp = tempFile

        # Parse the resulting file into a local ConfigParser instance.

        parsedConfig = ConfigParser.SafeConfigParser()

        if self.__use_ordered_sections:
            parsedConfig._sections = OrderedDict()

        parsedConfig.optionxform = str
        parsedConfig.read(fp)

        # Process the variable substitutions.

        self.__normalizeVariableReferences(parsedConfig)
        self.__substituteVariables(parsedConfig)

    def __normalizeVariableReferences(self, sourceConfig):
        """
        Convert all section-local variable references (i.e., those that don't
        specify a section) to fully-qualified references. Necessary for
        recursive references to work.
        """
        simpleVarRefRe = re.compile(SIMPLE_VARIABLE_REF_PATTERN)
        for section in sourceConfig.sections():
            for option in sourceConfig.options(section):
                value = sourceConfig.get(section, option, raw=True)
                oldValue = value
                match = simpleVarRefRe.search(value)
                while match:
                    value = value[0:match.start(1)] +\
                            section +\
                            SECTION_OPTION_DELIM +\
                            value[match.start(1):]
                    match = simpleVarRefRe.search(value)

                sourceConfig.set(section, option, value)

    def __substituteVariables(self, sourceConfig):
        mapping = _ConfigDict(sourceConfig, self.__strict_substitution)
        for section in sourceConfig.sections():
            mapping.section = section
            self.add_section(section)
            for option in sourceConfig.options(section):
                value = sourceConfig.get(section, option, raw=True)

                # Repeatedly substitute, to permit recursive references

                previousValue = ''
                while value != previousValue:
                    previousValue = value
                    value = _ConfigTemplate(value).safe_substitute(mapping)

                self.set(section, option, value)

class _ConfigTemplate(string.Template):
    """
    Subclass of string.Template that handles our configuration variable
    reference syntax.
    """
    idpattern = VARIABLE_REF_PATTERN

class _ConfigDict(dict):
    """
    Dictionary that knows how to dereference variables within a parsed config.
    Only used internally.
    """
    idPattern = re.compile(VARIABLE_REF_PATTERN)
    def __init__(self, parsedConfig, strict_substitution):
        self.__config = parsedConfig
        self.__strict_substitution = strict_substitution
        self.section = None

    def __getitem__(self, key):
        try:
            # Match against the ID regular expression. (If the match fails,
            # it's a bug, since we shouldn't be in here unless it does.)

            match = self.idPattern.search(key)
            assert(match)

            # Now, get the value.

            default = None
            if SECTION_OPTION_DELIM in key:
                if match.group(3):
                    default = self.__extract_default(match.group(3))

                section = match.group(1)
                option = match.group(2)
            else:
                section = self.section
                default = None
                option = match.group(3)
                if match.group(4):
                    default = self.__extract_default(match.group(3))

            result = self.__value_from_section(section, option)

        except KeyError:
            result = default

        except ConfigParser.NoSectionError:
            result = default

        except ConfigParser.NoOptionError:
            result = default

        if not result:
            if self.__strict_substitution:
                raise NoVariableError, 'No such variable: "%s"' % key
            else:
                result = ''

        return result

    def __extract_default(self, s):
        default = s
        if default:
            default = default[1:]  # strip leading '?'
            if len(default) == 0:
                default = None

        return default

    def __value_from_program_section(self, option):
        return {
            'cwd'  : os.getcwd(),
            'now'  : time.strftime('%Y-%m-%d %H:%M:%S'),
            'name' : os.path.basename(sys.argv[0])
               }[option]

    def __value_from_section(self, section, option):
        result = None
        if section == 'env':
            result = os.environ[option]
            if len(result) == 0:
                raise KeyError, option

        elif section == 'program':
            result = self.__value_from_program_section(option)

        else:
            result = self.__config.get(section, option)

        return result

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def preprocess(file_or_url, defaults=None):
    """
    This function preprocesses a file or URL for a configuration file,
    processing all includes and substituting all variables. It writes a new
    configuration file to a temporary file (or specified output file). The
    new configuration file can be read by a standard ``ConfigParser``
    object. Thus, this method is useful when you have an extended
    configuration file that must be passed to a function or object that can
    only read a standard ``ConfigParser`` file.

    For example, here's how you might use the Python ``logging`` API with an
    extended configuration file:

    .. python::

        from grizzled.config import Configuration
        import logging

        logging.config.fileConfig(Configuration.preprocess('/path/to/config')

    :Parameters:
        file_or_url :  str
           file or URL to read and preprocess
        defaults : dict
            defaults to pass through to the config parser

    :rtype: string
    :return: Path to a temporary file containing the expanded configuration.
             The file will be deleted when the program exits, though the caller
             is free to delete it sooner.
    """
    import tempfile
    import atexit

    def unlink(path):
        try:
            os.unlink(path)
        except:
            pass

    parser = Configuration(use_ordered_sections=True)
    parser.read(file_or_url)
    fd, path = tempfile.mkstemp(suffix='.cfg')
    atexit.register(unlink, path)
    parser.write(os.fdopen(fd, "w"))
    return path


# ---------------------------------------------------------------------------
# Main program (for testing)
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys

    format = '%(asctime)s %(name)s %(levelname)s %(message)s'
    logging.basicConfig(level=logging.DEBUG, format=format)

    configFile = sys.argv[1]
    config = Configuration()
    config.read(configFile)

    if len(sys.argv) > 2:
        for var in sys.argv[2:]:
            (section, option) = var.split(':')
            val = config.get(section, option, optional=True)
            print '%s=%s' % (var, val)
    else:
        config.write(sys.stdout)
