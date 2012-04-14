#!/usr/bin/python2.4
# $Id: fa0cb7de413daf47d5326583abff1efa6e2eab94 $
#
# Nose program for testing grizzled.config.Configuration

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import google3
from grizzled.config import (Configuration, NoVariableError)
from cStringIO import StringIO
import os
import tempfile
import atexit
import sys

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

CONFIG1 = """
[section1]
foo = bar
bar = ${foo}
bar2 = ${section1:foo}
name = ${program:name}
time = ${program:now}
cwd = ${program:cwd}
"""

CONFIG2 = """
[section1]
foo = bar
bar = ${foo}

[section2]
foo = ${section1:foo}
bar = ${env:SOME_ENV_VAR}
"""

CONFIG_ORDER_TEST = """
[z]
foo = bar
bar = ${foo}

[y]
foo = ${z:foo}
bar = ${z:bar}

[a]
foo = 1
bar = 2

[z2]
foo = ${z:foo}
bar = ${z:bar}
"""

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class TestParser(object):

    def testSubstitute1(self):
        config = Configuration()
        config.readfp(StringIO(CONFIG1))
        assert config.has_section('section1')
        assert not config.has_section('section2')
        assert not config.has_section('foo')
        assert not config.has_section('bar')
        assert not config.has_section('bar2')
        assert config.has_option('section1', 'foo')
        assert config.has_option('section1', 'name')
        assert config.get('section1', 'name') == os.path.basename(sys.argv[0])
        assert config.get('section1', 'cwd') == os.getcwd()
        assert config.has_option('section1', 'bar')
        assert config.has_option('section1', 'bar2')
        assert config.get('section1', 'foo') == 'bar'
        assert config.get('section1', 'bar') == 'bar'
        assert config.get('section1', 'bar2') == 'bar'

    def testSubstitute2(self):
        os.environ['SOME_ENV_VAR'] = 'test_test_test'
        config = Configuration()
        config.readfp(StringIO(CONFIG2))
        assert config.has_section('section1')
        assert config.has_section('section2')
        assert not config.has_section('foo')
        assert not config.has_section('bar')
        assert not config.has_section('bar2')
        assert config.has_option('section1', 'foo')
        assert config.has_option('section1', 'bar')
        assert not config.has_option('section1', 'bar2')
        assert config.has_option('section2', 'foo')
        assert config.has_option('section2', 'bar')
        assert config.get('section1', 'foo') == 'bar'
        assert config.get('section1', 'bar') == 'bar'
        assert config.get('section2', 'foo') == 'bar'
        assert config.get('section2', 'bar') == os.environ['SOME_ENV_VAR']

    def testInclude(self):
        fd, tempPath = tempfile.mkstemp(suffix='.cfg')

        def unlinkTemp(path):
            try:
                os.unlink(path)
            except:
                pass

        atexit.register(unlinkTemp, tempPath)
        fp = os.fdopen(fd, "w")
        print >> fp, '[section3]\nbaz = somevalue\n'
        fp.close()

        s = '%s\n\n%%include "%s"\n' % (CONFIG2, tempPath)

        os.environ['SOME_ENV_VAR'] = 'test_test_test'
        config = Configuration()
        config.readfp(StringIO(s))
        unlinkTemp(tempPath)
        assert config.has_section('section1')
        assert config.has_section('section2')
        assert config.has_section('section3')
        assert not config.has_section('foo')
        assert not config.has_section('bar')
        assert not config.has_section('bar2')
        assert config.has_option('section1', 'foo')
        assert config.has_option('section1', 'bar')
        assert not config.has_option('section1', 'bar2')
        assert config.has_option('section2', 'foo')
        assert config.has_option('section2', 'bar')
        assert config.has_option('section3', 'baz')
        assert config.get('section1', 'foo') == 'bar'
        assert config.get('section1', 'bar') == 'bar'
        assert config.get('section2', 'foo') == 'bar'
        assert config.get('section2', 'bar') == os.environ['SOME_ENV_VAR']
        assert config.get('section3', 'baz') == 'somevalue'

    def testOrdering(self):
        config = Configuration(use_ordered_sections=True)
        config.readfp(StringIO(CONFIG_ORDER_TEST))
        assert config.has_section('a')
        assert config.has_section('y')
        assert config.has_section('z')
        sections = config.sections
        assert len(sections) == 4
        assert sections[0] == 'z'
        assert sections[1] == 'y'
        assert sections[2] == 'a'
        assert sections[3] == 'z2'

    def testBadSubstitution(self):
        cfgString = """
[foo]
var1 = ${bar}
"""
        import sys
        from grizzled.io import AutoFlush
        sys.stdout = AutoFlush(sys.stdout)
        config = Configuration(strict_substitution=False)
        config.readfp(StringIO(cfgString))
        config.write(sys.stdout)

        try:
            var1 = config.get('foo', 'var1', optional=True)
            assert var1 == None, 'Expected empty variable value'
        except:
            raise

        config = Configuration(strict_substitution=True)
        try:
            config.readfp(StringIO(cfgString))
            assert False, 'Expected an exception'
        except NoVariableError:
            pass
        except:
            assert False, 'Unexpected exception'
