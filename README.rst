mautrix-python
==============

|PyPI| |ReadTheDocs| |Python versions| |License|

A Python 3.6+ asyncio Matrix framework.

Components:

* Basic HTTP request sender (mautrix.api_)

* `Client API`_ endpoints as functions (mautrix.client.api_)

* Medium-level application service framework (mautrix.appservice_)

  * Basic transaction and user/alias query support (based on Cadair's python-appservice-framework_)
  * Basic room state storage
  * Intent wrapper around the client API functions (design based on matrix-appservice-bridge)

* Soon™: High-level bridging framework (mautrix.bridge_).

* High-level client framework (mautrix.client_). Currently only has an event handling helper.

.. _python-appservice-framework: https://github.com/Cadair/python-appservice-framework/
.. _Client API: https://matrix.org/docs/spec/client_server/r0.4.0.html

.. _mautrix.api: https://mautrix.readthedocs.io/en/latest/mautrix.api.html
.. _mautrix.client.api: https://mautrix.readthedocs.io/en/latest/mautrix.client.api.html
.. _mautrix.appservice: https://mautrix.readthedocs.io/en/latest/mautrix.appservice.html
.. _mautrix.bridge: https://mautrix.readthedocs.io/en/latest/mautrix.bridge.html
.. _mautrix.client: https://mautrix.readthedocs.io/en/latest/mautrix.client.html

.. |PyPI| image:: https://img.shields.io/pypi/v/mautrix.svg
   :target: https://pypi.python.org/pypi/mautrix
.. |ReadTheDocs| image:: https://img.shields.io/readthedocs/mautrix.svg
   :target: https://mautrix.readthedocs.io
.. |Python versions| image:: https://img.shields.io/pypi/pyversions/mautrix.svg
.. |License| image:: https://img.shields.io/github/license/tulir/mautrix-python.svg
   :target: https://github.com/tulir/mautrix-python/blob/master/LICENSE
