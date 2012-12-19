from setuptools import setup

version = '1.1.1'

setup(
    name='WebOb',
    version=version,
    description="WSGI request and response object",
    long_description="""\
WebOb provides wrappers around the WSGI request environment, and an
object to help create WSGI responses.

The objects map much of the specified behavior of HTTP, including
header parsing and accessors for other standard parts of the
environment.

You may install the `in-development version of WebOb
<http://bitbucket.org/ianb/webob/get/tip.gz#egg=WebOb-dev>`_ with
``pip install WebOb==dev`` (or ``easy_install WebOb==dev``).

* `WebOb reference <http://docs.webob.org/en/latest/reference.html>`_
* `Bug tracker <https://bitbucket.org/ianb/webob/issues>`_
* `Browse source code <https://bitbucket.org/ianb/webob/src>`_
* `Mailing list <http://bit.ly/paste-users>`_
* `Release news <http://docs.webob.org/en/latest/news.html>`_
* `Detailed changelog <https://bitbucket.org/ianb/webob/changesets>`_
""",
    classifiers=[
        "Development Status :: 6 - Mature",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Topic :: Internet :: WWW/HTTP :: WSGI",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware",
        "Programming Language :: Python :: 2.5",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
    ],
    keywords='wsgi request web http',
    author='Ian Bicking',
    author_email='ianb@colorstudy.com',
    maintainer='Sergey Schetinin',
    maintainer_email='sergey@maluke.com',
    url='http://webob.org/',
    license='MIT',
    packages=['webob'],
    zip_safe=True,
    test_suite='nose.collector',
    tests_require=['nose', 'WebTest'],
)
