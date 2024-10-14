Changes
=======

0.3.0 (14 Oct 2024)
-------------------

- Strictly type checked with `mypy`.

- Re-worked interfaces for :class:`~testservices.service.Service` and
  :class:`~testservices.provider.Provider`.

- Re-worked container services.

- Beginnings of API documentation.

0.2.2 (11 May 2023)
-------------------

.. py:currentmodule:: testservices.services.databases

- Make it clear that for :class:`DatabaseFromEnvironment` to check a port is up,
  the port must be specified.

0.2.1 (11 May 2023)
-------------------

- Fix bug when no port was specified in a :class:`DatabaseFromEnvironment` url.

0.2.0 (11 May 2023)
-------------------

- Add :class:`DatabaseFromEnvironment` service.

- :class:`~testservices.provider.Provider` can now be used to choose the first available
  :class:`~testservices.service.Service` that provides an instance.

0.1.0 (9 May 2023)
-------------------

- Initial release featuring simple container services with helpers for common databases.
