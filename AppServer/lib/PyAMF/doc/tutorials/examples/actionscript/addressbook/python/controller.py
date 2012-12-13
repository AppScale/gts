# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Controller for SQLAlchemy Addressbook example.

@since: 0.4.1
"""

from datetime import datetime

import pyamf

import models
from persistent import Schema


class SAObject(object):
    """
    Handles common operations for persistent objects.
    """
    
    def load(self, class_alias, key):
        klass = pyamf.load_class(class_alias).klass
        session = Schema().session
        return session.query(klass).get(key)

    def loadAll(self, class_alias):
        klass = pyamf.load_class(class_alias).klass
        session = Schema().session
        return session.query(klass).all()

    def loadAttr(self, class_alias, key, attr):
        obj = self.load(class_alias, key)
        return getattr(obj, attr)

    def save(self, obj):
        session = Schema().session
        merged_obj = session.merge(obj)
        session.commit()

    def saveList(self, objs):
        for obj in objs:
            self.save(obj)

    def remove(self, class_alias, key):
        klass = pyamf.load_class(class_alias).klass
        session = Schema().session
        obj = session.query(klass).get(key)
        session.delete(obj)
        session.commit()

    def removeList(self, class_alias, keys):
        for key in keys:
            self.remove(class_alias, key)

    def insertDefaultData(self):
        user = models.User()
        user.first_name = 'Bill'
        user.last_name = 'Lumbergh'
        user.created = datetime.utcnow()
        for label, email in {'personal': 'bill@yahoo.com', 'work': 'bill@initech.com'}.iteritems():
            email_obj = models.Email()
            email_obj.label = label
            email_obj.email = email
            user.emails.append(email_obj)

        for label, number in {'personal': '1-800-555-5555', 'work': '1-555-555-5555'}.iteritems():
            phone_obj = models.PhoneNumber()
            phone_obj.label = label
            phone_obj.number = number
            user.phone_numbers.append(phone_obj)

        session = Schema().session
        session.add(user)
        session.commit()
        
        return 'Added user: %s %s' % (user.first_name, user.last_name)
