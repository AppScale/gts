******************************
  RemoteObject Configuration
******************************

.. topic:: Introduction

   For Flex developers it is much more natural to use the `RemoteObject`
   ActionScript API for accessing server-side objects instead of the
   pure Actionscript approach using NetConnection.

   Despite PyAMF currently not supporting the use of server-side Flex
   configuration files (like services-config.xml and remoting-config.xml),
   you can still use a `RemoteObject` within your Flex/PyAMF applications
   via programmatic configuration.


Example
=======

Here is how to wire up a `RemoteObject` programmatically:

.. literalinclude:: ../examples/general/remoteobject/remoteobject_test.as
    :linenos: