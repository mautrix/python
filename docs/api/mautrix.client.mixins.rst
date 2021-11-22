mautrix.client mixins
=====================

The :class:`Client <mautrix.client.Client>` class itself is very small, most of
the functionality on top of :class:`ClientAPI <mautrix.client.ClientAPI>` comes
from mixins that it includes. In some cases it might be useful to extend from a
mixin instead of the high-level client class (e.g. the appservice module's
:class:`IntentAPI <mautrix.appservice.api.IntentAPI>` extends
:class:`StoreUpdatingAPI <mautrix.client.StoreUpdatingAPI>`).

Syncer
------

.. autoclass:: mautrix.client.Syncer

DecryptionDispatcher
--------------------

.. autoclass:: mautrix.client.DecryptionDispatcher

EncryptingAPI
-------------

.. autoclass:: mautrix.client.EncryptingAPI

StoreUpdatingAPI
----------------

.. autoclass:: mautrix.client.StoreUpdatingAPI
