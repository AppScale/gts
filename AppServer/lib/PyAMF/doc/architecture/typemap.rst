************
  Type Map 
************

.. topic:: Overview

   The following is a guide to the ActionScript to Python type
   mappings.


Basic Types
===========

The following types are available in Adobe Flash Player 6 and newer:

+-------------------------------------+---------------------------------------------+
| ActionScript Type                   | Python Type	                            |
+=====================================+=============================================+
| ``null``          		      | ``None``    	                            |
+-------------------------------------+---------------------------------------------+
| ``undefined``, ``void``             | :class:`pyamf.Undefined`                    |
+-------------------------------------+---------------------------------------------+
| ``String``     	              | ``unicode``                                 |
+-------------------------------------+---------------------------------------------+
| ``Boolean``                         | ``bool``                                    |
+-------------------------------------+---------------------------------------------+
| ``Number``     		      | ``float``                                   |
+-------------------------------------+---------------------------------------------+
| ``Date``                            | :py:class:`datetime.datetime`               |
+-------------------------------------+---------------------------------------------+
| ``XML``                             | :py:class:`xml.etree.ElementTree.Element`   |
+-------------------------------------+---------------------------------------------+
| ``Array``               	      | ``list``, ``tuple``                         |
+-------------------------------------+---------------------------------------------+
| ``Object``    		      |	``dict``		                    |
+-------------------------------------+---------------------------------------------+
| ``RecordSet``                	      | :class:`pyamf.amf0.RecordSet`               |
+-------------------------------------+---------------------------------------------+
| Typed Object (other than the above) | class instance (registered via              |
|				      | :func:`pyamf.register_class`)               |
+-------------------------------------+---------------------------------------------+


AMF3
====

The following types are available in the Adobe Flash Player 9 and newer:

+-------------------------------------+---------------------------------+
| ActionScript Type                   | Python Type	                |
+=====================================+=================================+
| ``int``, ``uint``          	      | ``int``    	                |
+-------------------------------------+---------------------------------+
| ``ByteArray``             	      | :class:`pyamf.amf3.ByteArray`   |
+-------------------------------------+---------------------------------+
| ``DataInput``     	              | :class:`pyamf.amf3.DataInput`   |
+-------------------------------------+---------------------------------+
| ``DataOutput``                      | :class:`pyamf.amf3.DataOutput`  |
+-------------------------------------+---------------------------------+


Flex (AMF3)
===========

The following types are available in `Adobe Flex 2`_ and newer:

+-------------------------------------+---------------------------------------------------+
| ActionScript Type                   | Python Type	                                  |
+=====================================+===================================================+
| ``ObjectProxy``          	      | :class:`pyamf.flex.ObjectProxy`                   |
+-------------------------------------+---------------------------------------------------+
| ``ArrayCollection``         	      | :class:`pyamf.flex.ArrayCollection`               |
+-------------------------------------+---------------------------------------------------+
| ``AbstractMessage``     	      | :class:`pyamf.flex.messaging.AbstractMessage`     |
+-------------------------------------+---------------------------------------------------+
| ``AcknowledgeMessage``              | :class:`pyamf.flex.messaging.AcknowledgeMessage`  |
+-------------------------------------+---------------------------------------------------+
| ``AsyncMessage``                    | :class:`pyamf.flex.messaging.AsyncMessage`        |
+-------------------------------------+---------------------------------------------------+
| ``CommandMessage``                  | :class:`pyamf.flex.messaging.CommandMessage`      |
+-------------------------------------+---------------------------------------------------+
| ``ErrorMessage``                    | :class:`pyamf.flex.messaging.ErrorMessage`        |
+-------------------------------------+---------------------------------------------------+
| ``RemotingMessage``                 | :class:`pyamf.flex.messaging.RemotingMessage`     |
+-------------------------------------+---------------------------------------------------+
| ``DataMessage``                     | :class:`pyamf.flex.data.DataMessage`              |
+-------------------------------------+---------------------------------------------------+
| ``SequencedMessage``                | :class:`pyamf.flex.data.SequencedMessage`         |
+-------------------------------------+---------------------------------------------------+
| ``PagedMessage``                    | :class:`pyamf.flex.data.PagedMessage`             |
+-------------------------------------+---------------------------------------------------+
| ``DataErrorMessage``                | :class:`pyamf.flex.data.DataErrorMessage`         |
+-------------------------------------+---------------------------------------------------+

**Note**: We plan to deprecate and move the Flex support into a new project_ before PyAMF 1.0 is released.


.. _Adobe Flex 2: http://opensource.adobe.com/wiki/display/flexsdk
.. _project: http://plasmads.org
