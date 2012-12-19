*****************
  Shared Object 
*****************

.. topic:: Introduction

   The Adobe Flash Player has the ability to store persistent data on
   your computer, similar to a cookie, called a `Local Shared Object`_.
   PyAMF has the ability to read and write these ``.sol`` files.

.. contents::

Find the files
==============

The Local Shared Object files are not stored in the cookies folder of
your browser and the location also differs depending on the operating
system you are using.

For the Windows user::

   C:\Documents and Settings\{Your User Name}\Application Data\Macromedia\Flash Player\#SharedObjects\

On Linux::

   /home/{Your User Name}/.macromedia/Flash_Player/#SharedObjects/

On Mac OS X::

   /Users/{Your User Name}/Library/Preferences/Macromedia/Flash Player/#SharedObjects/


Manipulating the files
======================

PyAMF makes it as easy as possible to interact with these files.


Loading a Local Shared Object
-----------------------------

This file is located in the ``youtube.com`` directory, check it out on your
own system (assuming you've visited youtube.com_ at some point).

.. code-block:: python
   :linenos:

   from pyamf import sol

   file = 'timeDisplayConfig.sol'
   lso = sol.load(file)
   print lso


Which should output the following:

.. code-block:: python

   {u'modeDefaultSet': True, u'displayMode': u'played'}


Saving a Local Shared Object
----------------------------

.. code-block:: python
   :linenos:

   from pyamf import sol

   lso = sol.SOL('userData')
   lso['username'] = 'joe.bloggs'

   file = 'loginDetails.sol'
   sol.save(lso, file)


AMF0 and AMF3
=============

Since the introduction of the Adobe Flash Player 9, sol's can be read/written
using AMF0 encoding or AMF3 encoding. PyAMF also supports this. When reading
a sol file, PyAMF will automatically detect which encoding is used and act
appropriately.

When writing a sol, the default is to use AMF0. You can override this by
supplying the ``encoding`` keyword to the ``save`` function.

.. code-block:: python
    :linenos:

    from pyamf import sol, AMF3

    lso = sol.SOL('scoreData')
    lso['highScores'] = {
       'nick': 3400,
       'thijs': 3800,
       'arnar': 4500
    }

    file = 'highScores.sol'
    sol.save(lso, file, encoding=AMF3)


.. _youtube.com: http://www.youtube.com
.. _Local Shared Object: http://en.wikipedia.org/wiki/Local_Shared_Object
