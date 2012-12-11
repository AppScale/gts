import pyamf

class Person(object):
    class __amf__:
        static = ('gender', 'dob')

pyamf.register_class(Person, 'com.acme.app.Person')