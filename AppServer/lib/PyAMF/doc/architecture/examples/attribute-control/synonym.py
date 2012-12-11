import pyamf

class UserProfile(object):
    class __amf__:
        synonym = {'public': '_public'}

pyamf.register_class(Person, 'com.acme.app.UserProfile')