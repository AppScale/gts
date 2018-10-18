# Early, and incomplete implementation of -04.
#
import re
import urllib

RESERVED = ":/?#[]@!$&'()*+,;="
OPERATOR = "+./;?|!@"
EXPLODE = "*+"
MODIFIER = ":^"
TEMPLATE = re.compile("{([^\}]+)}")

def _tostring(varname, value, explode, operator, safe=""):
  if type(value) == type([]):
    if explode == "+":
      return ",".join([varname + "." + urllib.quote(x, safe) for x in value])
    else:
      return ",".join([urllib.quote(x, safe) for x in value])
  if type(value) == type({}):
    keys = value.keys()
    keys.sort()
    if explode == "+":
      return ",".join([varname + "." + urllib.quote(key, safe) + "," + urllib.quote(value[key], safe) for key in keys])
    else:
      return ",".join([urllib.quote(key, safe) + "," + urllib.quote(value[key], safe) for key in keys])
  else:
    return urllib.quote(value, safe)


def _tostring_path(varname, value, explode, operator, safe=""):
  joiner = operator
  if type(value) == type([]):
    if explode == "+":
      return joiner.join([varname + "." + urllib.quote(x, safe) for x in value])
    elif explode == "*":
      return joiner.join([urllib.quote(x, safe) for x in value])
    else:
      return ",".join([urllib.quote(x, safe) for x in value])
  elif type(value) == type({}):
    keys = value.keys()
    keys.sort()
    if explode == "+":
      return joiner.join([varname + "." + urllib.quote(key, safe) + joiner + urllib.quote(value[key], safe) for key in keys])
    elif explode == "*":
      return joiner.join([urllib.quote(key, safe) + joiner + urllib.quote(value[key], safe) for key in keys])
    else:
      return ",".join([urllib.quote(key, safe) + "," + urllib.quote(value[key], safe) for key in keys])
  else:
    if value:
      return urllib.quote(value, safe)
    else:
      return ""


def _tostring_semi(varname, value, explode, operator, safe=""):
  joiner = operator
  if operator == "?":
    joiner = "&"
  if type(value) == type([]):
    if explode == "+":
      return joiner.join([varname + "=" + urllib.quote(x, safe) for x in value])
    elif explode == "*":
      return joiner.join([urllib.quote(x, safe) for x in value])
    else:
      return ",".join([urllib.quote(x, safe) for x in value])
  elif type(value) == type({}):
    keys = value.keys()
    keys.sort()
    if explode == "+":
      return joiner.join([varname + "." + urllib.quote(key, safe) + "=" + urllib.quote(value[key], safe) for key in keys])
    elif explode == "*":
      return joiner.join([urllib.quote(key, safe) + "=" + urllib.quote(value[key], safe) for key in keys])
    else:
      return ",".join([urllib.quote(key, safe) + "," + urllib.quote(value[key], safe) for key in keys])
  else:
    if value:
      return varname + "=" + urllib.quote(value, safe)
    else:
      return varname 


def _tostring_query(varname, value, explode, operator, safe=""):
  joiner = operator
  if operator == "?":
    joiner = "&"
  if type(value) == type([]):
    if 0 == len(value):
      return ""
    if explode == "+":
      return joiner.join([varname + "=" + urllib.quote(x, safe) for x in value])
    elif explode == "*":
      return joiner.join([urllib.quote(x, safe) for x in value])
    else:
      return varname + "=" + ",".join([urllib.quote(x, safe) for x in value])
  elif type(value) == type({}):
    if 0 == len(value):
      return ""
    keys = value.keys()
    keys.sort()
    if explode == "+":
      return joiner.join([varname + "." + urllib.quote(key, safe) + "=" + urllib.quote(value[key], safe) for key in keys])
    elif explode == "*":
      return joiner.join([urllib.quote(key, safe) + "=" + urllib.quote(value[key], safe) for key in keys])
    else:
      return varname + "=" + ",".join([urllib.quote(key, safe) + "," + urllib.quote(value[key], safe) for key in keys])
  else:
    if value:
      return varname + "=" + urllib.quote(value, safe)
    else:
      return varname 

TOSTRING = {
    "" : _tostring,
    "+": _tostring,
    ";": _tostring_semi,
    "?": _tostring_query,
    "/": _tostring_path,
    ".": _tostring_path,
    }


def expand(template, vars):
  def _sub(match):
    expression = match.group(1)
    operator = ""
    if expression[0] in OPERATOR:
      operator = expression[0] 
      varlist = expression[1:]
    else:
      varlist = expression

    safe = ""
    explode = ""
    if operator == '+':
      safe = RESERVED
    varspecs = varlist.split(",")
    varnames = []
    defaults = {}
    for varspec in varspecs:
      default = None
      if "=" in varspec:
        varname, default = tuple(varspec.split("=", 1))
      else:
        varname = varspec
      if varname[-1] in EXPLODE:
        explode = varname[-1]
        varname = varname[:-1]
      if default:
        defaults[varname] = default
      varnames.append((varname, explode))

    retval = []
    joiner = operator
    prefix = operator
    if operator == "+":
      prefix = ""
      joiner = ","
    if operator == "?":
      joiner = "&"
    if operator == "":
      joiner = ","
    for varname, explode in varnames:
      if varname in vars:
        value = vars[varname]
        #if not value and (type(value) == type({}) or type(value) == type([])) and varname in defaults:
        if not value and value != "" and varname in defaults:
          value = defaults[varname]
      elif varname in defaults:
        value = defaults[varname]
      else:
        continue
      retval.append(TOSTRING[operator](varname, value, explode, operator, safe=safe))
    if "".join(retval):
      return prefix + joiner.join(retval)
    else:
      return ""

  return TEMPLATE.sub(_sub, template)
