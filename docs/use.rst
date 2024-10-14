.. py:currentmodule:: testservices

Using testservices
==================

Here are the concepts used by testservices:

.. glossary::

  Service
    This is the basic thing that testservices manages. It often ends up representing
    a TCP port and some credential to connect to it, but, conceptually, can be anything
    from a piece of hardware to a simple file on disk.

    Its API is defined by :class:`testservices.service.Service`.

  .. py:currentmodule:: testservices.service

Installation
~~~~~~~~~~~~

testservices is available on the `Python Package Index`__ and can be installed
with any tools for managing Python environments.

__ https://pypi.org
