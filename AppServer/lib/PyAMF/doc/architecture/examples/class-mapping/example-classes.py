class User(object):
    def __init__(self, name, pass):
        self.name = name
        self.pass = pass

class Permission(object):
    def __init__(self, type):
        self.type = type
