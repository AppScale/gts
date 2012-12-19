import pyamf

class Person(object):
    class __amf__:
        proxy = ('address',)

pyamf.register_class(Person, 'com.acme.app.Person')