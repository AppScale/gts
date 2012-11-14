"""
A collection of common utility functions which can be used by any
module within the AppScale Infrastructure Manager implementation.
"""

from commands import getoutput
import os
from os.path import abspath
from random import choice
import re
from string import digits, letters
import time
import sys

__author__ = 'hiranya'

def get_secret(filename = '/etc/appscale/secret.key'):
    return read_file(abspath(filename), chomp = True)

def read_file(location, chomp = True):
    """
    Read the specified file and return the contents. Optionally
    the file content could be subjected to a chomp operation
    before returning.

    Arguments:
        location    Location of the file that needs to be read
        chomp       True if the file content needs to be chomped
                    prior to returning. This is an optional parameter
                    and defaults to True.
    """
    file_handle = open(location, 'r')
    contents = file_handle.read()
    file_handle.close()
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

def log(msg):
    print msg
    sys.stdout.flush()

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
    return params.has_key(p) and params[p] is not None

def diff(list1, list2):
    return sorted(set(list1) - set(list2))

def obscure_string(string):
    if string is None or len(string) < 4:
        return string
    last_four = string[-4:]
    obscured = '*' * (len(string) - 4)
    return obscured + last_four

def get_obscured_env(list=None):
    """
    Prints out a list of environment variables currently set in this process'
    runtime along with their values. Any environment variables specified
    in the input 'list' will be obscured for privacy and security reasons.
    """
    if not list: list = []
    env = shell('env')
    for item in list:
        index = env.find(item)
        if index != -1:
            old = env[env.find('=', index) + 1:env.find('\n', index)]
            env = env.replace(old, obscure_string(old))
    return env

def convert_fqdn_to_ip(fqdn):
    ip_regex = re.compile('\d+\.\d+\.\d+\.\d+')
    if ip_regex.match(fqdn) is not None:
        return fqdn

    ip = shell('dig {0} +short'.format(fqdn)).rstrip()
    if not len(ip):
        return None
    else:
        list = ip.split('\n')
        if len(list) > 1:
            print 'Warning: Host name {0} resolved to multiple IPs: {1}'.format(fqdn, ip)
            print 'Using the first address in the list'
        return list[0]

def sleep(seconds):
    time.sleep(seconds)


