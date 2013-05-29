from google.appengine.ext import db


class PetModel(db.Model):
    """
    """

    # 'borrowed' from http://code.google.com/appengine/docs/datastore/entitiesandmodels.html
    name = db.StringProperty(required=True)
    type = db.StringProperty(required=True, choices=set(["cat", "dog", "bird"]))
    birthdate = db.DateProperty()
    weight_in_pounds = db.IntegerProperty()
    spayed_or_neutered = db.BooleanProperty()


class PetExpando(db.Expando):
    """
    """

    name = db.StringProperty(required=True)
    type = db.StringProperty(required=True, choices=set(["cat", "dog", "bird"]))
    birthdate = db.DateProperty()
    weight_in_pounds = db.IntegerProperty()
    spayed_or_neutered = db.BooleanProperty()


class ListModel(db.Model):
    """
    """
    numbers = db.ListProperty(long)


class GettableModelStub(db.Model):
    """
    """

    gets = []

    @staticmethod
    def get(*args, **kwargs):
        GettableModelStub.gets.append([args, kwargs])


class Author(db.Model):
    name = db.StringProperty()


class Novel(db.Model):
    title = db.StringProperty()
    author = db.ReferenceProperty(Author)


class EmptyModel(db.Model):
    """
    A model that has no properties but also has no entities in the datastore.
    """
