__author__ = 'hiranya'

from os.path import abspath
from random import random
from string import digits, letters

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
