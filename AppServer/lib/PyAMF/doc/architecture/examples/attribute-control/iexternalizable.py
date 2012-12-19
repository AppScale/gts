import pyamf

class Person(object):
    class __amf__:
        external = True

    def __writeamf__(self, output):
        # Implement the encoding here
        pass

    def __readamf__(self, input):
        # Implement the decoding here
        pass

pyamf.register_class(Person, 'com.acme.app.Person')