mautrix-python
==============

|PyPI| |Python versions| |License| |Docs| |Code style| |Imports|

A Python 3.8+ asyncio Matrix framework.

Matrix room: `#maunium:maunium.net`_


Components
----------

* Basic HTTP request sender (mautrix.api_)

* `Client API`_ endpoints as functions (mautrix.client.api_)

* Medium-level application service framework (mautrix.appservice_)

  * Basic transaction and user/alias query support (based on Cadair's python-appservice-framework_)
  * Basic room state storage
  * Intent wrapper around the client API functions (design based on matrix-appservice-bridge)

* Medium-level end-to-end encryption framework (mautrix.crypto_)

  * Handles all the complicated e2ee key exchange
  * Uses libolm through python-olm for the low-level crypto

* High-level bridging utility framework (mautrix.bridge_)

  * Base class for bridges
  * Common bridge configuration and appservice registration generation things
  * Double-puppeting helper
  * End-to-bridge encryption helper

* High-level client framework (mautrix.client_)

  * Syncing and event handling helper.
  * End-to-end encryption helper.

* Utilities (mautrix.util_)

  * Matrix HTML parsing and generating utilities
  * Manhole system (get a python shell in a running process)
  * YAML config helpers
  * Database helpers (new: asyncpg, legacy: SQLAlchemy)
  * Color logging utility
  * Very simple HMAC-SHA256 utility for signing tokens (like JWT, but hardcoded to use a single good algorithm)

.. _#maunium:maunium.net: https://matrix.to/#/#maunium:maunium.net
.. _python-appservice-framework: https://github.com/Cadair/python-appservice-framework/
.. _Client API: https://matrix.org/docs/spec/client_server/r0.6.1.html

.. _mautrix.api: https://docs.mau.fi/python/latest/api/mautrix.api.html
.. _mautrix.client.api: https://docs.mau.fi/python/latest/api/mautrix.client.api.html
.. _mautrix.appservice: https://docs.mau.fi/python/latest/api/mautrix.appservice/index.html
.. _mautrix.bridge: https://docs.mau.fi/python/latest/api/mautrix.bridge/index.html
.. _mautrix.client: https://docs.mau.fi/python/latest/api/mautrix.client.html
.. _mautrix.crypto: https://docs.mau.fi/python/latest/api/mautrix.crypto.html
.. _mautrix.util: https://docs.mau.fi/python/latest/api/mautrix.util/index.html

.. |PyPI| image:: https://img.shields.io/pypi/v/mautrix.svg
   :target: https://pypi.python.org/pypi/mautrix
   :alt: PyPI: mautrix
.. |Python versions| image:: https://img.shields.io/pypi/pyversions/mautrix.svg
.. |License| image:: https://img.shields.io/github/license/mautrix/python.svg
   :target: https://github.com/mautrix/python/blob/master/LICENSE
   :alt: License: MPL-2.0
.. |Docs| image:: https://img.shields.io/gitlab/pipeline-status/mautrix/python?branch=master&gitlab_url=https%3A%2F%2Fmau.dev&label=docs
   :target: https://docs.mau.fi/python/latest/
.. |Code style| image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black
.. |Imports| image:: https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336
   :target: https://pycqa.github.io/isort/
