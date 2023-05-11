Changes
=======

0.2.2 (11 May 2023)
-------------------

- Make it clear that for :class:`DatabaseFromEnvironment` to check a port is up,
  the port must be specified.

0.2.1 (11 May 2023)
-------------------

- Fix bug when no port was specified in a :class:`DatabaseFromEnvironment` url.

0.2.0 (11 May 2023)
-------------------

- Add :class:`DatabaseFromEnvironment` service.

- :class:`Provider` can now be used to choose the first available :class:`Service`
  that provides an instance.

0.1.0 (9 May 2023)
-------------------

- Initial release featuring simple container services with helpers for common databases.
