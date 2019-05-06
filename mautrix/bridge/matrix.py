# Copyright (c) 2019 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Tuple, Optional, TYPE_CHECKING
from abc import ABC, abstractmethod
import logging
import asyncio

from mautrix.types import (EventID, RoomID, UserID, Event, EventType, MessageEvent, MessageType,
                           MessageEventContent, StateEvent, Membership, MemberStateEventContent)
from mautrix.errors import IntentError, MatrixError
from mautrix.appservice import AppService

from .commands import CommandProcessor

if TYPE_CHECKING:
    from .config import BaseBridgeConfig
    from .user import BaseUser
    from .portal import BasePortal
    from .puppet import BasePuppet


class BaseMatrixHandler(ABC):
    log: logging.Logger = logging.getLogger("mau.mx")
    commands: CommandProcessor

    def __init__(self, az: AppService, config: 'BaseBridgeConfig',
                 command_processor: Optional[CommandProcessor] = None,
                 loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        self.az = az
        self.config = config
        self.commands = command_processor or CommandProcessor(az=az, config=config, loop=loop)
        self.az.matrix_event_handler(self.int_handle_event)

    async def init_as_bot(self) -> None:
        self.log.debug("Initializing appservice bot")
        displayname = self.config["appservice.bot_displayname"]
        if displayname:
            try:
                await self.az.intent.set_displayname(
                    displayname if displayname != "remove" else "")
            except asyncio.TimeoutError:
                self.log.exception("TimeoutError when trying to set displayname")

        avatar = self.config["appservice.bot_avatar"]
        if avatar:
            try:
                await self.az.intent.set_avatar_url(avatar if avatar != "remove" else "")
            except asyncio.TimeoutError:
                self.log.exception("TimeoutError when trying to set avatar")

    @abstractmethod
    async def get_user(self, user_id: UserID) -> 'BaseUser':
        pass

    @abstractmethod
    async def get_portal(self, room_id: RoomID) -> 'BasePortal':
        pass

    @abstractmethod
    async def get_puppet(self, user_id: UserID) -> 'BasePuppet':
        pass

    async def handle_leave(self, room_id: RoomID, user_id: UserID) -> None:
        pass

    async def handle_kick(self, room_id: RoomID, user_id: UserID, kicked_by: UserID, reason: str
                          ) -> None:
        pass

    async def handle_ban(self, room_id: RoomID, user_id: UserID, banned_by: UserID, reason: str
                         ) -> None:
        pass

    async def handle_join(self, room_id: RoomID, user_id: UserID) -> None:
        pass

    async def handle_member_info_change(self, room_id: RoomID, user_id: UserID,
                                        content: MemberStateEventContent,
                                        prev_content: MemberStateEventContent) -> None:
        pass

    async def handle_puppet_invite(self, room_id: RoomID, puppet: 'BasePuppet',
                                   invited_by: 'BaseUser') -> None:
        pass

    async def handle_invite(self, room_id: RoomID, user_id: UserID, invited_by: 'BaseUser') -> None:
        pass

    async def handle_event(self, evt: Event) -> None:
        """Called by :meth:`int_handle_event` for non-message/membership events."""

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

        if not inviter.is_whitelisted:
            await self.send_permission_error(room_id)
            await self.az.intent.leave_room(room_id)

    async def int_handle_invite(self, room_id: RoomID, user_id: UserID, invited_by: UserID
                                ) -> None:
        self.log.debug(f"{invited_by} invited {user_id} to {room_id}")
        inviter = await self.get_user(invited_by)
        if inviter is None:
            self.log.exception(f"Failed to find user with Matrix ID {invited_by}")
            return
        elif user_id == self.az.bot_mxid:
            await self.accept_bot_invite(room_id, inviter)
            return
        elif not inviter.is_whitelisted:
            return

        puppet = await self.get_puppet(user_id)
        if puppet:
            await self.handle_puppet_invite(room_id, puppet, inviter)
            return

        await self.handle_invite(room_id, user_id, inviter)

    def is_command(self, message: MessageEventContent) -> Tuple[bool, str]:
        text = message.body
        prefix = self.config["bridge.command_prefix"]
        is_command = text.startswith(prefix)
        if is_command:
            text = text[len(prefix) + 1:]
        return is_command, text

    async def handle_message(self, room_id: RoomID, user_id: UserID, message: MessageEventContent,
                             event_id: EventID) -> None:
        sender = await self.get_user(user_id)
        if not sender or not sender.is_whitelisted:
            self.log.debug(f"Ignoring message \"{message}\" from {sender.mxid} to {room_id}:"
                           " User is not whitelisted.")
            return
        self.log.debug(f"Received Matrix event \"{message}\" from {sender.mxid} in {room_id}")

        is_command, text = self.is_command(message)
        portal = await self.get_portal(room_id)
        if not is_command and portal and await sender.is_logged_in():
            await portal.handle_matrix_message(sender, message, event_id)
            return

        if message.msgtype != MessageType.TEXT:
            return

        try:
            is_management = len(await self.az.intent.get_room_members(room_id)) == 2
        except MatrixError:
            # The AS bot is not in the room.
            return

        if is_command or is_management:
            try:
                command, arguments = text.split(" ", 1)
                args = arguments.split(" ")
            except ValueError:
                # Not enough values to unpack, i.e. no arguments
                command = text
                args = []
            await self.commands.handle(room_id, event_id, sender, command, args, is_management,
                                       is_portal=portal is not None)

    def filter_matrix_event(self, evt: Event) -> bool:
        if not isinstance(evt, (MessageEvent, StateEvent)):
            return False
        return evt.sender == self.az.bot_mxid

    async def try_handle_event(self, evt: Event) -> None:
        try:
            await self.int_handle_event(evt)
        except Exception:
            self.log.exception("Error handling manually received Matrix event")

    async def int_handle_event(self, evt: Event) -> None:
        if self.filter_matrix_event(evt):
            return
        self.log.debug("Received event: %s", evt)

        if evt.type == EventType.ROOM_MEMBER:
            evt: StateEvent
            prev_content = evt.unsigned.prev_content if evt.unsigned else None
            prev_membership = prev_content.membership if prev_content else Membership.JOIN
            if evt.content.membership == Membership.INVITE:
                await self.int_handle_invite(evt.room_id, UserID(evt.state_key), evt.sender)
            elif evt.content.membership == Membership.LEAVE:
                if evt.sender != evt.state_key:
                    await self.handle_kick(evt.room_id, UserID(evt.state_key), evt.sender,
                                           evt.content.reason)
                else:
                    await self.handle_leave(evt.room_id, UserID(evt.state_key))
            elif evt.content.membership == Membership.BAN:
                await self.handle_ban(evt.room_id, UserID(evt.state_key), evt.sender,
                                      evt.content.reason)
            elif evt.content.membership == Membership.JOIN:
                if prev_membership != Membership.JOIN:
                    await self.handle_join(evt.room_id, UserID(evt.state_key))
                else:
                    await self.handle_member_info_change(evt.room_id, UserID(evt.state_key),
                                                         evt.content, prev_content)
        elif evt.type in (EventType.ROOM_MESSAGE, EventType.STICKER):
            evt: MessageEvent
            if evt.type != EventType.ROOM_MESSAGE:
                evt.content.msgtype = MessageType(str(evt.type))
            await self.handle_message(evt.room_id, evt.sender, evt.content, evt.event_id)
        else:
            await self.handle_event(evt)
