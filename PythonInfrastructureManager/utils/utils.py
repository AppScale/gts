from commands import getoutput
from os.path import abspath
from random import random
from string import digits, letters

__author__ = 'hiranya'

def get_secret(filename = '/etc/appscale/secret.key'):
    return read_file(abspath(filename), chomp = True)

def read_file(location, chomp = True):
    file_handle = open(location, 'r')
    contents = file_handle.read()
    if chomp:
        return contents.rstrip('\n')
    else:
        return contents

def get_random_alphanumeric(length = 10):
    alphabet = digits + letters
    return ''.join(random.choice(alphabet) for i in range(length))

def shell(cmd):
    print cmd
    return getoutput(cmd)

def flatten(list):
    result = []
    for l in list:
        if hasattr(l, '__iter__'):
            result.extend(flatten(l))
        else:
            result.append(l)
    return result

def get_ip_addresses(all_addresses):
    return None

def has_parameter(p, params):
    return params.has_key(p) and params[p] is not None and len(params[p]) > 0
