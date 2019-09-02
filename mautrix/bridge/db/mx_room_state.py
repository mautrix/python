# Copyright (c) 2019 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Optional
import json

from sqlalchemy import Column, String, types

from mautrix.types import RoomID, PowerLevelStateEventContent
from mautrix.util.db import Base


class PowerLevelType(types.TypeDecorator):
    impl = types.Text

    @property
    def python_type(self):
        return PowerLevelStateEventContent

    def process_bind_param(self, value: PowerLevelStateEventContent, dialect) -> Optional[Dict]:
        if value is not None:
            return json.dumps(value.serialize())
        return None

    def process_result_value(self, value: Dict, dialect) -> Optional[PowerLevelStateEventContent]:
        if value is not None:
            return PowerLevelStateEventContent.deserialize(json.loads(value))
        return None

    def process_literal_param(self, value, dialect):
        return value


class RoomState(Base):
    __tablename__ = "mx_room_state"

    room_id: RoomID = Column(String(255), primary_key=True)
    power_levels: PowerLevelStateEventContent = Column(PowerLevelType, nullable=True)

    @property
    def has_power_levels(self) -> bool:
        return bool(self.power_levels)

    @classmethod
    def get(cls, room_id: RoomID) -> Optional['RoomState']:
        return cls._select_one_or_none(cls.c.room_id == room_id)
