# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Tuple, Union, Optional, List
import logging
import asyncio
import hashlib
import hmac

from nio import (AsyncClient, Event as NioEvent, GroupEncryptionError, LoginError,
                 MatrixRoom as NioRoom, RoomMemberEvent as NioMemberEvent, MatrixUser as NioUser,
                 AsyncClientConfig)

from mautrix.types import (Filter, RoomFilter, EventFilter, RoomEventFilter, StateFilter,
                           EventType, RoomID, Serializable, JSON, MessageEvent, Event, UserID,
                           EncryptedEvent, StateEvent, Membership)
from mautrix.bridge.db import UserProfile
from mautrix.bridge.db.nio_state_store import NioStore, DBAccount


class EncryptionManager:
    loop: asyncio.AbstractEventLoop
    log: logging.Logger = logging.getLogger("mau.e2ee")
    client: AsyncClient

    bot_mxid: UserID
    login_shared_secret: bytes
    _id_prefix: str
    _id_suffix: str

    sync_task: asyncio.Task

    def __init__(self, bot_mxid: UserID, login_shared_secret: str, homeserver_address: str,
                 user_id_prefix: str, user_id_suffix: str, device_name: str,
                 loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        self.loop = loop or asyncio.get_event_loop()
        self.bot_mxid = bot_mxid
        self.device_name = device_name
        self._id_prefix = user_id_prefix
        self._id_suffix = user_id_suffix
        self.login_shared_secret = login_shared_secret.encode("utf-8")
        config = AsyncClientConfig(store=NioStore, encryption_enabled=True,
                                   pickle_key="mautrix-python", store_sync_tokens=True)
        device_id = DBAccount.first_device_id(self.bot_mxid)
        if device_id:
            self.log.debug(f"Found device ID in database: {device_id}")
        self.client = AsyncClient(homeserver=homeserver_address, user=bot_mxid,
                                  device_id=device_id, config=config, store_path="3:<")

    def _init_load_profiles(self) -> None:
        self.log.debug("Loading room and member list into encryption client")
        for profile in UserProfile.all_except(self._id_prefix, self._id_suffix, self.bot_mxid):
            try:
                room = self.client.rooms[profile.room_id]
            except KeyError:
                room = self.client.rooms[profile.room_id] = NioRoom(profile.room_id, self.bot_mxid,
                                                                    encrypted=True)
            user = NioUser(profile.user_id, profile.displayname, profile.avatar_url)
            if profile.membership == Membership.JOIN:
                room.users[profile.user_id] = user
            elif profile.membership == Membership.INVITE:
                room.invited_users[profile.user_id] = user

    def _ignore_user(self, user_id: str) -> bool:
        return (user_id.startswith(self._id_prefix) and user_id.endswith(self._id_suffix)
                and user_id != self.bot_mxid)

    async def handle_room_membership(self, evt: StateEvent) -> None:
        if self._ignore_user(evt.state_key):
            return
        try:
            room = self.client.rooms[evt.room_id]
        except KeyError:
            room = self.client.rooms[evt.room_id] = NioRoom(evt.room_id, self.bot_mxid,
                                                            encrypted=True)
            await self.client.joined_members(evt.room_id)
        nio_evt = NioMemberEvent.from_dict(evt.serialize())
        try:
            if room.handle_membership(nio_evt):
                self.client._invalidate_session_for_member_event(evt.room_id)
        except Exception:
            self.log.exception("matrix-nio failed to handle membership event")

    async def handle_room_encryption(self, evt: StateEvent) -> None:
        try:
            room = self.client.rooms[evt.room_id]
            room.encrypted = True
        except KeyError:
            self.client.rooms[evt.room_id] = NioRoom(evt.room_id, self.bot_mxid, encrypted=True)
            await self.client.joined_members(evt.room_id)

    async def add_room(self, room_id: RoomID, members: Optional[List[UserID]] = None,
                       encrypted: bool = False) -> None:
        if room_id in self.client.invited_rooms:
            del self.client.invited_rooms[room_id]
        try:
            room = self.client.rooms[room_id]
            room.encrypted = encrypted
        except KeyError:
            room = self.client.rooms[room_id] = NioRoom(room_id, self.bot_mxid, encrypted=True)
        if members:
            update = False
            for member in members:
                if not self._ignore_user(member):
                    update = room.add_member(member, "", "") or update
            if update:
                self.client._invalidate_session_for_member_event(room_id)
        else:
            await self.client.joined_members(room_id)

    async def encrypt(self, room_id: RoomID, event_type: EventType,
                      content: Union[Serializable, JSON]) -> Tuple[EventType, JSON]:
        serialized = content.serialize() if isinstance(content, Serializable) else content
        type_str = str(event_type)
        retries = 0
        while True:
            try:
                type_str, encrypted = self.client.encrypt(room_id, type_str, serialized)
                break
            except GroupEncryptionError:
                if retries > 3:
                    self.log.error("Got GroupEncryptionError again, giving up")
                    raise
                retries += 1
                self.log.debug("Got GroupEncryptionError, sharing group session and trying again")
                await self.client.share_group_session(room_id, ignore_unverified_devices=True)
        event_type = EventType.find(type_str)
        try:
            encrypted["m.relates_to"] = serialized["m.relates_to"]
        except KeyError:
            pass
        return event_type, encrypted

    def decrypt(self, event: EncryptedEvent) -> MessageEvent:
        serialized = event.serialize()
        event = self.client.decrypt_event(NioEvent.parse_encrypted_event(serialized))
        try:
            event.source["content"]["m.relates_to"] = serialized["content"]["m.relates_to"]
        except KeyError:
            pass
        return Event.deserialize(event.source)

    async def start(self) -> None:
        self.log.debug("Logging in with bridge bot user")
        password = hmac.new(self.login_shared_secret, self.bot_mxid.encode("utf-8"),
                            hashlib.sha512).hexdigest()
        resp = await self.client.login(password, device_name=self.device_name)
        if isinstance(resp, LoginError):
            raise Exception(f"Failed to log in with bridge bot: {resp}")
        self._init_load_profiles()
        self.sync_task = self.loop.create_task(self.client.sync_forever(
            timeout=30000, sync_filter=self._filter.serialize()))
        self.log.info("End-to-bridge encryption support is enabled")

    def stop(self) -> None:
        self.sync_task.cancel()

    @property
    def _filter(self) -> Filter:
        all_events = EventType.find("*")
        return Filter(
            account_data=EventFilter(types=[all_events]),
            presence=EventFilter(not_types=[all_events]),
            room=RoomFilter(
                include_leave=False,
                state=StateFilter(not_types=[all_events]),
                timeline=RoomEventFilter(not_types=[all_events]),
                account_data=RoomEventFilter(not_types=[all_events]),
                ephemeral=RoomEventFilter(not_types=[all_events]),
            ),
        )
