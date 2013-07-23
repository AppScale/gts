from django.db import models


class SimplestModel(models.Model):
    """
    The simplest Django model you can have
    """


class TimeClass(models.Model):
    """
    A model with all the time based fields
    """

    t = models.TimeField()
    d = models.DateField()
    dt = models.DateTimeField()


class ParentReference(models.Model):
    """
    Has a foreign key to L{ChildReference}
    """

    name = models.CharField(max_length=100)
    bar = models.ForeignKey('ChildReference', null=True)


class ChildReference(models.Model):
    """
    Has a foreign key relation to L{ParentReference}
    """

    name = models.CharField(max_length=100)
    foo = models.ForeignKey(ParentReference)


class NotSaved(models.Model):
    name = models.CharField(max_length=100)


class Publication(models.Model):
    title = models.CharField(max_length=30)

    def __unicode__(self):
        return self.title

    class Meta:
        ordering = ('title',)


class Reporter(models.Model):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.EmailField()

    def __unicode__(self):
        return u"%s %s" % (self.first_name, self.last_name)


class Article(models.Model):
    headline = models.CharField(max_length=100)
    publications = models.ManyToManyField(Publication)
    reporter = models.ForeignKey(Reporter, null=True)

    def __unicode__(self):
        return self.headline

    class Meta:
        ordering = ('headline',)


# concrete inheritance
class Place(models.Model):
    name = models.CharField(max_length=50)
    address = models.CharField(max_length=80)


class Restaurant(Place):
    serves_hot_dogs = models.BooleanField()
    serves_pizza = models.BooleanField()


# abstract inheritance
class CommonInfo(models.Model):
    name = models.CharField(max_length=100)
    age = models.PositiveIntegerField()

    class Meta:
        abstract = True

class Student(CommonInfo):
    home_group = models.CharField(max_length=5)


# foreign keys
class NullForeignKey(models.Model):
    foobar = models.ForeignKey(SimplestModel, null=True)

class BlankForeignKey(models.Model):
    foobar = models.ForeignKey(SimplestModel, blank=True)


class StaticRelation(models.Model):
    gak = models.ForeignKey(SimplestModel)


class FileModel(models.Model):
    file = models.FileField(upload_to='file_model')
    text = models.CharField(max_length=64)


try:
    import PIL

    class Profile(models.Model):
        file = models.ImageField(upload_to='profile')
        text = models.CharField(max_length=64)
except ImportError:
    pass


class DBColumnModel(models.Model):
    """
    @see: #807
    """
    bar = models.ForeignKey(SimplestModel, db_column='custom')
