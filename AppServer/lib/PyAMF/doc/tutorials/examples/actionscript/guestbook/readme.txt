Guestbook example
=================

This example shows how to create a simple guestbook
using Flex (client) and Twisted (remoting gateway).

More info can be found in the documentation:
http://pyamf.org/tutorials/actionscript/guestbook.html

Please note that the Twisted and Genshi packages are required to
run this example. Genshi is only used to sanitize the incoming
html for the guestbook messages.

Install via setuptools::

  easy_install Twisted
  easy_install Genshi
