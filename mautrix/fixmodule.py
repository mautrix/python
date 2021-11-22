from types import FunctionType, ModuleType
from typing import NewType

from . import types, bridge, client, crypto, errors, appservice
from .crypto import attachments
from .util import async_db, config, db, formatter, logging


def _fix(obj: ModuleType) -> None:
    for item_name in dir(obj):
        item = getattr(obj, item_name)
        if isinstance(item, (type, FunctionType, NewType)):
            # Ignore backwards-compatibility imports like the BridgeState import in mautrix.bridge
            if (
                item.__module__.startswith("mautrix")
                and not item.__module__.startswith(obj.__name__)
            ):
                continue

            item.__module__ = obj.__name__
        # elif type(item).__module__ == "typing":
        #     print(obj.__name__, item_name, type(item))


_things_to_fix = [types, bridge, client, crypto, attachments, errors, appservice, async_db,
                  config, db, formatter, logging]

for mod in _things_to_fix:
    _fix(mod)
