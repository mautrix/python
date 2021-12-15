# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import cast
from collections import defaultdict
from datetime import timedelta

from mautrix.client.state_store import SyncStore
from mautrix.client.state_store.asyncpg import PgStateStore
from mautrix.types import DeviceID, EventID, IdentityKey, RoomID, SessionID, SyncToken, UserID
from mautrix.util.async_db import Database
from mautrix.util.logging import TraceLogger

from ... import (
    DeviceIdentity,
    InboundGroupSession,
    OlmAccount,
    OutboundGroupSession,
    Session,
    TrustState,
)
from ..abstract import CryptoStore, StateStore
from .upgrade import upgrade_table


class PgCryptoStateStore(PgStateStore, StateStore):
    """
    This class ensures that the PgStateStore in the client module implements the StateStore
    methods needed by the crypto module.
    """


class PgCryptoStore(CryptoStore, SyncStore):
    upgrade_table = upgrade_table

    db: Database
    account_id: str
    pickle_key: str
    log: TraceLogger

    _sync_token: SyncToken | None
    _device_id: DeviceID | None
    _account: OlmAccount | None
    _olm_cache: dict[IdentityKey, dict[SessionID, Session]]

    def __init__(self, account_id: str, pickle_key: str, db: Database) -> None:
        self.db = db
        self.account_id = account_id
        self.pickle_key = pickle_key

        self._sync_token = None
        self._device_id = DeviceID("")
        self._account = None
        self._olm_cache = defaultdict(lambda: {})

    async def delete(self) -> None:
        tables = ("crypto_account", "crypto_olm_session", "crypto_megolm_outbound_session")
        async with self.db.acquire() as conn, conn.transaction():
            for table in tables:
                await conn.execute(f"DELETE FROM {table} WHERE account_id=$1", self.account_id)

    async def get_device_id(self) -> DeviceID | None:
        device_id = await self.db.fetchval(
            "SELECT device_id FROM crypto_account WHERE account_id=$1", self.account_id
        )
        self._device_id = device_id or self._device_id
        return self._device_id

    async def put_device_id(self, device_id: DeviceID) -> None:
        await self.db.fetchval(
            "UPDATE crypto_account SET device_id=$1 WHERE account_id=$2",
            device_id,
            self.account_id,
        )
        self._device_id = device_id

    async def put_next_batch(self, next_batch: SyncToken) -> None:
        self._sync_token = next_batch
        await self.db.execute(
            "UPDATE crypto_account SET sync_token=$1 WHERE account_id=$2",
            self._sync_token,
            self.account_id,
        )

    async def get_next_batch(self) -> SyncToken:
        if self._sync_token is None:
            self._sync_token = await self.db.fetchval(
                "SELECT sync_token FROM crypto_account WHERE account_id=$1", self.account_id
            )
        return self._sync_token

    async def put_account(self, account: OlmAccount) -> None:
        self._account = account
        pickle = account.pickle(self.pickle_key)
        await self.db.execute(
            "INSERT INTO crypto_account (account_id, device_id, shared, "
            "sync_token, account) VALUES($1, $2, $3, $4, $5) "
            "ON CONFLICT (account_id) DO UPDATE SET shared=$3, sync_token=$4,"
            "                                       account=$5",
            self.account_id,
            self._device_id,
            account.shared,
            self._sync_token or "",
            pickle,
        )

    async def get_account(self) -> OlmAccount:
        if self._account is None:
            row = await self.db.fetchrow(
                "SELECT shared, account, device_id FROM crypto_account WHERE account_id=$1",
                self.account_id,
            )
            if row is not None:
                self._account = OlmAccount.from_pickle(
                    row["account"], passphrase=self.pickle_key, shared=row["shared"]
                )
        return self._account

    async def has_session(self, key: IdentityKey) -> bool:
        if len(self._olm_cache[key]) > 0:
            return True
        val = await self.db.fetchval(
            "SELECT session_id FROM crypto_olm_session WHERE sender_key=$1 AND account_id=$2",
            key,
            self.account_id,
        )
        return val is not None

    async def get_sessions(self, key: IdentityKey) -> list[Session]:
        rows = await self.db.fetch(
            "SELECT session_id, session, created_at, last_used FROM crypto_olm_session "
            "WHERE sender_key=$1 AND account_id=$2 ORDER BY session_id",
            key,
            self.account_id,
        )
        sessions = []
        for row in rows:
            try:
                sess = self._olm_cache[key][row["session_id"]]
            except KeyError:
                sess = Session.from_pickle(
                    row["session"],
                    passphrase=self.pickle_key,
                    creation_time=row["created_at"],
                    use_time=row["last_used"],
                )
            sessions.append(sess)
        return sessions

    async def get_latest_session(self, key: IdentityKey) -> Session | None:
        row = await self.db.fetchrow(
            "SELECT session_id, session, created_at, last_used FROM crypto_olm_session "
            "WHERE sender_key=$1 AND account_id=$2 ORDER BY session_id DESC LIMIT 1",
            key,
            self.account_id,
        )
        if row is None:
            return None
        try:
            return self._olm_cache[key][row["session_id"]]
        except KeyError:
            return Session.from_pickle(
                row["session"],
                passphrase=self.pickle_key,
                creation_time=row["created_at"],
                use_time=row["last_used"],
            )

    async def add_session(self, key: IdentityKey, session: Session) -> None:
        pickle = session.pickle(self.pickle_key)
        self._olm_cache[key][cast(SessionID, session.id)] = session
        await self.db.execute(
            "INSERT INTO crypto_olm_session (session_id, sender_key, session, "
            "created_at, last_used, account_id) VALUES ($1, $2, $3, $4, $5, $6)",
            session.id,
            key,
            pickle,
            session.creation_time,
            session.use_time,
            self.account_id,
        )

    async def update_session(self, key: IdentityKey, session: Session) -> None:
        pickle = session.pickle(self.pickle_key)
        await self.db.execute(
            "UPDATE crypto_olm_session SET session=$1, last_used=$2 "
            "WHERE session_id=$3 AND account_id=$4",
            pickle,
            session.use_time,
            session.id,
            self.account_id,
        )

    async def put_group_session(
        self,
        room_id: RoomID,
        sender_key: IdentityKey,
        session_id: SessionID,
        session: InboundGroupSession,
    ) -> None:
        pickle = session.pickle(self.pickle_key)
        forwarding_chains = ",".join(session.forwarding_chain)
        await self.db.execute(
            "INSERT INTO crypto_megolm_inbound_session (session_id, sender_key, "
            "signing_key, room_id, session, forwarding_chains, account_id) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7)",
            session_id,
            sender_key,
            session.signing_key,
            room_id,
            pickle,
            forwarding_chains,
            self.account_id,
        )

    async def get_group_session(
        self, room_id: RoomID, sender_key: IdentityKey, session_id: SessionID
    ) -> InboundGroupSession | None:
        row = await self.db.fetchrow(
            "SELECT signing_key, session, forwarding_chains FROM crypto_megolm_inbound_session "
            "WHERE room_id=$1 AND sender_key=$2 AND session_id=$3 AND account_id=$4",
            room_id,
            sender_key,
            session_id,
            self.account_id,
        )
        if row is None:
            return None
        return InboundGroupSession.from_pickle(
            row["session"],
            passphrase=self.pickle_key,
            signing_key=row["signing_key"],
            sender_key=sender_key,
            room_id=room_id,
            forwarding_chain=row["forwarding_chains"].split(","),
        )

    async def has_group_session(
        self, room_id: RoomID, sender_key: IdentityKey, session_id: SessionID
    ) -> bool:
        count = await self.db.fetchval(
            "SELECT COUNT(session) FROM crypto_megolm_inbound_session "
            "WHERE room_id=$1 AND sender_key=$2 AND session_id=$3 AND account_id=$4",
            room_id,
            sender_key,
            session_id,
            self.account_id,
        )
        return count > 0

    async def add_outbound_group_session(self, session: OutboundGroupSession) -> None:
        pickle = session.pickle(self.pickle_key)
        max_age = session.max_age
        if self.db.scheme == "sqlite":
            max_age = max_age.total_seconds()
        await self.db.execute(
            "INSERT INTO crypto_megolm_outbound_session (room_id, session_id, session, shared, "
            "max_messages, message_count, max_age, created_at, last_used, account_id) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)"
            "ON CONFLICT (account_id, room_id) DO UPDATE SET session_id=$2, session=$3, shared=$4,"
            " max_messages=$5, message_count=$6, max_age=$7, created_at=$8, last_used=$9",
            session.room_id,
            session.id,
            pickle,
            session.shared,
            session.max_messages,
            session.message_count,
            max_age,
            session.creation_time,
            session.use_time,
            self.account_id,
        )

    async def update_outbound_group_session(self, session: OutboundGroupSession) -> None:
        pickle = session.pickle(self.pickle_key)
        await self.db.execute(
            "UPDATE crypto_megolm_outbound_session SET session=$1, message_count=$2, last_used=$3 "
            "WHERE room_id=$4 AND session_id=$5 AND account_id=$6",
            pickle,
            session.message_count,
            session.use_time,
            session.room_id,
            session.id,
            self.account_id,
        )

    async def get_outbound_group_session(self, room_id: RoomID) -> OutboundGroupSession | None:
        row = await self.db.fetchrow(
            "SELECT room_id, session_id, session, shared, max_messages, message_count, max_age, "
            "       created_at, last_used "
            "FROM crypto_megolm_outbound_session WHERE room_id=$1 AND account_id=$2",
            room_id,
            self.account_id,
        )
        if row is None:
            return None
        max_age = row["max_age"]
        if self.db.scheme == "sqlite":
            max_age = timedelta(seconds=max_age)
        return OutboundGroupSession.from_pickle(
            row["session"],
            passphrase=self.pickle_key,
            room_id=row["room_id"],
            shared=row["shared"],
            max_messages=row["max_messages"],
            message_count=row["message_count"],
            max_age=max_age,
            use_time=row["last_used"],
            creation_time=row["created_at"],
        )

    async def remove_outbound_group_session(self, room_id: RoomID) -> None:
        await self.db.execute(
            "DELETE FROM crypto_megolm_outbound_session WHERE room_id=$1 AND account_id=$2",
            room_id,
            self.account_id,
        )

    async def remove_outbound_group_sessions(self, rooms: list[RoomID]) -> None:
        if self.db.scheme == "postgres":
            await self.db.execute(
                "DELETE FROM crypto_megolm_outbound_session "
                "WHERE account_id=$1 AND room_id=ANY($2)",
                self.account_id,
                rooms,
            )
        else:
            params = ",".join(["?"] * len(rooms))
            await self.db.execute(
                "DELETE FROM crypto_megolm_outbound_session "
                f"WHERE account_id=? AND room_id IN ({params})",
                self.account_id,
                *rooms,
            )

    _validate_message_index_query = (
        "WITH existing AS ("
        " INSERT INTO crypto_message_index(sender_key, session_id, index, event_id, timestamp)"
        " VALUES ($1, $2, $3, $4, $5)"
        # have to update something so that RETURNING * always returns the row
        " ON CONFLICT (sender_key, session_id, index) DO UPDATE SET sender_key=$1"
        " RETURNING *"
        ")"
        "SELECT * FROM existing"
    )

    async def validate_message_index(
        self,
        sender_key: IdentityKey,
        session_id: SessionID,
        event_id: EventID,
        index: int,
        timestamp: int,
    ) -> bool:
        if self.db.scheme == "postgres":
            row = await self.db.fetchrow(
                self._validate_message_index_query,
                sender_key,
                session_id,
                index,
                event_id,
                timestamp,
            )
            return row["event_id"] == event_id and row["timestamp"] == timestamp
        else:
            row = await self.db.fetchrow(
                "SELECT event_id, timestamp FROM crypto_message_index "
                'WHERE sender_key=$1 AND session_id=$2 AND "index"=$3',
                sender_key,
                session_id,
                index,
            )
            if row is not None:
                return row["event_id"] == event_id and row["timestamp"] == timestamp
            await self.db.execute(
                "INSERT INTO crypto_message_index(sender_key, session_id, "
                '                                 "index", event_id, timestamp) '
                "VALUES ($1, $2, $3, $4, $5)",
                sender_key,
                session_id,
                index,
                event_id,
                timestamp,
            )
            return True

    async def get_devices(self, user_id: UserID) -> dict[DeviceID, DeviceIdentity] | None:
        tracked_user_id = await self.db.fetchval(
            "SELECT user_id FROM crypto_tracked_user WHERE user_id=$1", user_id
        )
        if tracked_user_id is None:
            return None
        rows = await self.db.fetch(
            "SELECT device_id, identity_key, signing_key, trust, deleted, "
            "name FROM crypto_device WHERE user_id=$1",
            user_id,
        )
        result = {}
        for row in rows:
            result[row["device_id"]] = DeviceIdentity(
                user_id=user_id,
                device_id=row["device_id"],
                identity_key=row["identity_key"],
                signing_key=row["signing_key"],
                trust=TrustState(row["trust"]),
                deleted=row["deleted"],
                name=row["name"],
            )
        return result

    async def get_device(self, user_id: UserID, device_id: DeviceID) -> DeviceIdentity | None:
        row = await self.db.fetchrow(
            "SELECT identity_key, signing_key, trust, deleted, name "
            "FROM crypto_device WHERE user_id=$1 AND device_id=$2",
            user_id,
            device_id,
        )
        if row is None:
            return None
        return DeviceIdentity(
            user_id=user_id,
            device_id=device_id,
            name=row["name"],
            identity_key=row["identity_key"],
            signing_key=row["signing_key"],
            trust=TrustState(row["trust"]),
            deleted=row["deleted"],
        )

    async def find_device_by_key(
        self, user_id: UserID, identity_key: IdentityKey
    ) -> DeviceIdentity | None:
        row = await self.db.fetchrow(
            "SELECT device_id, signing_key, trust, deleted, name "
            "FROM crypto_device WHERE user_id=$1 AND identity_key=$2",
            user_id,
            identity_key,
        )
        if row is None:
            return None
        return DeviceIdentity(
            user_id=user_id,
            device_id=row["device_id"],
            name=row["name"],
            identity_key=identity_key,
            signing_key=row["signing_key"],
            trust=TrustState(row["trust"]),
            deleted=row["deleted"],
        )

    async def put_devices(self, user_id: UserID, devices: dict[DeviceID, DeviceIdentity]) -> None:
        data = [
            (
                user_id,
                device_id,
                identity.identity_key,
                identity.signing_key,
                identity.trust,
                identity.deleted,
                identity.name,
            )
            for device_id, identity in devices.items()
        ]
        columns = [
            "user_id",
            "device_id",
            "identity_key",
            "signing_key",
            "trust",
            "deleted",
            "name",
        ]
        async with self.db.acquire() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO crypto_tracked_user (user_id) VALUES ($1) "
                "ON CONFLICT (user_id) DO NOTHING",
                user_id,
            )
            await conn.execute("DELETE FROM crypto_device WHERE user_id=$1", user_id)
            if self.db.scheme == "postgres":
                await conn.copy_records_to_table("crypto_device", records=data, columns=columns)
            else:
                await conn.executemany(
                    "INSERT INTO crypto_device (user_id, device_id, "
                    "identity_key, signing_key, trust, deleted, name) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                    data,
                )

    async def filter_tracked_users(self, users: list[UserID]) -> list[UserID]:
        if self.db.scheme == "postgres":
            rows = await self.db.fetch(
                "SELECT user_id FROM crypto_tracked_user WHERE user_id = ANY($1)", users
            )
        else:
            params = ",".join(["?"] * len(users))
            rows = await self.db.fetch(
                f"SELECT user_id FROM crypto_tracked_user WHERE user_id IN ({params})", *users
            )
        return [row["user_id"] for row in rows]
