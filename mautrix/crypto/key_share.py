# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional

from mautrix.types import (UserID, EventType, RequestedKeyInfo, RoomKeyWithheldCode,
                           RoomKeyWithheldEventContent, RoomKeyRequestEventContent, ToDeviceEvent,
                           KeyRequestAction, ForwardedRoomKeyEventContent, EncryptionAlgorithm)
from mautrix.errors import MatrixError, MatrixConnectionError, MatrixRequestError

from .device_lists import DeviceListMachine
from .encrypt_olm import OlmEncryptionMachine
from .types import DeviceIdentity, TrustState


class RejectKeyShare(MatrixError):
    def __init__(self, log_message: str = "", code: Optional[RoomKeyWithheldCode] = None,
                 reason: Optional[str] = None) -> None:
        """
        RejectKeyShare is an error used to signal that a key share request should be rejected.

        Args:
            log_message: The message to log when rejecting the request.
            code: The m.room_key.withheld code, or ``None`` to reject silently.
            reason: The human-readable reason for the rejection.
        """
        super().__init__(log_message)
        self.code = code
        self.reason = reason


class KeySharingMachine(OlmEncryptionMachine, DeviceListMachine):
    async def default_allow_key_share(self, device: DeviceIdentity, request: RequestedKeyInfo
                                      ) -> bool:
        """
        Check whether or not the given key request should be fulfilled. You can set a custom
        function in :attr:`allow_key_share` to override this.

        Args:
            device: The identity of the device requesting keys.
            request: The requested key details.

        Returns:
            ``True`` if the key share should be accepted,
            ``False`` if it should be silently ignored.

        Raises:
            RejectKeyShare: if the key share should be rejected.
        """
        if device.user_id != self.client.mxid:
            raise RejectKeyShare(f"Rejecting key request from a different user ({device.user_id})",
                                 code=RoomKeyWithheldCode.UNAUTHORIZED,
                                 reason="This device does not share keys to other users")
        elif device.device_id == self.client.device_id:
            raise RejectKeyShare("Ignoring key request from ourselves", code=None)
        elif device.trust == TrustState.BLACKLISTED:
            raise RejectKeyShare(
                f"Rejecting key request from blacklisted device {device.device_id}",
                code=RoomKeyWithheldCode.BLACKLISTED,
                reason="You have been blacklisted by this device")
        elif device.trust == TrustState.VERIFIED:
            self.log.debug(f"Accepting key request from verified device {device.device_id}")
            return True
        elif self.share_to_unverified_devices:
            self.log.debug(f"Accepting key request from unverified device {device.device_id}, "
                           f"as share_to_unverified_devices is True")
            return True
        else:
            raise RejectKeyShare(f"Rejecting key request from unverified device {device.device_id}",
                                 code=RoomKeyWithheldCode.UNVERIFIED,
                                 reason="You have not been verified by this device")

    async def handle_room_key_request(self, evt: ToDeviceEvent, raise_exceptions: bool = False
                                      ) -> None:
        """
        Handle a ``m.room_key_request`` where the action is ``request``.

        This is automatically registered as an event handler and therefore called if the client you
        passed to the OlmMachine is syncing. You shouldn't need to call this yourself unless you
        do syncing in some manual way.

        Args:
            evt: The to-device event.
            raise_exceptions: Whether or not errors while handling should be raised.
        """
        request: RoomKeyRequestEventContent = evt.content
        if request.action != KeyRequestAction.REQUEST:
            return
        elif evt.sender == self.client.mxid and request.requesting_device_id == self.client.device_id:
            self.log.debug(f"Ignoring key request {request.request_id} from ourselves")
            return

        try:
            device = await self.get_or_fetch_device(evt.sender, request.requesting_device_id)
        except Exception:
            self.log.warning(f"Failed to get device {evt.sender}/{request.requesting_device_id} to "
                             f"handle key request {request.request_id}", exc_info=True)
            if raise_exceptions:
                raise
            return
        if not device:
            self.log.warning(f"Couldn't find device {evt.sender}/{request.requesting_device_id} to "
                             f"handle key request {request.request_id}")
            return

        self.log.debug(f"Received key request {request.request_id} from {device.user_id}/"
                       f"{device.device_id} for session {request.body.session_id}")
        try:
            await self._handle_room_key_request(device, request.body)
        except RejectKeyShare as e:
            self.log.debug(f"Rejecting key request {request.request_id}: {e}")
            await self._reject_key_request(e, device, request.body)
        except (MatrixRequestError, MatrixConnectionError):
            self.log.exception(f"API error while handling key request {request.request_id} "
                               f"(not sending rejection)")
            if raise_exceptions:
                raise
        except Exception:
            self.log.exception(f"Error while handling key request {request.request_id}, "
                               f"sending rejection...")
            error = RejectKeyShare(code=RoomKeyWithheldCode.UNAVAILABLE,
                                   reason="An internal error occurred while trying to "
                                          "share the requested session")
            await self._reject_key_request(error, device, request.body)
            if raise_exceptions:
                raise

    async def _handle_room_key_request(self, device: DeviceIdentity, request: RequestedKeyInfo
                                       ) -> None:
        if not await self.allow_key_share(device, request):
            return

        sess = await self.crypto_store.get_group_session(request.room_id, request.sender_key,
                                                         request.session_id)
        if sess is None:
            raise RejectKeyShare(f"Didn't find group session {request.session_id} to forward to "
                                 f"{device.user_id}/{device.device_id}",
                                 code=RoomKeyWithheldCode.UNAVAILABLE,
                                 reason="Requested session ID not found on this device")

        exported_key = sess.export_session(sess.first_known_index)
        forward_content = ForwardedRoomKeyEventContent(algorithm=EncryptionAlgorithm.MEGOLM_V1,
                                                       room_id=sess.room_id, session_id=sess.id,
                                                       session_key=exported_key,
                                                       sender_key=sess.sender_key,
                                                       forwarding_key_chain=sess.forwarding_chain,
                                                       signing_key=sess.signing_key)
        await self.send_encrypted_to_device(device, EventType.FORWARDED_ROOM_KEY, forward_content)

    async def _reject_key_request(self, rejection: RejectKeyShare, device: DeviceIdentity,
                                  request: RequestedKeyInfo) -> None:
        if not rejection.code:
            # Silent rejection
            return
        content = RoomKeyWithheldEventContent(room_id=request.room_id,
                                              algorithm=request.algorithm,
                                              session_id=request.session_id,
                                              sender_key=request.sender_key,
                                              code=rejection.code,
                                              reason=rejection.reason)

        try:
            await self.client.send_to_one_device(EventType.ROOM_KEY_WITHHELD,
                                                 device.user_id, device.device_id, content)
            await self.client.send_to_one_device(EventType.ORG_MATRIX_ROOM_KEY_WITHHELD,
                                                 device.user_id, device.device_id, content)
        except MatrixError:
            self.log.warning(f"Failed to send key share rejection {rejection.code} "
                             f"to {device.user_id}/{device.device_id}", exc_info=True)
