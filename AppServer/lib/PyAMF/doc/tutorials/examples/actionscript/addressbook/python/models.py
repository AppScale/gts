# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.


"""
Model classes for the SQLAlchemy Addressbook example.

@since: 0.4.1
"""


class User(object):
    def __init__(self):
        self.first_name = None
        self.last_name = None
        self.emails = []
        self.phone_numbers = []
        self.created = None


class PhoneNumber(object):
    def __init__(self):
        self.label = None
        self.number = None


class Email(object):
    def __init__(self):
        self.label = None
        self.email = None
