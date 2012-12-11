import pyamf

@RemoteClass(alias="model.MyClass")
class MyClass:
    def __init__(self, *args, **kwargs):
        self.a = args[0]
        self.b = args[1]

class RemoteClass(object):
    def __init__(self, alias):
        self.alias = alias

    def __call__(self, klass):
        pyamf.register_class(klass, self.alias)
        return klass

