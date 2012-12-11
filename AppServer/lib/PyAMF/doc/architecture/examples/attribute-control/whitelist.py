# models.py

from google.appengine.ext import db

import pyamf


class User(db.Model):
    class __amf__:
        dynamic = False
        exclude = ('password',)
        readonly = ('username',)

    username = db.StringProperty()
    password = db.StringProperty()

    name = db.StringProperty()
    dob = db.DateProperty()


pyamf.register_class(User, 'com.acme.app.User')