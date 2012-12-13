=====================
 Installation Guide
=====================

.. contents::

PyAMF requires Python_ 2.4 or newer. Python 3.0 isn't supported yet_.


Easy Installation
=================

If you have setuptools_ or the `easy_install`_ tool already installed,
simply type the following on the command-line to install PyAMF::

    easy_install pyamf

`Note: you might need root permissions or equivalent for these steps.`

If you don't have `setuptools` or `easy_install`, first download
distribute_setup.py_ and run::

    python distribute_setup.py

After `easy_install` is installed, run `easy_install pyamf` again. If
you run into problems, try the manual installation instructions below.

To upgrade your existing PyAMF installation to the latest version
use::

    easy_install -U pyamf


Manual Installation
===================

To use PyAMF with Python 2.4, the following software packages
must be installed. You **don't** need these packages if you're using
Python 2.5 or newer!

The ``easy_install`` command will automatically install them for you, as
described above, but you can also choose to download and install the packages
manually.

- ElementTree_ 1.2.6 or newer
- uuid_ 1.30 or newer

Step 1
------

:doc:`community/download` and unpack the PyAMF archive of your choice::

    tar zxfv PyAMF-<version>.tar.gz
    cd PyAMF-<version>


Step 2
------

Run the Python-typical setup at the top of the source directory
from a command-prompt::

    python setup.py install

This will byte-compile the Python source code and install it in the
``site-packages`` directory of your Python installation.

Note: to disable the installation of the C-extension, supply the
``--disable-ext`` option::

    python setup.py install --disable-ext


Optional Extras
===============

PyAMF integrates with the following optional third-party Python
libraries:

- wsgiref_ 0.1.2 or newer (included in Python 2.5 and newer)
- cElementTree_ 1.0.5 or newer (included in Python 2.5 and newer)
- lxml_ 2.2 or newer
- SQLAlchemy_ 0.4 or newer
- Twisted_ 2.5 or newer
- Django_ 0.97 or newer
- `Google App Engine`_ 1.0 or newer
- Elixir_ 0.7.1 or newer


Unit Tests
==========

To run the PyAMF unit tests the following software packages
must be installed. The ``easy_install`` command will automatically
install them for you, as described above, but you can also choose to
download and install the packages manually.

- unittest2_ (included in Python 2.7 and newer)

You can run the unit tests using setuptools like this::

    python setup.py test

Other libraries for unit testing are also supported, including:

- nose_
- Trial_


C-Extension
===========

To modify the cPyAMF extension you need:

- Cython_ 0.13 or newer

And run the command below on the ``.pyx`` files to create the
``.c`` file, which contains the C source for the ``cPyAMF``
extension module::

    cython amf3.pyx


Advanced Options
================

To find out about other advanced installation options, run::

    easy_install --help

Also see `Installing Python Modules`_ for detailed information.

To install PyAMF to a custom location::

    easy_install --prefix=/path/to/installdir


Documentation
=============

Sphinx
------

To build the main documentation you need:

- Sphinx_ 1.0 or newer
- `sphinxcontrib.epydoc`_ 0.4 or newer
- a :doc:`copy <community/download>` of the PyAMF source distribution

Unix users run the command below in the ``doc`` directory to create the
HTML version of the PyAMF documentation::

    make html

Windows users can run the make.bat file instead::

    make.bat

This will generate the HTML documentation in the ``doc/build/html``
folder. This documentation is identical to the content on the main PyAMF
website_.

**Note**: if you don't have the `make` tool installed then you can invoke
Sphinx from the ``doc`` directory directly like this::

    sphinx-build -b html . build

Epydoc
------

To build the API documentation you need:

- Epydoc_ 3.0 or newer
- a :doc:`copy <community/download>` of the PyAMF source distribution

Run the command below in the root directory to create the HTML version of
the PyAMF API documentation::

    epydoc --config=setup.cfg

This will generate the HTML documentation in the ``doc/build/api``
folder.


.. _Python: 			http://www.python.org
.. _yet:			http://dev.pyamf.org/milestone/0.7
.. _setuptools:			http://peak.telecommunity.com/DevCenter/setuptools
.. _easy_install: 		http://peak.telecommunity.com/DevCenter/EasyInstall#installing-easy-install
.. _distribute_setup.py:		http://github.com/hydralabs/pyamf/blob/master/distribute_setup.py
.. _Epydoc:			http://epydoc.sourceforge.net
.. _ElementTree:		http://effbot.org/zone/element-index.htm
.. _lxml:			http://codespeak.net/lxml
.. _uuid:			http://pypi.python.org/pypi/uuid
.. _wsgiref:			http://pypi.python.org/pypi/wsgiref
.. _cElementTree: 		http://effbot.org/zone/celementtree.htm
.. _SQLAlchemy:			http://www.sqlalchemy.org
.. _Twisted:			http://twistedmatrix.com
.. _Django:			http://www.djangoproject.com
.. _Google App Engine: 		http://code.google.com/appengine
.. _Elixir:			http://elixir.ematia.de
.. _unittest2:			http://pypi.python.org/pypi/unittest2
.. _nose:			http://somethingaboutorange.com/mrl/projects/nose
.. _Trial:			http://twistedmatrix.com/trac/wiki/TwistedTrial
.. _Cython:			http://cython.org
.. _Sphinx:     		http://sphinx.pocoo.org
.. _website:    		http://pyamf.org
.. _Installing Python Modules: 	http://docs.python.org/install/index.html
.. _sphinxcontrib.epydoc:       http://packages.python.org/sphinxcontrib-epydoc
