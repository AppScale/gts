import logging

from google.appengine.ext import db

from pyamf.remoting.gateway.wsgi import WSGIGateway

from models import User


class UserService(object):
    def saveUser(self, user):
        user.put()

    def getUsers(self):
        return User.all()


services = {
    'user': UserService
}

gw = WSGIGateway(services, logger=logging)