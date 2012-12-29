"""Low-level utilities used internally by NDB.

These are not meant for use by code outside NDB.
"""

import logging
import os
import sys
import threading

__all__ = []

DEBUG = True  # Set to False for some speedups


def logging_debug(*args):
  # NOTE: If you want to see debug messages, set the logging level
  # manually to logging.DEBUG - 1; or for tests use -v -v -v (see below).
  if DEBUG and logging.getLogger().level < logging.DEBUG:
    logging.debug(*args)


def wrapping(wrapped):
  # A decorator to decorate a decorator's wrapper.  Following the lead
  # of Twisted and Monocle, this is supposed to make debugging heavily
  # decorated code easier.  We'll see...
  # TODO: Evaluate; so far it hasn't helped, and it has hurt some.
  def wrapping_wrapper(wrapper):
    try:
      wrapper.__wrapped__ = wrapped
      wrapper.__name__ = wrapped.__name__
      wrapper.__doc__ = wrapped.__doc__
      wrapper.__dict__.update(wrapped.__dict__)
    except Exception:
      pass
    return wrapper
  return wrapping_wrapper


# Define a base class for classes that need to be thread-local.
# This is pretty subtle; we want to use threading.local if threading
# is supported, but object if it is not.
if threading.local.__module__ == 'thread':
  logging_debug('Using threading.local')
  threading_local = threading.local
else:
  logging_debug('Not using threading.local')
  threading_local = object


def get_stack(limit=10):
  # Return a list of strings showing where the current frame was called.
  if not DEBUG:
    return ()
  frame = sys._getframe(1)  # Always skip get_stack() itself.
  lines = []
  while len(lines) < limit and frame is not None:
    f_locals = frame.f_locals
    ndb_debug = f_locals.get('__ndb_debug__')
    if ndb_debug != 'SKIP':
      line = frame_info(frame)
      if ndb_debug is not None:
        line += ' # ' + str(ndb_debug)
      lines.append(line)
    frame = frame.f_back
  return lines


def func_info(func, lineno=None):
  if not DEBUG:
    return None
  func = getattr(func, '__wrapped__', func)
  code = getattr(func, 'func_code', None)
  return code_info(code, lineno)


def gen_info(gen):
  if not DEBUG:
    return None
  frame = gen.gi_frame
  if gen.gi_running:
    prefix = 'running generator '
  elif frame:
    if frame.f_lasti < 0:
      prefix = 'initial generator '
    else:
      prefix = 'suspended generator '
  else:
    prefix = 'terminated generator '
  if frame:
    return prefix + frame_info(frame)
  code = getattr(gen, 'gi_code', None)
  if code:
    return prefix + code_info(code)
  return prefix + hex(id(gen))


def frame_info(frame):
  if not DEBUG:
    return None
  return code_info(frame.f_code, frame.f_lineno)


def code_info(code, lineno=None):
  if not DEBUG or not code:
    return ''
  funcname = code.co_name
  # TODO: Be cleverer about stripping filename,
  # e.g. strip based on sys.path.
  filename = os.path.basename(code.co_filename)
  if lineno is None:
    lineno = code.co_firstlineno
  return '%s(%s:%s)' % (funcname, filename, lineno)


def positional(max_pos_args):
  """A decorator to declare that only the first N arguments may be positional.

  Note that for methods, n includes 'self'.
  """
  __ndb_debug__ = 'SKIP'
  def positional_decorator(wrapped):
    if not DEBUG:
      return wrapped
    __ndb_debug__ = 'SKIP'
    @wrapping(wrapped)
    def positional_wrapper(*args, **kwds):
      __ndb_debug__ = 'SKIP'
      if len(args) > max_pos_args:
        plural_s = ''
        if max_pos_args != 1:
          plural_s = 's'
        raise TypeError(
          '%s() takes at most %d positional argument%s (%d given)' %
          (wrapped.__name__, max_pos_args, plural_s, len(args)))
      return wrapped(*args, **kwds)
    return positional_wrapper
  return positional_decorator


def tweak_logging():
  # Hack for running tests with verbose logging.  If there are two or
  # more -v flags, turn on INFO logging; if there are 3 or more, DEBUG.
  # (A single -v just tells unittest.main() to print the name of each
  # test; we don't want to interfere with that.)
  # Also, if there is a -q flag, set DEBUG to False, suppressing more
  # debug info even from warnings.
  q = 0
  v = 0
  for arg in sys.argv[1:]:
    if arg.startswith('-v'):
      v += arg.count('v')
    if arg.startswith('-q'):
      q += arg.count('q')
  if v >= 2:
    level = logging.INFO
    if v >= 3:
      level = logging.DEBUG - 1
    logging.basicConfig(level=level)
  if q > 0:
    global DEBUG
    DEBUG = False


if 'test' in os.path.basename(sys.argv[0]):
  tweak_logging()
