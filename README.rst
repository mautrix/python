mautrix-python
==============

|PyPI badge| |Python versions| |License|

A Python 3 asyncio Matrix framework.

Components:

* Basic HTTP request sender
* Client API endpoints as functions
* High-level application service framework

  * Basic transaction and user/alias query support (based on Cadair's python-appservice-framework_)
  * Basic room state storage
  * Intent wrapper around the client API functions (design based on matrix-appservice-bridge)

* Soon™: High-level client framework

.. _python-appservice-framework: https://github.com/Cadair/python-appservice-framework/
.. |PyPI badge| image:: https://img.shields.io/pypi/v/mautrix.svg
   :target: https://pypi.python.org/pypi/mautrix
.. |Python versions| image:: https://img.shields.io/pypi/pyversions/mautrix-appservice.svg
.. |License| image:: https://img.shields.io/github/license/tulir/mautrix.svg
   :target: https://github.com/tulir/mautrix-python/blob/master/LICENSE
