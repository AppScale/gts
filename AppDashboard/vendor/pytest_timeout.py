"""Timeout for tests to stop hanging testruns

This plugin will dump the stack and terminate the test.  This can be
useful when running tests on a continuous integration server.

If the platform supports SIGALRM this is used to raise an exception in
the test, otherwise os._exit(1) is used.
"""

import os
import signal
import sys
import threading
import traceback

import py
import pytest


HAVE_SIGALRM = hasattr(signal, 'SIGALRM')
if HAVE_SIGALRM:
    DEFAULT_METHOD = 'signal'
else:
    DEFAULT_METHOD = 'thread'
TIMEOUT_DESC = """
Timeout in seconds before dumping the stacks.  Default is 0 which
means no timeout.
""".strip()
METHOD_DESC = """
Timeout mechanism to use.  'signal' uses SIGALRM if available,
'thread' uses a timer thread.  The default is to use 'signal' and fall
back to 'thread'.
""".strip()


@pytest.hookimpl
def pytest_addoption(parser):
    """Add options to control the timeout plugin"""
    group = parser.getgroup(
        'timeout', 'Interrupt test run and dump stacks of all threads after '
        'a test times out')
    group.addoption('--timeout',
                    type='int',
                    help=TIMEOUT_DESC)
    group.addoption('--timeout_method',
                    type='choice',
                    action='store',
                    choices=['signal', 'thread'],
                    help='Depreacted, use --timeout-method')
    group.addoption('--timeout-method',
                    dest='timeout_method',
                    type='choice',
                    action='store',
                    choices=['signal', 'thread'],
                    help=METHOD_DESC)
    parser.addini('timeout', TIMEOUT_DESC)
    parser.addini('timeout_method', METHOD_DESC)


@pytest.hookimpl
def pytest_configure(config):
    # Register the marker so it shows up in --markers output.
    config.addinivalue_line(
        'markers',
        'timeout(timeout, method=None): Set a timeout and timeout method on '
        'just one test item.  The first argument, *timeout*, is the timeout '
        'in seconds while the keyword, *method*, takes the same values as the '
        '--timeout_method option.')


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item):
    timeout_setup(item)
    outcome = yield
    timeout_teardown(item)


@pytest.hookimpl(tryfirst=True)
def pytest_exception_interact(node):
    timeout_teardown(node)


@pytest.hookimpl
def pytest_enter_pdb():
    # Since pdb.set_trace happens outside of any pytest control, we don't have
    # any pytest ``item`` here, so we cannot use timeout_teardown. Thus, we
    # need another way to signify that the timeout should not be performed.
    global SUPPRESS_TIMEOUT
    SUPPRESS_TIMEOUT = True
SUPPRESS_TIMEOUT = False


def timeout_setup(item):
    """Setup up a timeout trigger and handler"""
    timeout, method = get_params(item)
    if timeout is None or timeout <= 0:
        return
    if method == 'signal':
        def handler(signum, frame):
            __tracebackhide__ = True
            timeout_sigalrm(item, timeout)
        def cancel():
            signal.alarm(0)
            signal.signal(signal.SIGALRM, signal.SIG_DFL)
        item.cancel_timeout = cancel
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(timeout)
    elif method == 'thread':
        timer = threading.Timer(timeout, timeout_timer, (item, timeout))
        def cancel():
            timer.cancel()
            timer.join()
        item.cancel_timeout = cancel
        timer.start()


def timeout_teardown(item):
    """Cancel the timeout trigger if it was set"""
    # When skipping is raised from a pytest_runtest_setup function
    # (as is the case when using the pytest.mark.skipif marker) we
    # may be called without our setup counterpart having been
    # called.
    cancel = getattr(item, 'cancel_timeout', None)
    if cancel:
        cancel()


def get_params(item):
    """Return (timeout, method) for an item"""
    timeout = method = None
    if 'timeout' in item.keywords:
        timeout, method = _parse_marker(item.keywords['timeout'])
        timeout = _validate_timeout(timeout, 'marker')
        method = _validate_method(method, 'marker')
    if timeout is None:
        timeout = item.config.getvalue('timeout')
    if timeout is None:
        timeout = _validate_timeout(
            os.environ.get('PYTEST_TIMEOUT'),
            'PYTEST_TIMEOUT environment variable')
    if timeout is None:
        ini = item.config.getini('timeout')
        if ini:
            timeout = _validate_timeout(ini, 'config file')
    if method is None:
        method = item.config.getvalue('timeout_method')
    if method is None:
        ini = item.config.getini('timeout_method')
        if ini:
            method = _validate_method(ini, 'config file')
    if method is None:
        method = DEFAULT_METHOD
    return timeout, method


def _parse_marker(marker):
    """Return (timeout, method) tuple from marker

    Either could be None.  The values are not interpreted, so
    could still be bogus and even the wrong type.
    """
    if not marker.args and not marker.kwargs:
        raise TypeError('Timeout marker must have at least one argument')
    timeout = method = NOTSET = object()
    for kw, val in marker.kwargs.items():
        if kw == 'timeout':
            timeout = val
        elif kw == 'method':
            method = val
        else:
            raise TypeError(
                'Invalid keyword argument for timeout marker: %s' % kw)
    if len(marker.args) >= 1 and timeout is not NOTSET:
        raise TypeError(
            'Multiple values for timeout argument of timeout marker')
    elif len(marker.args) >= 1:
        timeout = marker.args[0]
    if len(marker.args) >= 2 and method is not NOTSET:
        raise TypeError(
            'Multiple values for method argument of timeout marker')
    elif len(marker.args) >= 2:
        method = marker.args[1]
    if len(marker.args) > 2:
        raise TypeError('Too many arguments for timeout marker')
    if timeout is NOTSET:
        timeout = None
    if method is NOTSET:
        method = None
    return timeout, method


def _validate_timeout(timeout, where):
    """Helper for get_params()"""
    if timeout is None:
        return None
    try:
        return int(timeout)
    except ValueError:
        raise ValueError('Invalid timeout %s from %s' % (timeout, where))


def _validate_method(method, where):
    """Helper for get_params()"""
    if method is None:
        return None
    if method not in ['signal', 'thread']:
        raise ValueError('Invalid method %s from %s' % (method, where))
    return method


def timeout_sigalrm(item, timeout):
    """Dump stack of threads and raise an exception

    This will output the stacks of any threads other then the
    current to stderr and then raise an AssertionError, thus
    terminating the test.
    """
    if SUPPRESS_TIMEOUT:
        return
    __tracebackhide__ = True
    nthreads = len(threading.enumerate())
    if nthreads > 1:
        write_title('Timeout', sep='+')
    dump_stacks()
    if nthreads > 1:
        write_title('Timeout', sep='+')
    pytest.fail('Timeout >%ss' % timeout)


def timeout_timer(item, timeout):
    """Dump stack of threads and call os._exit()

    This disables the capturemanager and dumps stdout and stderr.
    Then the stacks are dumped and os._exit(1) is called.
    """
    if SUPPRESS_TIMEOUT:
        return
    try:
        capman = item.config.pluginmanager.getplugin('capturemanager')
        if capman:
            stdout, stderr = capman.suspendcapture(item)
        else:
            stdout, stderr = None, None
        write_title('Timeout', sep='+')
        caplog = item.config.pluginmanager.getplugin('_capturelog')
        if caplog and hasattr(item, 'capturelog_handler'):
            log = item.capturelog_handler.stream.getvalue()
            if log:
                write_title('Captured log')
                write(log)
        if stdout:
            write_title('Captured stdout')
            write(stdout)
        if stderr:
            write_title('Captured stderr')
            write(stderr)
        dump_stacks()
        write_title('Timeout', sep='+')
    except Exception:
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)


def dump_stacks():
    """Dump the stacks of all threads except the current thread"""
    current_ident = threading.current_thread().ident
    for thread_ident, frame in sys._current_frames().items():
        if thread_ident == current_ident:
            continue
        for t in threading.enumerate():
            if t.ident == thread_ident:
                thread_name = t.name
                break
        else:
            thread_name = '<unknown>'
        write_title('Stack of %s (%s)' % (thread_name, thread_ident))
        write(''.join(traceback.format_stack(frame)))


def write_title(title, stream=None, sep='~'):
    """Write a section title

    If *stream* is None sys.stderr will be used, *sep* is used to
    draw the line.
    """
    if stream is None:
        stream = sys.stderr
    width = py.io.get_terminal_width()
    fill = int((width - len(title) - 2) / 2)
    line = ' '.join([sep * fill, title, sep * fill])
    if len(line) < width:
        line += sep * (width - len(line))
    stream.write('\n' + line + '\n')


def write(text, stream=None):
    """Write text to stream

    Pretty stupid really, only here for symetry with .write_title().
    """
    if stream is None:
        stream = sys.stderr
    stream.write(text)
