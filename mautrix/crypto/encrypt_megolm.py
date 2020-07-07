# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Any, Dict, List, Union
import json

from mautrix.types import (EncryptedMegolmEventContent, EventType, UserID, DeviceID, Serializable,
                           EncryptionAlgorithm, RoomID, EncryptedToDeviceEventContent, SessionID,
                           RoomKeyWithheldEventContent, RoomKeyWithheldCode, IdentityKey,
                           SigningKey, RelatesTo)

from .types import DeviceIdentity, TrustState, EncryptionError
from .encrypt_olm import OlmEncryptionMachine
from .sessions import OutboundGroupSession, InboundGroupSession

SessionEncryptResult = Union[
    type(None),
    EncryptedToDeviceEventContent,  # share successful
    RoomKeyWithheldEventContent,  # won't share
    DeviceIdentity,  # missing device
]


class MegolmEncryptionMachine(OlmEncryptionMachine):
    async def encrypt_megolm_event(self, room_id: RoomID, event_type: EventType, content: Any
                                   ) -> EncryptedMegolmEventContent:
        self.log.trace(f"Encrypting event of type {event_type} for {room_id}")
        session = await self.crypto_store.get_outbound_group_session(room_id)
        if not session:
            raise EncryptionError("No group session created")
        ciphertext = session.encrypt(json.dumps({
            "room_id": room_id,
            "type": event_type.serialize(),
            "content": content.serialize() if isinstance(content, Serializable) else content,
        }))
        try:
            relates_to = content.relates_to
        except AttributeError:
            try:
                relates_to = RelatesTo.deserialize(content["m.relates_to"])
            except KeyError:
                relates_to = None
        await self.crypto_store.update_outbound_group_session(session)
        return EncryptedMegolmEventContent(sender_key=self.account.identity_key,
                                           device_id=self.client.device_id, session_id=session.id,
                                           ciphertext=ciphertext, relates_to=relates_to)

    async def share_group_session(self, room_id: RoomID, users: List[UserID]) -> None:
        # TODO
        pass

    async def _new_outbound_group_session(self, room_id: RoomID) -> OutboundGroupSession:
        session = OutboundGroupSession(room_id)
        await self._create_group_session(self.account.identity_key, self.account.signing_key,
                                         room_id, session.id, session.session_key)
        return session

    async def _create_group_session(self, sender_key: IdentityKey, signing_key: SigningKey,
                                    room_id: RoomID, session_id: SessionID, session_key: str
                                    ) -> None:
        session = InboundGroupSession(session_key=session_key, signing_key=signing_key,
                                      sender_key=sender_key, room_id=room_id)
        await self.crypto_store.put_group_session(room_id, sender_key, session_id, session)
        self.log.trace(f"Created inbound group session {room_id}/{sender_key}/{session_id}")

    async def _encrypt_group_session_for_user(self, session: OutboundGroupSession, user_id: UserID,
                                              devices: Dict[DeviceID, DeviceIdentity],
                                              ) -> Dict[DeviceID, SessionEncryptResult]:
        return {device_id: await self._encrypt_group_session_for_device(session, user_id, device_id,
                                                                        device)
                for device_id, device in devices.items()}

    async def _encrypt_group_session_for_device(self, session: OutboundGroupSession,
                                                user_id: UserID, device_id: DeviceID,
                                                device: DeviceIdentity) -> SessionEncryptResult:
        key = (user_id, device_id)
        if key in session.users_ignored or key in session.users_shared_with:
            return None
        elif user_id == self.client.mxid and device_id == self.client.device_id:
            session.users_ignored.add(key)
            return None

        if device.trust == TrustState.BLACKLISTED:
            self.log.debug(f"Not encrypting group session {session.id} for {device_id} "
                           f"of {user_id}: device is blacklisted")
            session.users_ignored.add(key)
            return RoomKeyWithheldEventContent(
                room_id=session.room_id, algorithm=EncryptionAlgorithm.MEGOLM_V1,
                session_id=session.id, sender_key=self.account.identity_key,
                code=RoomKeyWithheldCode.BLACKLISTED, reason="Device is blacklisted")
        elif not self.allow_unverified_devices and device.trust == TrustState.UNSET:
            self.log.debug(f"Not encrypting group session {session.id} for {device_id} "
                           f"of {user_id}: device is not verified")
            session.users_ignored.add(key)
            return RoomKeyWithheldEventContent(
                room_id=session.room_id, algorithm=EncryptionAlgorithm.MEGOLM_V1,
                session_id=session.id, sender_key=self.account.identity_key,
                code=RoomKeyWithheldCode.UNVERIFIED, reason="This device does not encrypt "
                                                            "messages for unverified devices")
        device_session = await self.crypto_store.get_latest_session(device.identity_key)
        if not device_session:
            return device
        encrypted = await self._encrypt_olm_event(device_session, device, EventType.ROOM_KEY,
                                                  session.share_content)
        session.users_shared_with.add(key)
        self.log.trace(f"Encrypted group session {session.id} for {device_id} of {user_id}")
        return encrypted
