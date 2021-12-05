# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Dict, List, Optional, Union
import asyncio
import uuid

from mautrix.types import (
    DeviceID,
    EncryptionAlgorithm,
    EventType,
    ForwardedRoomKeyEventContent,
    IdentityKey,
    KeyRequestAction,
    RequestedKeyInfo,
    RoomID,
    RoomKeyRequestEventContent,
    SessionID,
    UserID,
)

from .base import BaseOlmMachine
from .sessions import InboundGroupSession
from .types import DecryptedOlmEvent


class KeyRequestingMachine(BaseOlmMachine):
    async def request_room_key(
        self,
        room_id: RoomID,
        sender_key: IdentityKey,
        session_id: SessionID,
        from_devices: Dict[UserID, List[DeviceID]],
        timeout: Optional[Union[int, float]] = None,
    ) -> bool:
        """
        Request keys for a Megolm group session from other devices.

        Once the keys are received, or if this task is cancelled (via the ``timeout`` parameter),
        a cancel request event is sent to the remaining devices. If the ``timeout`` is set to zero
        or less, this will return immediately, and the extra key requests will not be cancelled.

        Args:
            room_id: The room where the session is used.
            sender_key: The key of the user who created the session.
            session_id: The ID of the session.
            from_devices: A dict from user ID to list of device IDs whom to ask for the keys.
            timeout: The maximum number of seconds to wait for the keys. If the timeout is
                     ``None``, the wait time is not limited, but the task can still be cancelled.
                     If it's zero or less, this returns immediately and will never cancel requests.

        Returns:
            ``True`` if the keys were received and are now in the crypto store,
            ``False`` otherwise (including if the method didn't wait at all).
        """
        request_id = str(uuid.uuid1())
        request = RoomKeyRequestEventContent(
            action=KeyRequestAction.REQUEST,
            body=RequestedKeyInfo(
                algorithm=EncryptionAlgorithm.MEGOLM_V1,
                room_id=room_id,
                sender_key=sender_key,
                session_id=session_id,
            ),
            request_id=request_id,
            requesting_device_id=self.client.device_id,
        )

        wait = timeout is None or timeout > 0
        fut: Optional[asyncio.Future] = None
        if wait:
            fut = asyncio.get_running_loop().create_future()
            self._key_request_waiters[session_id] = fut
        await self.client.send_to_device(
            EventType.ROOM_KEY_REQUEST,
            {
                user_id: {device_id: request for device_id in devices}
                for user_id, devices in from_devices.items()
            },
        )
        if not wait:
            # Timeout is set and <=0, don't wait for keys
            return False
        assert fut is not None
        got_keys = False
        try:
            user_id, device_id = await asyncio.wait_for(fut, timeout=timeout)
            got_keys = True
            try:
                del from_devices[user_id][device_id]
                if len(from_devices[user_id]) == 0:
                    del from_devices[user_id]
            except KeyError:
                pass
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        del self._key_request_waiters[session_id]
        if len(from_devices) > 0:
            cancel = RoomKeyRequestEventContent(
                action=KeyRequestAction.CANCEL,
                request_id=str(request_id),
                requesting_device_id=self.client.device_id,
            )
            await self.client.send_to_device(
                EventType.ROOM_KEY_REQUEST,
                {
                    user_id: {device_id: cancel for device_id in devices}
                    for user_id, devices in from_devices.items()
                },
            )
        return got_keys

    async def _receive_forwarded_room_key(self, evt: DecryptedOlmEvent) -> None:
        key: ForwardedRoomKeyEventContent = evt.content
        if await self.crypto_store.has_group_session(key.room_id, key.sender_key, key.session_id):
            self.log.debug(
                f"Ignoring received session {key.session_id} from {evt.sender}/"
                f"{evt.sender_device}, as crypto store says we have it already"
            )
            return
        key.forwarding_key_chain.append(evt.sender_key)
        sess = InboundGroupSession.import_session(
            key.session_key, key.signing_key, key.sender_key, key.room_id, key.forwarding_key_chain
        )
        if key.session_id != sess.id:
            self.log.warning(
                f"Mismatched session ID while importing forwarded key from "
                f"{evt.sender}/{evt.sender_device}: '{key.session_id}' != '{sess.id}'"
            )
            return

        await self.crypto_store.put_group_session(
            key.room_id, key.sender_key, key.session_id, sess
        )
        self._mark_session_received(key.session_id)

        self.log.debug(
            f"Imported {key.session_id} for {key.room_id} "
            f"from {evt.sender}/{evt.sender_device}"
        )

        try:
            task = self._key_request_waiters[key.session_id]
        except KeyError:
            pass
        else:
            task.set_result((evt.sender, evt.sender_device))
