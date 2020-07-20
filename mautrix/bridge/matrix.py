# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Tuple, Optional, Union, TYPE_CHECKING
import logging
import asyncio
import os.path
import time

from yarl import URL

from mautrix.types import (EventID, RoomID, UserID, Event, EventType, MessageEvent, MessageType,
                           MessageEventContent, StateEvent, Membership, MemberStateEventContent,
                           PresenceEvent, TypingEvent, ReceiptEvent, TextMessageEventContent,
                           EncryptedEvent)
from mautrix.errors import IntentError, MatrixError, MForbidden
from mautrix.appservice import AppService
from mautrix.util.logging import TraceLogger

from .commands import CommandProcessor

if TYPE_CHECKING:
    from .config import BaseBridgeConfig
    from .user import BaseUser
    from .portal import BasePortal
    from .puppet import BasePuppet
    from .bridge import Bridge

try:
    from .e2ee import EncryptionManager
except ImportError:
    EncryptionManager = None


class BaseMatrixHandler:
    log: TraceLogger = logging.getLogger("mau.mx")
    az: AppService
    commands: CommandProcessor
    config: 'BaseBridgeConfig'
    bridge: 'Bridge'
    e2ee: Optional[EncryptionManager]

    user_id_prefix: str
    user_id_suffix: str

    def __init__(self, command_processor: Optional[CommandProcessor] = None,
                 bridge: Optional['Bridge'] = None) -> None:
        self.az = bridge.az
        self.config = bridge.config
        self.bridge = bridge
        self.commands = command_processor or CommandProcessor(bridge=bridge)
        self.az.matrix_event_handler(self.int_handle_event)

        self.e2ee = None
        if self.config["bridge.encryption.allow"]:
            if not EncryptionManager:
                self.log.error("Encryption enabled in config, but dependencies not installed.")
            elif not self.config["bridge.login_shared_secret"]:
                self.log.warning("Encryption enabled in config, but login_shared_secret not set.")
            else:
                self.e2ee = EncryptionManager(
                    az=bridge.az, device_name=bridge.name, loop=bridge.loop,
                    user_id_prefix=self.user_id_prefix, user_id_suffix=self.user_id_suffix,
                    login_shared_secret=self.config["bridge.login_shared_secret"],
                    homeserver_address=self.config["homeserver.address"],
                    db_url=self._get_db_url(bridge.config), get_portal=self.bridge.get_portal)

    @staticmethod
    def _get_db_url(config: 'BaseBridgeConfig') -> str:
        db_url = config["bridge.encryption.database"]
        if not db_url or db_url == "default":
            db_url = config["appservice.database"]
            parsed_url = URL(db_url)
            if parsed_url.scheme == "sqlite":
                # Remove the extension to replace it with our own
                path = os.path.splitext(parsed_url.path)[0]
                db_url = f"pickle://{path}.crypto.pickle"
        return db_url

    async def wait_for_connection(self) -> None:
        self.log.info("Ensuring connectivity to homeserver")
        errors = 0
        tried_to_register = False
        while True:
            try:
                await self.az.intent.whoami()
                break
            except MForbidden as e:
                if "has not registered this user" in e.message and not tried_to_register:
                    self.log.debug("Whoami endpoint returned M_FORBIDDEN, "
                                   "trying to register bridge bot before retrying...")
                    await self.az.intent.ensure_registered()
                    tried_to_register = True
                else:
                    raise
            except Exception:
                errors += 1
                if errors <= 6:
                    self.log.exception("Connection to homeserver failed, retrying in 10 seconds")
                    await asyncio.sleep(10)
                else:
                    raise

    async def init_as_bot(self) -> None:
        self.log.debug("Initializing appservice bot")
        displayname = self.config["appservice.bot_displayname"]
        if displayname:
            try:
                await self.az.intent.set_displayname(
                    displayname if displayname != "remove" else "")
            except Exception:
                self.log.exception("Failed to set bot displayname")

        avatar = self.config["appservice.bot_avatar"]
        if avatar:
            try:
                await self.az.intent.set_avatar_url(avatar if avatar != "remove" else "")
            except Exception:
                self.log.exception("Failed to set bot avatar")

    async def init_encryption(self) -> None:
        if self.e2ee:
            await self.e2ee.start()

    @staticmethod
    async def allow_message(user: 'BaseUser') -> bool:
        return user.is_whitelisted

    @staticmethod
    async def allow_command(user: 'BaseUser') -> bool:
        return user.is_whitelisted

    @staticmethod
    async def allow_bridging_message(user: 'BaseUser', portal: 'BasePortal') -> bool:
        return await user.is_logged_in()

    async def handle_leave(self, room_id: RoomID, user_id: UserID, event_id: EventID) -> None:
        pass

    async def handle_kick(self, room_id: RoomID, user_id: UserID, kicked_by: UserID, reason: str,
                          event_id: EventID) -> None:
        pass

    async def handle_ban(self, room_id: RoomID, user_id: UserID, banned_by: UserID, reason: str,
                         event_id: EventID) -> None:
        pass

    async def handle_unban(self, room_id: RoomID, user_id: UserID, unbanned_by: UserID,
                           reason: str, event_id: EventID) -> None:
        pass

    async def handle_join(self, room_id: RoomID, user_id: UserID, event_id: EventID) -> None:
        pass

    async def handle_member_info_change(self, room_id: RoomID, user_id: UserID,
                                        content: MemberStateEventContent,
                                        prev_content: MemberStateEventContent,
                                        event_id: EventID) -> None:
        pass

    async def handle_puppet_invite(self, room_id: RoomID, puppet: 'BasePuppet',
                                   invited_by: 'BaseUser', event_id: EventID) -> None:
        pass

    async def handle_invite(self, room_id: RoomID, user_id: UserID, inviter: 'BaseUser',
                            event_id: EventID) -> None:
        pass

    async def handle_reject(self, room_id: RoomID, user_id: UserID, reason: str, event_id: EventID
                            ) -> None:
        pass

    async def handle_disinvite(self, room_id: RoomID, user_id: UserID, disinvited_by: UserID,
                               reason: str, event_id: EventID) -> None:
        pass

    async def handle_event(self, evt: Event) -> None:
        """Called by :meth:`int_handle_event` for message events other than m.room.message."""

    async def handle_state_event(self, evt: StateEvent) -> None:
        """Called by :meth:`int_handle_event` for state events other than m.room.membership."""

    async def handle_ephemeral_event(self, evt: Union[ReceiptEvent, PresenceEvent, TypingEvent]
                                     ) -> None:
        pass

    async def send_permission_error(self, room_id: RoomID) -> None:
        await self.az.intent.send_notice(
            room_id,
            text="You are not whitelisted to use this bridge.\n\n"
                 "If you are the owner of this bridge, see the bridge.permissions "
                 "section in your config file.",
            html="<p>You are not whitelisted to use this bridge.</p>"
                 "<p>If you are the owner of this bridge, see the "
                 "<code>bridge.permissions</code> section in your config file.</p>")

    async def accept_bot_invite(self, room_id: RoomID, inviter: 'BaseUser') -> None:
        tries = 0
        while tries < 5:
            try:
                await self.az.intent.join_room(room_id)
                break
            except (IntentError, MatrixError):
                tries += 1
                wait_for_seconds = (tries + 1) * 10
                if tries < 5:
                    self.log.exception(f"Failed to join room {room_id} with bridge bot, "
                                       f"retrying in {wait_for_seconds} seconds...")
                    await asyncio.sleep(wait_for_seconds)
                else:
                    self.log.exception(f"Failed to join room {room_id}, giving up.")
                    return

        if not await self.allow_command(inviter):
            await self.send_permission_error(room_id)
            await self.az.intent.leave_room(room_id)
            return

        await self.send_welcome_message(room_id, inviter)

    async def send_welcome_message(self, room_id: RoomID, inviter: 'BaseUser') -> None:
        await self.az.intent.send_notice(
            room_id=room_id,
            text=f"Hello, I'm a bridge bot. Use `{self.commands.command_prefix} help` for help.",
            html=f"Hello, I'm a bridge bot. Use <code>{self.commands.command_prefix} help</code> "
                 f"for help.")

    async def int_handle_invite(self, room_id: RoomID, user_id: UserID, invited_by: UserID,
                                event_id: EventID) -> None:
        self.log.debug(f"{invited_by} invited {user_id} to {room_id}")
        inviter = await self.bridge.get_user(invited_by)
        if inviter is None:
            self.log.exception(f"Failed to find user with Matrix ID {invited_by}")
            return
        elif user_id == self.az.bot_mxid:
            await self.accept_bot_invite(room_id, inviter)
            return
        elif not await self.allow_command(inviter):
            return

        puppet = await self.bridge.get_puppet(user_id)
        if puppet:
            await self.handle_puppet_invite(room_id, puppet, inviter, event_id)
            return

        await self.handle_invite(room_id, user_id, inviter, event_id)

    def is_command(self, message: MessageEventContent) -> Tuple[bool, str]:
        text = message.body
        prefix = self.config["bridge.command_prefix"]
        is_command = text.startswith(prefix)
        if is_command:
            text = text[len(prefix) + 1:].lstrip()
        return is_command, text

    async def handle_message(self, room_id: RoomID, user_id: UserID, message: MessageEventContent,
                             event_id: EventID) -> None:
        sender = await self.bridge.get_user(user_id)
        if not sender or not await self.allow_message(sender):
            self.log.debug(f"Ignoring message {event_id} from {user_id} to {room_id}:"
                           " User is not whitelisted.")
            return
        self.log.debug(f"Received Matrix event {event_id} from {sender.mxid} in {room_id}")
        self.log.trace("Event %s content: %s", event_id, message)

        if isinstance(message, TextMessageEventContent):
            message.trim_reply_fallback()

        is_command, text = self.is_command(message)
        portal = await self.bridge.get_portal(room_id)
        if not is_command and portal and await self.allow_bridging_message(sender, portal):
            await portal.handle_matrix_message(sender, message, event_id)
            return

        if message.msgtype != MessageType.TEXT or not await self.allow_command(sender):
            return

        is_management = await self.is_management(room_id)

        if is_command or is_management:
            try:
                command, arguments = text.split(" ", 1)
                args = arguments.split(" ")
            except ValueError:
                # Not enough values to unpack, i.e. no arguments
                command = text
                args = []
            await self.commands.handle(room_id, event_id, sender, command, args, message,
                                       is_management, is_portal=portal is not None)

    async def is_management(self, room_id: RoomID) -> bool:
        try:
            members = await self.az.intent.get_room_members(room_id)
            return len(members) == 2 and self.az.bot_mxid in members
        except MatrixError:
            return False

    def filter_matrix_event(self, evt: Event) -> bool:
        if not isinstance(evt, (MessageEvent, StateEvent)):
            return False
        return evt.sender == self.az.bot_mxid

    async def try_handle_sync_event(self, evt: Event) -> None:
        try:
            if isinstance(evt, (ReceiptEvent, PresenceEvent, TypingEvent)):
                await self.handle_ephemeral_event(evt)
            else:
                self.log.trace("Unknown event type received from sync: %s", evt)
        except Exception:
            self.log.exception("Error handling manually received Matrix event")

    async def handle_encrypted(self, evt: EncryptedEvent) -> None:
        await self.int_handle_event(await self.e2ee.decrypt(evt))

    async def handle_encryption(self, evt: StateEvent) -> None:
        await self.az.state_store.set_encryption_info(evt.room_id, evt.content)
        portal = await self.bridge.get_portal(evt.room_id)
        if portal.encrypted:
            portal.encrypted = True
            await portal.save()

    async def int_handle_event(self, evt: Event) -> None:
        if isinstance(evt, StateEvent) and evt.type == EventType.ROOM_MEMBER and self.e2ee:
            await self.e2ee.handle_member_event(evt)
        if self.filter_matrix_event(evt):
            return
        self.log.trace("Received event: %s", evt)
        start_time = time.time()

        if evt.type == EventType.ROOM_MEMBER:
            evt: StateEvent
            prev_content = evt.unsigned.prev_content or MemberStateEventContent()
            prev_membership = prev_content.membership if prev_content else Membership.JOIN
            if evt.content.membership == Membership.INVITE:
                await self.int_handle_invite(evt.room_id, UserID(evt.state_key), evt.sender,
                                             evt.event_id)
            elif evt.content.membership == Membership.LEAVE:
                if prev_membership == Membership.BAN:
                    await self.handle_unban(evt.room_id, UserID(evt.state_key), evt.sender,
                                            evt.content.reason, evt.event_id)
                elif prev_membership == Membership.INVITE:
                    if evt.sender == evt.state_key:
                        await self.handle_reject(evt.room_id, UserID(evt.state_key),
                                                 evt.content.reason, evt.event_id)
                    else:
                        await self.handle_disinvite(evt.room_id, UserID(evt.state_key), evt.sender,
                                                    evt.content.reason, evt.event_id)
                elif evt.sender == evt.state_key:
                    await self.handle_leave(evt.room_id, UserID(evt.state_key), evt.event_id)
                else:
                    await self.handle_kick(evt.room_id, UserID(evt.state_key), evt.sender,
                                           evt.content.reason, evt.event_id)
            elif evt.content.membership == Membership.BAN:
                await self.handle_ban(evt.room_id, UserID(evt.state_key), evt.sender,
                                      evt.content.reason, evt.event_id)
            elif evt.content.membership == Membership.JOIN:
                if prev_membership != Membership.JOIN:
                    await self.handle_join(evt.room_id, UserID(evt.state_key), evt.event_id)
                else:
                    await self.handle_member_info_change(evt.room_id, UserID(evt.state_key),
                                                         evt.content, prev_content, evt.event_id)
        elif evt.type in (EventType.ROOM_MESSAGE, EventType.STICKER):
            evt: MessageEvent
            if evt.type != EventType.ROOM_MESSAGE:
                evt.content.msgtype = MessageType(str(evt.type))
            await self.handle_message(evt.room_id, evt.sender, evt.content, evt.event_id)
        elif evt.type == EventType.ROOM_ENCRYPTED and self.e2ee:
            await self.handle_encrypted(evt)
        elif evt.type == EventType.ROOM_ENCRYPTION:
            await self.handle_encryption(evt)
        else:
            if evt.type.is_state and isinstance(evt, StateEvent):
                await self.handle_state_event(evt)
            else:
                await self.handle_event(evt)

        await self.log_event_handle_duration(evt, time.time() - start_time)

    async def log_event_handle_duration(self, evt: Event, duration: float) -> None:
        pass
