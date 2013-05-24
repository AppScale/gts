MarkupSafe
==========

Implements a unicode subclass that supports HTML strings:

>>> from markupsafe import Markup, escape
>>> escape("<script>alert(document.cookie);</script>")
Markup(u'&lt;script&gt;alert(document.cookie);&lt;/script&gt;')
>>> tmpl = Markup("<em>%s</em>")
>>> tmpl % "Peter > Lustig"
Markup(u'<em>Peter &gt; Lustig</em>')

If you want to make an object unicode that is not yet unicode
but don't want to lose the taint information, you can use the
`soft_unicode` function:

>>> from markupsafe import soft_unicode
>>> soft_unicode(42)
u'42'
>>> soft_unicode(Markup('foo'))
Markup(u'foo')

Objects can customize their HTML markup equivalent by overriding
the `__html__` function:

>>> class Foo(object):
...  def __html__(self):
...   return '<strong>Nice</strong>'
...
>>> escape(Foo())
Markup(u'<strong>Nice</strong>')
>>> Markup(Foo())
Markup(u'<strong>Nice</strong>')

Since MarkupSafe 0.10 there is now also a separate escape function
called `escape_silent` that returns an empty string for `None` for
consistency with other systems that return empty strings for `None`
when escaping (for instance Pylons' webhelpers).

If you also want to use this for the escape method of the Markup
object, you can create your own subclass that does that::

    from markupsafe import Markup, escape_silent as escape

    class SilentMarkup(Markup):
        __slots__ = ()

        @classmethod
        def escape(cls, s):
            return cls(escape(s))
