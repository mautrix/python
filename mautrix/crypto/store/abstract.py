# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, Dict, List
from abc import ABC, abstractmethod

from mautrix.types import (SyncToken, IdentityKey, SessionID, RoomID, EventID, UserID, DeviceID,
                           RoomEncryptionStateEventContent)

from .. import OlmAccount, Session, InboundGroupSession, OutboundGroupSession, DeviceIdentity


class StateStore(ABC):
    @abstractmethod
    async def is_encrypted(self, room_id: RoomID) -> bool: ...

    @abstractmethod
    async def get_encryption_info(self, room_id: RoomID
                                  ) -> Optional[RoomEncryptionStateEventContent]: ...

    @abstractmethod
    async def find_shared_rooms(self, user_id: UserID) -> List[RoomID]: ...


class CryptoStore(ABC):
    account_id: str
    pickle_key: str

    @abstractmethod
    async def get_device_id(self) -> Optional[DeviceID]:
        """
        Get the device ID corresponding to this account_id

        Returns:
            The device ID in the store.
        """

    @abstractmethod
    async def put_device_id(self, device_id: DeviceID) -> None: ...

    async def open(self) -> None:
        """
        Open the store. If the store doesn't require opening any resources beforehand or only opens
        when flushing, this can be a no-op
        """

    async def close(self) -> None:
        """
        Close the store when it will no longer be used. The default implementation will simply call
        .flush(). If the store doesn't keep any persistent resources, the default implementation is
        sufficient.
        """
        await self.flush()

    async def flush(self) -> None:
        """Flush the store. If all the methods persist data immediately, this can be a no-op."""

    @abstractmethod
    async def put_next_batch(self, next_batch: SyncToken) -> None: ...

    @abstractmethod
    async def get_next_batch(self) -> SyncToken: ...

    @abstractmethod
    async def put_account(self, account: OlmAccount) -> None: ...

    @abstractmethod
    async def get_account(self) -> OlmAccount: ...

    @abstractmethod
    async def has_session(self, key: IdentityKey) -> bool: ...

    @abstractmethod
    async def get_sessions(self, key: IdentityKey) -> List[Session]: ...

    @abstractmethod
    async def get_latest_session(self, key: IdentityKey) -> Optional[Session]: ...

    @abstractmethod
    async def add_session(self, key: IdentityKey, session: Session) -> None: ...

    @abstractmethod
    async def update_session(self, key: IdentityKey, session: Session) -> None: ...

    @abstractmethod
    async def put_group_session(self, room_id: RoomID, sender_key: IdentityKey,
                                session_id: SessionID, session: InboundGroupSession) -> None: ...

    @abstractmethod
    async def get_group_session(self, room_id: RoomID, sender_key: IdentityKey,
                                session_id: SessionID) -> InboundGroupSession: ...

    @abstractmethod
    async def add_outbound_group_session(self, session: OutboundGroupSession) -> None: ...

    @abstractmethod
    async def update_outbound_group_session(self, session: OutboundGroupSession) -> None: ...

    @abstractmethod
    async def get_outbound_group_session(self, room_id: RoomID
                                         ) -> Optional[OutboundGroupSession]: ...

    @abstractmethod
    async def remove_outbound_group_session(self, room_id: RoomID) -> None: ...

    @abstractmethod
    async def remove_outbound_group_sessions(self, rooms: List[RoomID]) -> None: ...

    @abstractmethod
    async def validate_message_index(self, sender_key: IdentityKey, session_id: SessionID,
                                     event_id: EventID, index: int, timestamp: int) -> bool: ...

    @abstractmethod
    async def get_devices(self, user_id: UserID) -> Optional[Dict[DeviceID, DeviceIdentity]]: ...

    @abstractmethod
    async def get_device(self, user_id: UserID, device_id: DeviceID
                         ) -> Optional[DeviceIdentity]: ...

    @abstractmethod
    async def put_devices(self, user_id: UserID, devices: Dict[DeviceID, DeviceIdentity]
                          ) -> None: ...

    @abstractmethod
    async def filter_tracked_users(self, users: List[UserID]) -> List[UserID]: ...
