from commands import getoutput
import os
from os.path import abspath
from random import choice
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

def write_key_file(location, content):
    if type(location) == type(''):
        location = [ location ]
    for l in location:
        path = abspath(l)
        file_handle = open(path, 'w')
        file_handle.write(content)
        file_handle.close()
        os.chmod(path, 0600)

def get_random_alphanumeric(length = 10):
    alphabet = digits + letters
    return ''.join(choice(alphabet) for i in range(length))

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

def has_parameter(p, params):
    return params.has_key(p) and params[p] is not None and len(params[p]) > 0

def diff(list1, list2):
    return sorted(set(list1) - set(list2))

def obscure_string(string):
    if string is None or len(string) < 4:
        return string
    last_four = string[-4:]
    obscured = '*' * (len(string) - 4)
    return obscured + last_four

def get_obscured_env(list=[]):
    """
    Prints out a list of environment variables currently set in this process'
    runtime along with their values. Any environment variables specified
    in the input 'list' will be obscured for privacy and security reasons.
    """
    env = shell('env')
    for item in list:
        index = env.find(item)
        if index != -1:
            old = env[env.find('=', index) + 1:env.find('\n', index)]
            env = env.replace(old, obscure_string(old))
    return env


