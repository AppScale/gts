import logging
import os
import sys

DEBUG = True  # Set to False for some speedups


def wrapping(wrapped):
  # A decorator to decorate a decorator's wrapper.  Following the lead
  # of Twisted and Monocle, this is supposed to make debugging heavily
  # decorated code easier.  We'll see...
  # TODO: Evaluate; so far it hasn't helped (nor hurt).
  def wrapping_wrapper(wrapper):
    wrapper.__name__ = wrapped.__name__
    wrapper.__doc__ = wrapped.__doc__
    wrapper.__dict__.update(wrapped.__dict__)
    return wrapper
  return wrapping_wrapper

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
  code = func.func_code
  return code_info(code, lineno)

def gen_info(gen):
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
  return code_info(frame.f_code, frame.f_lineno)

def code_info(code, lineno=None):
  funcname = code.co_name
  # TODO: Be cleverer about stripping filename,
  # e.g. strip based on sys.path.
  filename = os.path.basename(code.co_filename)
  if lineno is None:
    lineno = code.co_firstlineno
  return '%s(%s:%s)' % (funcname, filename, lineno)

def logging_debug(*args):
  # NOTE: If you want to see debug messages, set the logging level
  # manually to logging.DEBUG - 1; or for tests use -v -v -v (see below).
  if DEBUG and logging.getLogger().level < logging.DEBUG:
    logging.debug(*args)

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
