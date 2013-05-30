# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
PyAMF Elixir adapter tests.

@since: 0.6
"""

import unittest

try:
    import elixir as e
    from pyamf.adapters import _elixir as adapter
except ImportError:
    e = None

import pyamf


if e:
    class Genre(e.Entity):
        name = e.Field(e.Unicode(15), primary_key=True)
        movies = e.ManyToMany('Movie')

        def __repr__(self):
            return '<Genre "%s">' % self.name


    class Movie(e.Entity):
        title = e.Field(e.Unicode(30), primary_key=True)
        year = e.Field(e.Integer, primary_key=True)
        description = e.Field(e.UnicodeText, deferred=True)
        director = e.ManyToOne('Director')
        genres = e.ManyToMany('Genre')


    class Person(e.Entity):
        name = e.Field(e.Unicode(60), primary_key=True)


    class Director(Person):
        movies = e.OneToMany('Movie')
        e.using_options(inheritance='multi')


    # set up
    e.metadata.bind = "sqlite://"


class BaseTestCase(unittest.TestCase):
    """
    Initialise up all table/mappers.
    """

    def setUp(self):
        if not e:
            self.skipTest("'elixir' is not available")

        e.setup_all()
        e.create_all()

        self.movie_alias = pyamf.register_class(Movie, 'movie')
        self.genre_alias = pyamf.register_class(Genre, 'genre')
        self.director_alias = pyamf.register_class(Director, 'director')

        self.create_movie_data()

    def tearDown(self):
        e.drop_all()
        e.session.rollback()
        e.session.expunge_all()

        pyamf.unregister_class(Movie)
        pyamf.unregister_class(Genre)
        pyamf.unregister_class(Director)

    def create_movie_data(self):
        scifi = Genre(name=u"Science-Fiction")
        rscott = Director(name=u"Ridley Scott")
        glucas = Director(name=u"George Lucas")
        alien = Movie(title=u"Alien", year=1979, director=rscott, genres=[scifi, Genre(name=u"Horror")])
        brunner = Movie(title=u"Blade Runner", year=1982, director=rscott, genres=[scifi])
        swars = Movie(title=u"Star Wars", year=1977, director=glucas, genres=[scifi])

        e.session.commit()
        e.session.expunge_all()


class ClassAliasTestCase(BaseTestCase):
    def test_type(self):
        self.assertEqual(
            self.movie_alias.__class__, adapter.ElixirAdapter)
        self.assertEqual(
            self.genre_alias.__class__, adapter.ElixirAdapter)
        self.assertEqual(
            self.director_alias.__class__, adapter.ElixirAdapter)

    def test_get_attrs(self):
        m = Movie.query.filter_by(title=u"Blade Runner").one()

        g = m.genres[0]
        d = m.director

        attrs = self.movie_alias.getEncodableAttributes(m)

        self.assertEqual(attrs, {
            'genres': [g],
            'description': None,
            'title': u'Blade Runner',
            'director': d,
            'year': 1982,
            'sa_key': [u'Blade Runner', 1982],
            'sa_lazy': []
        })

    def test_inheritance(self):
        d = Director.query.filter_by(name=u"Ridley Scott").one()

        attrs = self.director_alias.getEncodableAttributes(d)

        self.assertEqual(attrs, {
            'movies': d.movies,
            'sa_key': [u'Ridley Scott'],
            'person_name': u'Ridley Scott',
            'name': u'Ridley Scott',
            'sa_lazy': []
        })
