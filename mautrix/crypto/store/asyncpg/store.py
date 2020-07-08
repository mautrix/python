# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, Optional, List, Any
import logging
import asyncio

from mautrix.types import SyncToken, IdentityKey, SessionID, RoomID, EventID, UserID, DeviceID
from mautrix.client import ClientStore
from mautrix.util.async_db import Database
from mautrix.util.logging import TraceLogger

from ... import (OlmAccount, Session, InboundGroupSession, OutboundGroupSession, TrustState,
                 DeviceIdentity)
from ..abstract import CryptoStore
from .upgrade import upgrade_table


class PgCryptoStore(Database, CryptoStore, ClientStore):
    device_id: DeviceID
    pickle_key: str
    log: TraceLogger

    _sync_token: Optional[SyncToken]
    _account: Optional[OlmAccount]

    def __init__(self, device_id: DeviceID, pickle_key: str, url: str,
                 db_args: Optional[Dict[str, Any]] = None, log: Optional[TraceLogger] = None,
                 loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        super().__init__(url=url, db_args=db_args, upgrade_table=upgrade_table,
                         log=log or logging.getLogger("mau.crypto.db"), loop=loop)
        self.device_id = device_id
        self.pickle_key = pickle_key

        self._sync_token = None
        self._account = None

    async def find_first_device_id(self) -> Optional[DeviceID]:
        return await self.fetchval("SELECT device_id FROM crypto_account LIMIT 1")

    async def put_next_batch(self, next_batch: SyncToken) -> None:
        self._sync_token = next_batch
        await self.execute("UPDATE crypto_account SET sync_token=$1 WHERE device_id=$2",
                           self._sync_token, self.device_id)

    async def get_next_batch(self) -> SyncToken:
        if self._sync_token is None:
            self._sync_token = await self.fetchval("SELECT sync_token FROM crypto_account"
                                                   " WHERE device_id=$1", self.device_id)
        return self._sync_token

    async def put_account(self, account: OlmAccount) -> None:
        self._account = account
        pickle = account.pickle(self.pickle_key)
        await self.execute("INSERT INTO crypto_account (device_id, shared, sync_token, account) "
                           "VALUES($1, $2, $3, $4) ON CONFLICT (device_id) DO UPDATE "
                           "SET shared=$2, sync_token=$3, account=$4",
                           self.device_id, account.shared, self._sync_token or "", pickle)

    async def get_account(self) -> OlmAccount:
        if self._account is None:
            row = await self.fetchrow("SELECT shared, account FROM crypto_account "
                                      "WHERE device_id=$1", self.device_id)
            if row is not None:
                self._account = OlmAccount.from_pickle(row["account"], passphrase=self.pickle_key,
                                                       shared=row["shared"])
        return self._account

    async def has_session(self, key: IdentityKey) -> bool:
        val = await self.fetchval("SELECT session_id FROM crypto_olm_session "
                                  "WHERE sender_key=$1", key)
        return val is not None

    async def get_sessions(self, key: IdentityKey) -> List[Session]:
        rows = await self.fetch("SELECT session, created_at, last_used FROM crypto_olm_session "
                                "WHERE sender_key=$1 ORDER BY session_id", key)
        sessions = []
        for row in rows:
            sess = Session.from_pickle(row["session"], passphrase=self.pickle_key,
                                       creation_time=row["created_at"], use_time=row["last_used"])
            sessions.append(sess)
        return sessions

    async def get_latest_session(self, key: IdentityKey) -> Optional[Session]:
        row = await self.fetchrow("SELECT session, created_at, last_used FROM crypto_olm_session"
                                  " WHERE sender_key=$1 ORDER BY session DESC LIMIT 1", key)
        if row is None:
            return None
        return Session.from_pickle(row["session"], passphrase=self.pickle_key,
                                   creation_time=row["created_at"], use_time=row["last_used"])

    async def add_session(self, key: IdentityKey, session: Session) -> None:
        pickle = session.pickle(self.pickle_key)
        await self.execute("INSERT INTO crypto_olm_session (session_id, sender_key, session, "
                           "created_at, last_used) VALUES ($1, $2, $3, $4, $5)",
                           session.id, key, pickle, session.creation_time, session.use_time)

    async def update_session(self, key: IdentityKey, session: Session) -> None:
        pickle = session.pickle(self.pickle_key)
        await self.execute("UPDATE crypto_olm_session SET session=$1, last_used=$2 "
                           "WHERE session_id=$3", pickle, session.use_time, session.id)

    async def put_group_session(self, room_id: RoomID, sender_key: IdentityKey,
                                session_id: SessionID, session: InboundGroupSession) -> None:
        pickle = session.pickle(self.pickle_key)
        forwarding_chains = ",".join(session.forwarding_chain)
        await self.execute("INSERT INTO crypto_megolm_inbound_session (session_id, sender_key, "
                           "signing_key, room_id, session, forwarding_chains) "
                           "VALUES ($1, $2, $3, $4, $5, $6)",
                           session_id, sender_key, session.signing_key, room_id, pickle,
                           forwarding_chains)

    async def get_group_session(self, room_id: RoomID, sender_key: IdentityKey,
                                session_id: SessionID) -> Optional[InboundGroupSession]:
        row = await self.fetchrow("SELECT signing_key, session, forwarding_chains "
                                  "FROM crypto_megolm_inbound_session "
                                  "WHERE room_id=$1 AND sender_key=$2 AND session_id=$3",
                                  room_id, sender_key, session_id)
        if row is None:
            return None
        return InboundGroupSession.from_pickle(row["session"], passphrase=self.pickle_key,
                                               signing_key=row["signing_key"],
                                               sender_key=sender_key, room_id=room_id,
                                               forwarding_chain=row["forwarding_chains"].split(","))

    async def add_outbound_group_session(self, session: OutboundGroupSession) -> None:
        pickle = session.pickle(self.pickle_key)
        await self.execute("INSERT INTO crypto_megolm_outbound_session (room_id, session_id, "
                           "session, shared, max_messages, message_count, max_age, created_at, "
                           "last_used) "
                           "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)"
                           "ON CONFLICT (room_id) DO UPDATE SET session_id=$2, session=$3, "
                           "shared=$4, max_messages=$5, message_count=$6, max_age=$7, "
                           "created_at=$8, last_used=$9",
                           session.room_id, session.id, pickle, session.shared,
                           session.max_messages, session.message_count, session.max_age,
                           session.creation_time, session.use_time)

    async def update_outbound_group_session(self, session: OutboundGroupSession) -> None:
        pickle = session.pickle(self.pickle_key)
        await self.execute("UPDATE crypto_megolm_outbound_session "
                           "SET session=$1, message_count=$2, last_used=$3 "
                           "WHERE room_id=$4 AND session_id=$5",
                           pickle, session.message_count, session.use_time, session.room_id,
                           session.id)

    async def get_outbound_group_session(self, room_id: RoomID) -> Optional[OutboundGroupSession]:
        row = await self.fetchrow("SELECT room_id, session_id, session, shared, max_messages, "
                                  "message_count, max_age, created_at, last_used "
                                  "FROM crypto_megolm_outbound_session WHERE room_id=$1",
                                  room_id)
        if row is None:
            return None
        return OutboundGroupSession.from_pickle(row["session"], passphrase=self.pickle_key,
                                                room_id=row["room_id"], shared=row["shared"],
                                                max_messages=row["max_messages"],
                                                message_count=row["message_count"],
                                                max_age=row["max_age"], use_time=row["last_used"],
                                                creation_time=row["created_at"])

    async def remove_outbound_group_session(self, room_id: RoomID) -> None:
        await self.execute("DELETE FROM crypto_megolm_outbound_session WHERE room_id=$1",
                           room_id)

    async def validate_message_index(self, sender_key: IdentityKey, session_id: SessionID,
                                     event_id: EventID, index: int, timestamp: int) -> bool:
        row = await self.fetchrow("SELECT event_id, timestamp FROM crypto_message_index "
                                  'WHERE sender_key=$1 AND session_id=$2 AND "index"=$3',
                                  sender_key, session_id, index)
        if row is None:
            await self.execute("INSERT INTO crypto_message_index (sender_key, session_id, index,"
                               " event_id, timestamp) VALUES ($1, $2, $3, $4, $5)",
                               sender_key, session_id, index, event_id, timestamp)
            return True
        return row["event_id"] == event_id and row["timestamp"] == timestamp

    async def get_devices(self, user_id: UserID) -> Optional[Dict[DeviceID, DeviceIdentity]]:
        tracked_user_id = await self.fetchval("SELECT user_id FROM crypto_tracked_user "
                                              "WHERE user_id=$1", user_id)
        if tracked_user_id is None:
            return None
        rows = await self.fetch("SELECT device_id, identity_key, signing_key, trust, deleted, "
                                "name FROM crypto_device WHERE user_id=$1", user_id)
        result = {}
        for row in rows:
            result[row["device_id"]] = DeviceIdentity(user_id=user_id, device_id=row["device_id"],
                                                      identity_key=row["identity_key"],
                                                      signing_key=row["signing_key"],
                                                      trust=TrustState(row["trust"]),
                                                      deleted=row["deleted"], name=row["name"])
        return result

    async def get_device(self, user_id: UserID, device_id: DeviceID) -> Optional[DeviceIdentity]:
        row = await self.fetchrow("SELECT identity_key, signing_key, trust, deleted, name "
                                  "FROM crypto_device WHERE user_id=$1 AND device_id=$2",
                                  user_id, device_id)
        if row is None:
            return None
        return DeviceIdentity(user_id=user_id, device_id=device_id, name=row["name"],
                              identity_key=row["identity_key"], signing_key=row["signing_key"],
                              trust=TrustState(row["trust"]), deleted=row["deleted"])

    async def put_devices(self, user_id: UserID, devices: Dict[DeviceID, DeviceIdentity]) -> None:
        data = [
            (user_id, device_id, identity.identity_key, identity.signing_key,
             identity.trust, identity.deleted, identity.name)
            for device_id, identity in devices.items()
        ]
        columns = ["user_id", "device_id", "identity_key", "signing_key",
                   "trust", "deleted", "name"]
        async with self.acquire() as conn, conn.transaction():
            await conn.execute("INSERT INTO crypto_tracked_user (user_id) VALUES ($1) "
                               "ON CONFLICT (user_id) DO NOTHING", user_id)
            await conn.execute("DELETE FROM crypto_device WHERE user_id=$1", user_id)
            await conn.copy_records_to_table("crypto_device", records=data, columns=columns)

    async def filter_tracked_users(self, users: List[UserID]) -> List[UserID]:
        rows = await self.fetch("SELECT user_id FROM crypto_tracked_user "
                                "WHERE user_id = ANY($1)", users)
        return [row["user_id"] for row in rows]
