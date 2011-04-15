#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#




"""A fast but lossy, totally generic object formatter."""


import types



EASY_TYPES = (type(None), int, long, float, bool)
META_TYPES = (type, types.ClassType)
STRING_TYPES = (str, unicode)
CONTAINER_TYPES = {tuple: ('(', ')'),
                   list: ('[', ']'),
                   dict: ('{', '}'),
                   }
BUILTIN_TYPES = EASY_TYPES + STRING_TYPES + tuple(CONTAINER_TYPES)
INSTANCE_TYPE = types.InstanceType


def format_value(val, limit=100, level=10):
    """Wrapper around _format_value()."""
    return _format_value(val, limit, level)


def _format_value(val, limit, level, len=len, repr=repr):
  """Format an arbitrary value as a compact string.

  This is a variant on Python's built-in repr() function, also
  borrowing some ideas from the repr.py standard library module, but
  tuned for speed even in extreme cases (like very large longs or very
  long strings) and safety (it never invokes user code).

  For structured data types like lists and objects it calls itself
  recursively; recursion is strictly limited by level.

  Python's basic types (numbers, strings, lists, tuples, dicts, bool,
  and None) are represented using their familiar Python notations.
  Objects are represented as ClassName<attr1=val1, attr2=val2, ...>.
  Portions omitted due to the various limits are represented using
  three dots ('...').

  Args:
    val: An arbitrary value.
    limit: Limit on the output length.
    level: Recursion level countdown.
    len, repr: Not arguments; for optimization.

  Returns:
    A str instance.
  """

  if level <= 0:
    return '...'

  typ = type(val)

  if typ in EASY_TYPES:
    if typ is float:
      rep = str(val)
    elif typ is long:
      if val >= 10L**99:
        return '...L'
      elif val <= -10L**98:
        return '-...L'
      else:
        rep = repr(val)
    else:
      rep = repr(val)
    if typ is long and len(rep) > limit:
      n1 = (limit - 3) // 2
      n2 = (limit - 3) - n1
      rep = rep[:n1] + '...' + rep[-n2:]
    return rep

  if typ in META_TYPES:
    return val.__name__

  if typ in STRING_TYPES:
    n1 = (limit - 3) // 2
    n2 = (limit - 3) - n1
    if len(val) > limit:
      head = repr(val[:n1])
      tail = repr(val[-n2:])
      return head[:n1] + '...' + tail[-n2:]
    rep = repr(val)
    if len(rep) <= limit:
      return rep
    return rep[:n1] + '...' + rep[-n2:]

  if typ is types.MethodType:
    if val.im_self is None:
      fmt = '<unbound method %s of %s>'
    else:
      fmt = '<method %s of %s<>>'
    return fmt % (val.__name__, val.im_class.__name__)

  if typ is types.FunctionType:
    nam = val.__name__
    if nam == '<lambda>':
      return nam
    else:
      return '<function %s>' % val.__name__

  if typ is types.BuiltinFunctionType:
    if val.__self__ is not None:
      return '<built-in method %s of %s<>>' % (val.__name__,
                                               val.__self__.__class__.__name__)
    else:
      return '<built-in function %s>' % val.__name__

  if typ is types.ModuleType:
    if hasattr(val, '__file__'):
      return '<module %s>' % val.__name__
    else:
      return '<built-in module %s>' % val.__name__

  if typ is types.CodeType:
    return '<code object %s>' % val.co_name

  dct = getattr(val, '__dict__', None)
  if type(dct) is dict:
    if typ is INSTANCE_TYPE:
      typ = val.__class__
    typnam = typ.__name__
    priv = '_' + typnam + '__'
    buffer = [typnam, '<']
    limit -= len(buffer[0]) + 2
    if len(dct) <= limit//4:
      names = sorted(dct)
    else:
      names = list(dct)
    append = buffer.append
    first = True

    if issubclass(typ, BUILTIN_TYPES):



      for builtin_typ in BUILTIN_TYPES:
        if issubclass(typ, builtin_typ):
          try:
            val = builtin_typ(val)
            assert type(val) is builtin_typ
          except Exception:
            break
          else:
            append(_format_value(val, limit, level-1))
            first = False
            break

    for nam in names:
      if not isinstance(nam, basestring):
        continue
      if first:
        first = False
      else:
        append(', ')
      pnam = nam
      if pnam.startswith(priv):
        pnam = pnam[len(priv)-2:]
      limit -= len(pnam) + 2
      if limit <= 0:
        append('...')
        break
      append(pnam)
      append('=')
      rep = _format_value(dct[nam], limit, level-1)
      limit -= len(rep)
      append(rep)
    append('>')
    return ''.join(buffer)

  how = CONTAINER_TYPES.get(typ)
  if how:
    head, tail = how
    buffer = [head]
    append = buffer.append
    limit -= 2
    series = val
    isdict = typ is dict
    if isdict and len(val) <= limit//4:
      series = sorted(val)
    for elem in series:
      if limit <= 0:
        append('...')
        break
      rep = _format_value(elem, limit, level-1)
      limit -= len(rep) + 2
      append(rep)
      if isdict:
        rep = _format_value(val[elem], limit, level-1)
        limit -= len(rep)
        append(':')
        append(rep)
      append(', ')
    if buffer[-1] == ', ':
      if tail == ')' and len(val) == 1:
        buffer[-1] = ',)'
      else:
        buffer[-1] = tail
    else:
      append(tail)
    return ''.join(buffer)

  if issubclass(typ, BUILTIN_TYPES):



    for builtin_typ in BUILTIN_TYPES:
      if issubclass(typ, builtin_typ):
        try:
          val = builtin_typ(val)
          assert type(val) is builtin_typ
        except Exception:
          break
        else:
          typnam = typ.__name__
          limit -= len(typnam) + 2
          return '%s<%s>' % (typnam, _format_value(val, limit, level-1))

  return typ.__name__ + '<>'
