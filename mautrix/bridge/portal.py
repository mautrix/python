# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any, NamedTuple
from abc import ABC, abstractmethod
from collections import defaultdict
from string import Template
import asyncio
import html
import logging
import time

from mautrix.appservice import AppService, IntentAPI
from mautrix.errors import MatrixError, MatrixRequestError, MForbidden, MNotFound
from mautrix.types import (
    JSON,
    EncryptionAlgorithm,
    EventID,
    EventType,
    Format,
    MessageEventContent,
    MessageType,
    RoomEncryptionStateEventContent,
    RoomID,
    RoomTombstoneStateEventContent,
    TextMessageEventContent,
    UserID,
)
from mautrix.util.logging import TraceLogger
from mautrix.util.simple_lock import SimpleLock

from .. import bridge as br


class RelaySender(NamedTuple):
    sender: br.BaseUser | None
    is_relay: bool


class RejectMatrixInvite(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class IgnoreMatrixInvite(Exception):
    pass


class DMCreateError(RejectMatrixInvite):
    """
    An error raised by :meth:`BasePortal.prepare_dm` if the DM can't be set up.

    The message in the exception will be sent to the user as a message before the ghost leaves.
    """


class BasePortal(ABC):
    log: TraceLogger = logging.getLogger("mau.portal")
    _async_get_locks: dict[Any, asyncio.Lock] = defaultdict(lambda: asyncio.Lock())
    disappearing_msg_class: type[br.AbstractDisappearingMessage] | None = None
    _disappearing_lock: asyncio.Lock | None
    az: AppService
    matrix: br.BaseMatrixHandler
    bridge: br.Bridge
    loop: asyncio.AbstractEventLoop
    main_intent: IntentAPI
    mxid: RoomID | None
    name: str | None
    encrypted: bool
    is_direct: bool
    backfill_lock: SimpleLock

    relay_user_id: UserID | None
    _relay_user: br.BaseUser | None
    relay_emote_to_text: bool = True
    relay_formatted_body: bool = True

    def __init__(self) -> None:
        self._disappearing_lock = asyncio.Lock() if self.disappearing_msg_class else None

    @abstractmethod
    async def save(self) -> None:
        pass

    @abstractmethod
    async def get_dm_puppet(self) -> br.BasePuppet | None:
        """
        Get the ghost representing the other end of this direct chat.

        Returns:
            A puppet entity, or ``None`` if this is not a 1:1 chat.
        """

    @abstractmethod
    async def handle_matrix_message(
        self, sender: br.BaseUser, message: MessageEventContent, event_id: EventID
    ) -> None:
        pass

    async def prepare_remote_dm(
        self, room_id: RoomID, invited_by: br.BaseUser, puppet: br.BasePuppet
    ) -> str:
        """
        Do whatever is needed on the remote platform to set up a direct chat between the user
        and the ghost. By default, this does nothing (and lets :meth:`setup_matrix_dm` handle
        everything).

        Args:
            room_id: The room ID that will be used.
            invited_by: The Matrix user who invited the ghost.
            puppet: The ghost who was invited.

        Returns:
            A simple message indicating what was done (will be sent as a notice to the room).
            If empty, the message won't be sent.

        Raises:
            DMCreateError: if the DM could not be created and the ghost should leave the room.
        """
        return "Portal to private chat created."

    async def postprocess_matrix_dm(self, user: br.BaseUser, puppet: br.BasePuppet) -> None:
        await self.update_bridge_info()

    async def reject_duplicate_dm(
        self, room_id: RoomID, invited_by: br.BaseUser, puppet: br.BasePuppet
    ) -> None:
        try:
            await puppet.default_mxid_intent.send_notice(
                room_id,
                text=f"You already have a private chat with me: {self.mxid}",
                html=(
                    "You already have a private chat with me: "
                    f"<a href='https://matrix.to/#/{self.mxid}'>Link to room</a>"
                ),
            )
        except Exception as e:
            self.log.debug(f"Failed to send notice to duplicate private chat room: {e}")

        try:
            await puppet.default_mxid_intent.send_state_event(
                room_id,
                event_type=EventType.ROOM_TOMBSTONE,
                content=RoomTombstoneStateEventContent(
                    replacement_room=self.mxid,
                    body="You already have a private chat with me",
                ),
            )
        except Exception as e:
            self.log.debug(f"Failed to send tombstone to duplicate private chat room: {e}")

        await puppet.default_mxid_intent.leave_room(room_id)

    async def accept_matrix_dm(
        self, room_id: RoomID, invited_by: br.BaseUser, puppet: br.BasePuppet
    ) -> None:
        """
        Set up a room as a direct chat portal.

        The ghost has already accepted the invite at this point, so this method needs to make it
        leave if the DM can't be created for some reason.

        By default, this checks if there's an existing portal and redirects the user there if it
        does exist. If a portal doesn't exist, this will call :meth:`prepare_matrix_dm` and then
        save the room ID, enable encryption and update bridge info. If the portal exists, but isn't
        usable, the old room will be cleaned up and the function will continue.

        Args:
            room_id: The room ID that will be used.
            invited_by: The Matrix user who invited the ghost.
            puppet: The ghost who was invited.
        """
        if self.mxid:
            try:
                portal_members = await self.main_intent.get_room_members(self.mxid)
            except (MForbidden, MNotFound):
                portal_members = []
            if invited_by.mxid in portal_members:
                await self.reject_duplicate_dm(room_id, invited_by, puppet)
                return
            self.log.debug(
                f"{invited_by.mxid} isn't in old portal room {self.mxid},"
                " cleaning up and accepting new room as the DM portal"
            )
            await self.cleanup_portal(
                message="User seems to have left DM portal", puppets_only=True
            )
        try:
            message = await self.prepare_remote_dm(room_id, invited_by, puppet)
        except DMCreateError as e:
            if e.message:
                await puppet.default_mxid_intent.send_notice(room_id, text=e.message)
            await puppet.default_mxid_intent.leave_room(room_id, reason="Failed to create DM")
            return
        self.mxid = room_id
        e2be_ok = await self.check_dm_encryption()
        await self.save()
        if e2be_ok is False:
            message += "\n\nWarning: Failed to enable end-to-bridge encryption."
        if message:
            await self._send_message(
                puppet.default_mxid_intent,
                TextMessageEventContent(
                    msgtype=MessageType.NOTICE,
                    body=message,
                ),
            )
        await self.postprocess_matrix_dm(invited_by, puppet)

    async def handle_matrix_invite(self, invited_by: br.BaseUser, puppet: br.BasePuppet) -> None:
        """
        Called when a Matrix user invites a bridge ghost to a room to process the invite (and check
        if it should be accepted).

        Args:
            invited_by: The user who invited the ghost.
            puppet: The ghost who was invited.

        Raises:
            RejectMatrixInvite: if the invite should be rejected.
            IgnoreMatrixInvite: if the invite should be ignored (e.g. if it was already accepted).
        """
        if self.is_direct:
            raise RejectMatrixInvite("You can't invite additional users to private chats.")
        raise RejectMatrixInvite("This bridge does not implement inviting users to portals.")

    async def update_bridge_info(self) -> None:
        """Resend the ``m.bridge`` event into the room."""

    @property
    def _relay_is_implemented(self) -> bool:
        return hasattr(self, "relay_user_id") and hasattr(self, "_relay_user")

    @property
    def has_relay(self) -> bool:
        return (
            self._relay_is_implemented
            and self.bridge.config["bridge.relay.enabled"]
            and bool(self.relay_user_id)
        )

    async def get_relay_user(self) -> br.BaseUser | None:
        if not self.has_relay:
            return None
        if self._relay_user is None:
            self._relay_user = await self.bridge.get_user(self.relay_user_id)
        return self._relay_user if await self._relay_user.is_logged_in() else None

    async def set_relay_user(self, user: br.BaseUser | None) -> None:
        if not self._relay_is_implemented or not self.bridge.config["bridge.relay.enabled"]:
            raise RuntimeError("Can't set_relay_user() when relay mode is not enabled")
        self._relay_user = user
        self.relay_user_id = user.mxid if user else None
        await self.save()

    async def get_relay_sender(self, sender: br.BaseUser, evt_identifier: str) -> RelaySender:
        if not await sender.needs_relay(self):
            return RelaySender(sender, False)

        if not self.has_relay:
            self.log.debug(
                f"Ignoring {evt_identifier} from non-logged-in user {sender.mxid} "
                f"in chat with no relay user"
            )
            return RelaySender(None, True)
        relay_sender = await self.get_relay_user()
        if not relay_sender:
            self.log.debug(
                f"Ignoring {evt_identifier} from non-logged-in user {sender.mxid} "
                f"relay user {self.relay_user_id} is not set up correctly"
            )
            return RelaySender(None, True)
        return RelaySender(relay_sender, True)

    async def apply_relay_message_format(
        self, sender: br.BaseUser, content: MessageEventContent
    ) -> None:
        if self.relay_formatted_body and content.get("format", None) != Format.HTML:
            content["format"] = Format.HTML
            content["formatted_body"] = html.escape(content.body).replace("\n", "<br/>")
        tpl = self.bridge.config["bridge.relay.message_formats"].get(
            content.msgtype.value, "$sender_displayname: $message"
        )
        displayname = await self.get_displayname(sender)
        username, _ = self.az.intent.parse_user_id(sender.mxid)
        tpl_args = {
            "sender_mxid": sender.mxid,
            "sender_username": username,
            "sender_displayname": html.escape(displayname),
            "formatted_body": content["formatted_body"],
            "body": content.body,
            "message": content.body,
        }
        content.body = Template(tpl).safe_substitute(tpl_args)
        if self.relay_formatted_body and "formatted_body" in content:
            tpl_args["message"] = content["formatted_body"]
            content["formatted_body"] = Template(tpl).safe_substitute(tpl_args)
        if self.relay_emote_to_text and content.msgtype == MessageType.EMOTE:
            content.msgtype = MessageType.TEXT

    async def get_displayname(self, user: br.BaseUser) -> str:
        return await self.main_intent.get_room_displayname(self.mxid, user.mxid) or user.mxid

    async def check_dm_encryption(self) -> bool | None:
        try:
            evt = await self.main_intent.get_state_event(self.mxid, EventType.ROOM_ENCRYPTION)
            self.log.debug("Found existing encryption event in direct portal: %s", evt)
            if evt and evt.algorithm == EncryptionAlgorithm.MEGOLM_V1:
                self.encrypted = True
        except MNotFound:
            pass
        if (
            self.is_direct
            and self.matrix.e2ee
            and (self.bridge.config["bridge.encryption.default"] or self.encrypted)
        ):
            return await self.enable_dm_encryption()
        return None

    def get_encryption_state_event_json(self) -> JSON:
        evt = RoomEncryptionStateEventContent(EncryptionAlgorithm.MEGOLM_V1)
        if self.bridge.config["bridge.encryption.rotation.enable_custom"]:
            evt.rotation_period_ms = self.bridge.config["bridge.encryption.rotation.milliseconds"]
            evt.rotation_period_msgs = self.bridge.config["bridge.encryption.rotation.messages"]
        return evt.serialize()

    async def enable_dm_encryption(self) -> bool:
        self.log.debug("Inviting bridge bot to room for end-to-bridge encryption")
        try:
            await self.main_intent.invite_user(self.mxid, self.az.bot_mxid)
            await self.az.intent.join_room_by_id(self.mxid)
            if not self.encrypted:
                await self.main_intent.send_state_event(
                    self.mxid,
                    EventType.ROOM_ENCRYPTION,
                    self.get_encryption_state_event_json(),
                )
        except Exception:
            self.log.warning(f"Failed to enable end-to-bridge encryption", exc_info=True)
            return False

        self.encrypted = True
        await self.update_info_from_puppet()
        return True

    async def update_info_from_puppet(self, puppet: br.BasePuppet | None = None) -> None:
        """
        Update the room metadata to match the ghost's name/avatar.

        This is called after enabling encryption, as the bridge bot needs to join for e2ee,
        but that messes up the default name generation. If/when canonical DMs happen,
        this might not be necessary anymore.

        Args:
            puppet: The ghost that is the other participant in the room.
                If ``None``, the entity should be fetched as necessary.
        """

    @property
    def disappearing_enabled(self) -> bool:
        return bool(self.disappearing_msg_class)

    async def _disappear_event(self, msg: br.AbstractDisappearingMessage) -> None:
        sleep_time = (msg.expiration_ts / 1000) - time.time()
        self.log.trace(f"Sleeping {sleep_time:.3f} seconds before redacting {msg.event_id}")
        await asyncio.sleep(sleep_time)
        try:
            await msg.delete()
        except Exception:
            self.log.exception(
                f"Failed to delete disappearing message record for {msg.event_id} from database"
            )
        if self.mxid != msg.room_id:
            self.log.debug(
                f"Not redacting expired event {msg.event_id}, "
                f"portal room seems to have changed ({self.mxid!r} != {msg.room_id!r})"
            )
            return
        try:
            await self._do_disappear(msg.event_id)
            self.log.debug(f"Expired event {msg.event_id} disappeared successfully")
        except Exception as e:
            self.log.warning(f"Failed to make expired event {msg.event_id} disappear: {e}", e)

    async def _do_disappear(self, event_id: EventID) -> None:
        await self.main_intent.redact(self.mxid, event_id)

    @classmethod
    async def restart_scheduled_disappearing(cls) -> None:
        """
        Restart disappearing message timers for all messages that were already scheduled to
        disappear earlier. This should be called at bridge startup.
        """
        if not cls.disappearing_msg_class:
            return
        msgs = await cls.disappearing_msg_class.get_all_scheduled()
        for msg in msgs:
            portal = await cls.bridge.get_portal(msg.room_id)
            if portal and portal.mxid:
                asyncio.create_task(portal._disappear_event(msg))
            else:
                await msg.delete()

    async def schedule_disappearing(self) -> None:
        """
        Start the disappearing message timer for all unscheduled messages in this room.
        This is automatically called from :meth:`MatrixHandler.handle_receipt`.
        """
        if not self.disappearing_msg_class:
            return
        async with self._disappearing_lock:
            msgs = await self.disappearing_msg_class.get_unscheduled_for_room(self.mxid)
            for msg in msgs:
                msg.start_timer()
                await msg.update()
                asyncio.create_task(self._disappear_event(msg))

    async def _send_message(
        self,
        intent: IntentAPI,
        content: MessageEventContent,
        event_type: EventType = EventType.ROOM_MESSAGE,
        **kwargs,
    ) -> EventID:
        if self.encrypted and self.matrix.e2ee:
            event_type, content = await self.matrix.e2ee.encrypt(self.mxid, event_type, content)
        event_id = await intent.send_message_event(self.mxid, event_type, content, **kwargs)
        if intent.api.is_real_user:
            asyncio.create_task(intent.mark_read(self.mxid, event_id))
        return event_id

    @property
    @abstractmethod
    def bridge_info_state_key(self) -> str:
        pass

    @property
    @abstractmethod
    def bridge_info(self) -> dict[str, Any]:
        pass

    # region Matrix room cleanup

    @abstractmethod
    async def delete(self) -> None:
        pass

    @classmethod
    async def cleanup_room(
        cls,
        intent: IntentAPI,
        room_id: RoomID,
        message: str = "Cleaning room",
        puppets_only: bool = False,
    ) -> None:
        try:
            members = await intent.get_room_members(room_id)
        except MatrixError:
            members = []
        for user_id in members:
            if user_id == intent.mxid:
                continue

            puppet = await cls.bridge.get_puppet(user_id, create=False)
            if puppet:
                await puppet.default_mxid_intent.leave_room(room_id)
                continue

            if not puppets_only:
                custom_puppet = await cls.bridge.get_double_puppet(user_id)
                left = False
                if custom_puppet:
                    try:
                        await custom_puppet.intent.leave_room(room_id)
                        await custom_puppet.intent.forget_room(room_id)
                    except MatrixError:
                        pass
                    else:
                        left = True
                if not left:
                    try:
                        await intent.kick_user(room_id, user_id, message)
                    except MatrixError:
                        pass
        try:
            await intent.leave_room(room_id)
        except MatrixError:
            cls.log.warning(f"Failed to leave room {room_id} when cleaning up room", exc_info=True)

    async def cleanup_portal(self, message: str, puppets_only: bool = False) -> None:
        await self.cleanup_room(self.main_intent, self.mxid, message, puppets_only)
        await self.delete()

    async def unbridge(self) -> None:
        await self.cleanup_portal("Room unbridged", puppets_only=True)

    async def cleanup_and_delete(self) -> None:
        await self.cleanup_portal("Portal deleted")

    async def get_authenticated_matrix_users(self) -> list[UserID]:
        """
        Get the list of Matrix user IDs who can be bridged. This is used to determine if the portal
        is empty (and should be cleaned up) or not. Bridges should override this to check that the
        users are either logged in or the portal has a relaybot.
        """
        try:
            members = await self.main_intent.get_room_members(self.mxid)
        except MatrixRequestError:
            return []
        return [
            member
            for member in members
            if (not self.bridge.is_bridge_ghost(member) and member != self.az.bot_mxid)
        ]

    # endregion
