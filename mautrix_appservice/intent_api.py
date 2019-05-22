# -*- coding: future_fstrings -*-
from urllib.parse import quote as urllib_quote
from time import time
from json.decoder import JSONDecodeError
from typing import Optional, Dict, Awaitable, List, Union, Tuple, Any
from logging import Logger
from datetime import datetime, timezone
import re
import json
import asyncio

from aiohttp import ClientSession
from aiohttp.client_exceptions import ContentTypeError

try:
    import magic
except ImportError:
    magic = None

from .state_store import StateStore
from .errors import MatrixError, MatrixRequestError, MatrixResponseError, IntentError


def quote(*args, **kwargs):
    return urllib_quote(*args, **kwargs, safe="")


class HTTPAPI:
    def __init__(self, base_url: str, domain: str = None, bot_mxid: str = None, token: str = None,
                 identity: str = None, log: Logger = None, state_store: StateStore = None,
                 client_session: ClientSession = None, child: bool = False, real_user: bool = False,
                 real_user_content_key: Optional[str] = None):
        self.base_url = base_url
        self.token = token
        self.identity = identity
        self.validate_cert = True
        self.session = client_session

        self.domain = domain
        self.bot_mxid = bot_mxid
        self._bot_intent = None
        self.state_store = state_store
        self.is_real_user = real_user
        self.real_user_content_key = real_user_content_key

        if real_user:
            self.log = log
            self.intent_log = log.getChild("intent")
            self.txn_id = 0
        elif child:
            self.log = log
        else:
            self.intent_log = log.getChild("intent")
            self.log = log.getChild("api")
            self.txn_id = 0
            self.children = {}
            self.real_users = {}

    def user(self, user: str) -> "ChildHTTPAPI":
        """
        Get a child HTTPAPI instance.

        Args:
            user: The Matrix ID of the user whose API to get.

        Returns:
            A HTTPAPI instance that always uses the given Matrix ID.
        """
        if self.is_real_user:
            raise ValueError("Can't get child of real user")

        try:
            return self.children[user]
        except KeyError:
            child = ChildHTTPAPI(user, self)
            self.children[user] = child
            return child

    def real_user(self, mxid: str, token: str) -> "HTTPAPI":
        if self.is_real_user:
            raise ValueError("Can't get child of real user")

        try:
            return self.real_users[mxid]
        except KeyError:
            child = self.__class__(self.base_url, self.domain, None, token, mxid, self.log,
                                   self.state_store, self.session, real_user=True,
                                   real_user_content_key=self.real_user_content_key)
            self.real_users[mxid] = child
            return child

    def bot_intent(self) -> "IntentAPI":
        """
        Get the intent API for the appservice bot.

        Returns:
            The IntentAPI for the appservice bot.
        """
        if not self._bot_intent:
            self._bot_intent = IntentAPI(self.bot_mxid, self, state_store=self.state_store,
                                         log=self.intent_log)
        return self._bot_intent

    def intent(self, user: str = None, token: Optional[str] = None) -> "IntentAPI":
        """
        Get the intent API for a specific user.

        Args:
            user: The Matrix ID of the user whose intent API to get.

        Returns:
            The IntentAPI for the given user.
        """
        if self.is_real_user:
            raise ValueError("Can't get child intent of real user")
        if token:
            return IntentAPI(user, self.real_user(user, token), self.bot_intent(), self.state_store,
                             self.intent_log)
        return IntentAPI(user, self.user(user), self.bot_intent(), self.state_store,
                         self.intent_log)

    async def _send(self, method, endpoint, content, query_params, headers):
        while True:
            request = self.session.request(method, endpoint, params=query_params,
                                           data=content, headers=headers)
            async with request as response:
                if response.status < 200 or response.status >= 300:
                    errcode = message = None
                    try:
                        response_data = await response.json()
                        errcode = response_data["errcode"]
                        message = response_data["error"]
                    except (JSONDecodeError, ContentTypeError, KeyError):
                        pass
                    raise MatrixRequestError(code=response.status, text=await response.text(),
                                             errcode=errcode, message=message)

                if response.status == 429:
                    await asyncio.sleep(response.json()["retry_after_ms"] / 1000)
                else:
                    return await response.json()

    def _log_request(self, method, path, content, query_params):
        log_content = content if not isinstance(content, bytes) else f"<{len(content)} bytes>"
        log_content = log_content or "(No content)"
        query_identity = query_params["user_id"] if "user_id" in query_params else "No identity"
        self.log.debug("%s %s %s as user %s", method, path, log_content, query_identity)

    def request(self, method: str, path: str, content: Optional[Union[dict, bytes, str]] = None,
                timestamp: Optional[int] = None, external_url: Optional[str] = None,
                headers: Optional[Dict[str, str]] = None,
                query_params: Optional[Dict[str, Any]] = None,
                api_path: str = "/_matrix/client/r0") -> Awaitable[dict]:
        """
        Make a raw HTTP request.

        Args:
            method: The HTTP method to use.
            path: The API endpoint to call. Does not include the base path (e.g. /_matrix/client/r0).
            content: The content to post as a dict (json) or bytes/str (raw).
            timestamp: The timestamp query param used for timestamp massaging.
            external_url: The external_url field to send in the content
                (only applicable if content is dict).
            headers: The dict of HTTP headers to send.
            query_params: The dict of query parameters to send.
            api_path: The base API path.

        Returns:
            The response as a dict.
        """
        content = content or {}
        headers = headers or {}
        query_params = query_params or {}
        query_params["access_token"] = self.token

        if timestamp is not None:
            if isinstance(timestamp, datetime):
                timestamp = int(timestamp.replace(tzinfo=timezone.utc).timestamp() * 1000)
            query_params["ts"] = timestamp
        if isinstance(content, dict) and external_url is not None:
            content["external_url"] = external_url

        method = method.upper()
        if method not in ["GET", "PUT", "DELETE", "POST"]:
            raise MatrixError("Unsupported HTTP method: %s" % method)

        is_json_ish = isinstance(content, (dict, list, str, int, float, bool, type(None)))
        if "Content-Type" not in headers and is_json_ish:
            headers["Content-Type"] = "application/json"
        if headers.get("Content-Type", None) == "application/json" and is_json_ish:
            content = json.dumps(content)

        if self.identity and not self.is_real_user:
            query_params["user_id"] = self.identity

        self._log_request(method, path, content, query_params)

        endpoint = self.base_url + api_path + path
        return self._send(method, endpoint, content, query_params, headers or {})

    def sync(self, since=None, timeout_ms=30000, filter=None, full_state=None, set_presence=None):
        """ Perform a sync request.
        Args:
            since (str): Optional. A token which specifies where to continue a sync from.
            timeout_ms (int): Optional. The time in m1illiseconds to wait.
            filter (int|str): Either a Filter ID or a JSON string.
            full_state (bool): Return the full state for every room the user has joined
                Defaults to false.
            set_presence (str): Should the client be marked as "online" or" offline"
        """
        request = {
            "timeout": int(timeout_ms)
        }

        if since:
            request["since"] = since
        if filter:
            request["filter"] = filter
        if full_state:
            request["full_state"] = json.dumps(full_state)
        if set_presence:
            request["set_presence"] = set_presence
        return self.request("GET", "/sync", query_params=request)

    def get_filter(self, user_id: str, filter_id: str) -> Awaitable[dict]:
        return self.request("GET", f"/user/{user_id}/filter/{filter_id}")

    async def create_filter(self, user_id: str, filter_params: dict) -> str:
        resp = await self.request("POST", f"/user/{user_id}/filter", filter_params)
        return resp.get("filter_id", None)

    def get_download_url(self, mxc_uri: str) -> str:
        """
        Get the full URL to download a mxc:// URI.

        Args:
            mxc_uri: The MXC URI whose full URL to get.

        Returns:
            The full URL.

        Raises:
            ValueError: If `mxc_uri` doesn't begin with mxc://
        """
        if mxc_uri.startswith('mxc://'):
            return f"{self.base_url}/_matrix/media/r0/download/{mxc_uri[6:]}"
        else:
            raise ValueError("MXC URI did not begin with 'mxc://'")


class ChildHTTPAPI(HTTPAPI):
    """ChildHTTPAPI is a simple proxy to a HTTPAPI that always uses a specific user."""

    def __init__(self, user: str, parent: HTTPAPI):
        super().__init__(parent.base_url, parent.domain, parent.bot_mxid, parent.token, user,
                         parent.log, parent.state_store, parent.session, child=True,
                         real_user_content_key=parent.real_user_content_key)
        self.parent = parent

    @property
    def txn_id(self) -> int:
        return self.parent.txn_id

    @txn_id.setter
    def txn_id(self, value: int):
        self.parent.txn_id = value


class IntentAPI:
    """
    IntentAPI is a high-level wrapper around the HTTPAPI that provides many easy-to-use functions
    for accessing the client-server API.
    """

    mxid_regex = re.compile("@(.+):(.+)")

    def __init__(self, mxid: str, client: HTTPAPI, bot: "IntentAPI" = None,
                 state_store: StateStore = None, log: Logger = None):
        self.client = client
        self.bot = bot
        self.mxid = mxid
        self.log = log

        results = self.mxid_regex.match(mxid)
        if not results:
            raise ValueError("invalid MXID")
        self.localpart = results.group(1)

        self.state_store = state_store

    def user(self, user: str, token: Optional[str] = None) -> "IntentAPI":
        """
        Get the intent API for a specific user. This is just a proxy to :func:`~HTTPAPI.intent`.

        You should only call this method for the bot user. Calling it with child intent APIs will
        result in a warning log.

        Args:
            user: The Matrix ID of the user whose intent API to get.
            token: The access token to use for the Matrix ID.

        Returns:
            The IntentAPI for the given user.
        """
        if not self.bot:
            return self.client.intent(user, token)
        else:
            self.log.warning("Called IntentAPI#user() of child intent object.")
            return self.bot.client.intent(user, token)

    # region User actions

    async def get_joined_rooms(self) -> List[str]:
        """
        Get the list of rooms the user is in. See also: `API reference`_

        Returns:
            The list of room IDs the user is in.

        .. _API reference:
           https://matrix.org/docs/spec/client_server/r0.3.0.html#get-matrix-client-r0-joined-rooms
        """
        await self.ensure_registered()
        response = await self.client.request("GET", "/joined_rooms")
        return response["joined_rooms"]

    async def set_display_name(self, name: str):
        """
        Set the display name of the user. See also: `API reference`_

        Args:
            name: The new display name for the user.

        .. _API reference:
           https://matrix.org/docs/spec/client_server/r0.3.0.html#put-matrix-client-r0-profile-userid-displayname
        """
        await self.ensure_registered()
        content = {"displayname": name}
        await self.client.request("PUT", f"/profile/{self.mxid}/displayname", content)

    async def set_presence(self, status: str = "online", ignore_cache: bool = False):
        """
        Set the online status of the user. See also: `API reference`_

        Args:
            status: The online status of the user. Allowed values: "online", "offline", "unavailable".
            ignore_cache: Whether or not to set presence even if the cache says the presence is
                already set to that value.

        .. _API reference:
           https://matrix.org/docs/spec/client_server/r0.3.0.html#put-matrix-client-r0-presence-userid-status
        """
        await self.ensure_registered()
        if not ignore_cache and self.state_store.has_presence(self.mxid, status):
            return

        content = {
            "presence": status
        }
        resp = await self.client.request("PUT", f"/presence/{self.mxid}/status", content)
        self.state_store.set_presence(self.mxid, status)

    async def set_avatar(self, url: str):
        """
        Set the avatar of the user. See also: `API reference`_

        Args:
            url: The new avatar URL for the user. Must be a MXC URI.

        .. _API reference:
           https://matrix.org/docs/spec/client_server/r0.3.0.html#put-matrix-client-r0-profile-userid-avatar-url
        """
        await self.ensure_registered()
        content = {"avatar_url": url}
        await self.client.request("PUT", f"/profile/{self.mxid}/avatar_url", content)

    async def upload_file(self, data: bytes, mime_type: Optional[str] = None) -> str:
        """
        Upload a file to the content repository. See also: `API reference`_

        Args:
            data: The data to upload.
            mime_type: The MIME type to send with the upload request.

        Returns:
            The MXC URI to the uploaded file.

        Raises:
            MatrixResponseError: If the response does not contain a ``content_uri`` field.

        .. _API reference:
           https://matrix.org/docs/spec/client_server/r0.3.0.html#post-matrix-media-r0-upload
        """
        await self.ensure_registered()
        if magic:
            mime_type = mime_type or magic.from_buffer(data, mime=True)
        resp = await self.client.request("POST", "", content=data,
                                         headers={"Content-Type": mime_type},
                                         api_path="/_matrix/media/r0/upload")
        try:
            return resp["content_uri"]
        except KeyError:
            raise MatrixResponseError("Media repo upload response did not contain content_uri.")

    async def download_file(self, url: str) -> bytes:
        """
        Download a file from the content repository. See also: `API reference`_

        Args:
            url: The MXC URI to download.

        Returns:
            The raw downloaded data.

        .. _API reference:
           https://matrix.org/docs/spec/client_server/r0.3.0.html#get-matrix-media-r0-download-servername-mediaid
        """
        await self.ensure_registered()
        url = self.client.get_download_url(url)
        async with self.client.session.get(url) as response:
            return await response.read()

    # endregion
    # region Room actions

    async def create_room(self, alias: Optional[str] = None, is_public: bool = False,
                          name: Optional[str] = None, topic: Optional[str] = None,
                          is_direct: bool = False, invitees: Optional[List[str]] = None,
                          initial_state: Optional[List[dict]] = None) -> str:
        """
        Create a new room. See also: `API reference`_

        Args:
            alias: The desired room alias **local part**. If this is included, a room alias will be
                created and mapped to the newly created room. The alias will belong on the same
                homeserver which created the room. For example, if this was set to "foo" and sent to
                the homeserver "example.com" the complete room alias would be ``#foo:example.com``.
            is_public: This flag sets the state event preset to ``public_chat``, which sets
                ``join_rules`` to ``public``. Defaults to false, which sets ``join_rules`` to
                ``invite``.
            name: If this is included, an ``m.room.name`` event will be sent into the room to
                indicate the name of the room. See `Room Events`_ for more information on
                ``m.room.name``.
            topic: If this is included, an ``m.room.topic`` event will be sent into the room to
                indicate the topic for the room. See `Room Events`_ for more information on
                ``m.room.topic``.
            is_direct: This flag makes the server set the ``is_direct`` flag on the
                ``m.room.member`` events sent to the users in ``invite`` and ``invite_3pid``. See
                `Direct Messaging`_ for more information.
            invitees: A list of user IDs to invite to the room. This will tell the server to invite
                everyone in the list to the newly created room.
            initial_state: A list of state events to set in the new room. This allows the user to
                override the default state events set in the new room. The expected format of the
                state events are an object with type, state_key and content keys set.

                Takes precedence over events set by `is_public`, but gets overriden by ``name`` and
                ``topic keys``.

        Returns:
            The ID of the newly created room.

        Raises:
            MatrixResponseError: If the response does not contain a ``room_id`` field.

        .. _API reference:
           https://matrix.org/docs/spec/client_server/r0.3.0.html#post-matrix-client-r0-createroom
        .. _Room Events:
           https://matrix.org/docs/spec/client_server/r0.3.0.html#room-events
        .. _Direct Messaging:
           https://matrix.org/docs/spec/client_server/r0.3.0.html#direct-messaging
        """
        await self.ensure_registered()
        content = {
            "visibility": "private",
            "is_direct": is_direct,
            "preset": "public_chat" if is_public else "private_chat",
        }
        if alias:
            content["room_alias_name"] = alias
        if invitees:
            content["invite"] = invitees
        if name:
            content["name"] = name
        if topic:
            content["topic"] = topic
        if initial_state:
            content["initial_state"] = initial_state

        resp = await self.client.request("POST", "/createRoom", content)
        try:
            return resp["room_id"]
        except KeyError:
            raise MatrixResponseError("Room create response did not contain room_id.")

    def _invite_direct(self, room_id: str, user_id: str) -> Awaitable[dict]:
        content = {"user_id": user_id}
        return self.client.request("POST", "/rooms/" + room_id + "/invite", content)

    async def invite(self, room_id: str, user_id: str, check_cache: bool = False
                     ) -> Optional[dict]:
        """
        Invite a user to participate in a particular room. See also: `API reference`_

        Args:
            room_id: The room identifier (not alias) to which to invite the user.
            user_id: The fully qualified user ID of the invitee.
            check_cache: Whether or not to check the state cache before inviting.
                If true, the actual invite HTTP request will only be made if the user is not in the
                room according to local state caches.

        Returns:
        .. _API reference:
           https://matrix.org/docs/spec/client_server/r0.3.0.html#post-matrix-client-r0-createroom
        """
        await self.ensure_joined(room_id)
        try:
            ok_states = {"invite", "join"}
            do_invite = (not check_cache
                         or self.state_store.get_membership(room_id, user_id) not in ok_states)
            if do_invite:
                response = await self._invite_direct(room_id, user_id)
                self.state_store.invited(room_id, user_id)
                return response
        except MatrixRequestError as e:
            if e.errcode != "M_FORBIDDEN":
                raise IntentError(f"Failed to invite {user_id} to {room_id}", e)
            if "is already in the room" in e.message:
                self.state_store.joined(room_id, user_id)

    def set_room_avatar(self, room_id: str, avatar_url: Optional[str], info: Optional[dict] = None,
                        **kwargs) -> Awaitable[dict]:
        content = {}
        if avatar_url:
            content["url"] = avatar_url
        if info:
            content["info"] = info
        return self.send_state_event(room_id, "m.room.avatar", content, **kwargs)

    async def add_room_alias(self, room_id: str, localpart: str, override: bool = True
                             ) -> Optional[dict]:
        await self.ensure_registered()
        content = {"room_id": room_id}
        alias = f"#{localpart}:{self.client.domain}"
        try:
            return await self.client.request("PUT", f"/directory/room/{quote(alias)}", content)
        except MatrixRequestError as e:
            if override and e.code == 409:
                await self.remove_room_alias(localpart)
                return await self.client.request("PUT", f"/directory/room/{quote(alias)}", content)

    def remove_room_alias(self, localpart: str) -> Awaitable[dict]:
        alias = f"#{localpart}:{self.client.domain}"
        return self.client.request("DELETE", f"/directory/room/{quote(alias)}")

    def set_room_name(self, room_id: str, name: str, **kwargs) -> Awaitable[dict]:
        body = {"name": name}
        return self.send_state_event(room_id, "m.room.name", body, **kwargs)

    def set_room_topic(self, room_id: str, topic: str, **kwargs) -> Awaitable[dict]:
        body = {"topic": topic}
        return self.send_state_event(room_id, "m.room.topic", body, **kwargs)

    async def get_power_levels(self, room_id: str, ignore_cache: bool = False) -> dict:
        await self.ensure_joined(room_id)
        if not ignore_cache:
            try:
                levels = self.state_store.get_power_levels(room_id)
            except KeyError:
                levels = None
            if levels:
                return levels
        levels = await self.client.request("GET",
                                           f"/rooms/{quote(room_id)}/state/m.room.power_levels")
        self.state_store.set_power_levels(room_id, levels)
        return levels

    async def set_power_levels(self, room_id: str, content: dict, **kwargs) -> dict:
        if "events" not in content:
            content["events"] = {}
        response = await self.send_state_event(room_id, "m.room.power_levels", content, **kwargs)
        if response:
            self.state_store.set_power_levels(room_id, content)
            return response

    async def get_pinned_messages(self, room_id: str) -> List[str]:
        await self.ensure_joined(room_id)
        response = await self.client.request("GET",
                                             f"/rooms/{quote(room_id)}/state/m.room.pinned_events")
        return response["content"]["pinned"]

    def set_pinned_messages(self, room_id: str, events: List[str], **kwargs) -> Awaitable[dict]:
        return self.send_state_event(room_id, "m.room.pinned_events", {
            "pinned": events
        }, **kwargs)

    async def pin_message(self, room_id: str, event_id: str):
        events = await self.get_pinned_messages(room_id)
        if event_id not in events:
            events.append(event_id)
            await self.set_pinned_messages(room_id, events)

    async def unpin_message(self, room_id: str, event_id: str):
        events = await self.get_pinned_messages(room_id)
        if event_id in events:
            events.remove(event_id)
            await self.set_pinned_messages(room_id, events)

    async def set_join_rule(self, room_id: str, join_rule: str, **kwargs):
        if join_rule not in ("public", "knock", "invite", "private"):
            raise ValueError(f"Invalid join rule \"{join_rule}\"")
        await self.send_state_event(room_id, "m.room.join_rules", {
            "join_rule": join_rule,
        }, **kwargs)

    async def get_profile(self, user_id: str) -> dict:
        return await self.client.request("GET", f"/profile/{quote(user_id)}")

    async def whoami(self) -> Optional[str]:
        try:
            resp = await self.client.request("GET", f"/account/whoami")
            return resp.get("user_id", None)
        except MatrixError:
            return None

    async def get_displayname(self, room_id: str, user_id: str, ignore_cache=False) -> str:
        return (await self.get_member_info(room_id, user_id, ignore_cache)).get("displayname", None)

    async def get_avatar_url(self, room_id: str, user_id: str, ignore_cache=False) -> str:
        return (await self.get_member_info(room_id, user_id, ignore_cache)).get("avatar_url", None)

    async def get_member_info(self, room_id: str, user_id: str, ignore_cache=False) -> dict:
        member = self.state_store.get_member(room_id, user_id)
        if len(member) == 0 or ignore_cache:
            event = await self.get_state_event(room_id, "m.room.member", user_id)
            member = event.get("content", {})
        return member

    async def get_event(self, room_id: str, event_id: str) -> dict:
        await self.ensure_joined(room_id)
        return await self.client.request("GET", f"/rooms/{quote(room_id)}/event/{quote(event_id)}")

    async def set_typing(self, room_id: str, is_typing: bool = True, timeout: int = 5000,
                         ignore_cache: bool = False) -> Optional[dict]:
        await self.ensure_joined(room_id)
        if not ignore_cache and is_typing == self.state_store.is_typing(room_id, self.mxid):
            return
        content = {
            "typing": is_typing
        }
        if is_typing:
            content["timeout"] = timeout
        resp = await self.client.request("PUT",
                                         f"/rooms/{quote(room_id)}/typing/{self.mxid}", content)
        self.state_store.set_typing(room_id, self.mxid, is_typing, timeout)
        return resp

    async def mark_read(self, room_id: str, event_id: str) -> dict:
        await self.ensure_joined(room_id)
        return await self.client.request(
            "POST", f"/rooms/{quote(room_id)}/receipt/m.read/{quote(event_id)}", content={})

    def send_notice(self, room_id: str, text: str, html: Optional[str] = None,
                    relates_to: Optional[dict] = None, **kwargs) -> Awaitable[dict]:
        return self.send_text(room_id, text, html, "m.notice", relates_to, **kwargs)

    def send_emote(self, room_id: str, text: str, html: Optional[str] = None,
                   relates_to: Optional[dict] = None, **kwargs) -> Awaitable[dict]:
        return self.send_text(room_id, text, html, "m.emote", relates_to, **kwargs)

    def send_image(self, room_id: str, url: str, info: Optional[dict] = None, text: str = None,
                   relates_to: Optional[dict] = None, **kwargs) -> Awaitable[dict]:
        return self.send_file(room_id, url, info or {}, text, "m.image", relates_to, **kwargs)

    def send_file(self, room_id: str, url: str, info: Optional[dict] = None, text: str = None,
                  file_type: str = "m.file", relates_to: Optional[dict] = None, **kwargs
                  ) -> Awaitable[dict]:
        return self.send_message(room_id, {
            "msgtype": file_type,
            "url": url,
            "body": text or "Uploaded file",
            "info": info or {},
            "m.relates_to": relates_to or None,
        }, **kwargs)

    def send_sticker(self, room_id: str, url: str, info: Optional[dict] = None, text: str = None,
                     relates_to: Optional[dict] = None, **kwargs) -> Awaitable[dict]:
        return self.send_event(room_id, "m.sticker", {
            "url": url,
            "body": text or "",
            "info": info or {},
            "m.relates_to": relates_to or None,
        }, **kwargs)

    def send_text(self, room_id: str, text: str, html: Optional[str] = None,
                  msgtype: str = "m.text", relates_to: Optional[dict] = None, **kwargs
                  ) -> Awaitable[dict]:
        if html:
            if not text:
                text = html
            return self.send_message(room_id, {
                "body": text,
                "msgtype": msgtype,
                "format": "org.matrix.custom.html",
                "formatted_body": html or text,
                "m.relates_to": relates_to or None,
            }, **kwargs)
        else:
            return self.send_message(room_id, {
                "body": text,
                "msgtype": msgtype,
                "m.relates_to": relates_to or None,
            }, **kwargs)

    def send_message(self, room_id: str, body: dict, **kwargs) -> Awaitable[dict]:
        return self.send_event(room_id, "m.room.message", body, **kwargs)

    async def error_and_leave(self, room_id: str, text: str, html: Optional[str] = None):
        await self.ensure_joined(room_id)
        await self.send_notice(room_id, text, html=html)
        await self.leave_room(room_id)

    def kick(self, room_id: str, user_id: str, message: Optional[str] = None) -> Awaitable[dict]:
        return self.set_membership(room_id, user_id, "leave", message or "")

    def get_membership(self, room_id: str, user_id: str) -> Awaitable[str]:
        return self.get_state_event(room_id, "m.room.member", state_key=user_id)

    def set_membership(self, room_id: str, user_id: str, membership: str,
                       reason: Optional[str] = "", profile: Optional[dict] = None, **kwargs
                       ) -> Awaitable[dict]:
        body = {
            "membership": membership,
            "reason": reason
        }
        profile = profile or {}
        if "displayname" in profile:
            body["displayname"] = profile["displayname"]
        if "avatar_url" in profile:
            body["avatar_url"] = profile["avatar_url"]

        return self.send_state_event(room_id, "m.room.member", body, state_key=user_id, **kwargs)

    def redact(self, room_id: str, event_id: str, reason: Optional[str] = None,
               txn_id: Optional[int] = None, timestamp: Optional[int] = None) -> Awaitable[dict]:
        txn_id = txn_id or str(self.client.txn_id) + str(int(time() * 1000))
        self.client.txn_id += 1
        content = {}
        if reason:
            content["reason"] = reason
        return self.client.request("PUT",
                                   f"/rooms/{quote(room_id)}/redact/{quote(event_id)}/{txn_id}",
                                   content, timestamp=timestamp)

    @staticmethod
    def _get_event_url(room_id: str, event_type: str, txn_id: int) -> str:
        if not room_id:
            raise ValueError("Room ID not given")
        elif not event_type:
            raise ValueError("Event type not given")
        elif not txn_id:
            raise ValueError("Transaction ID not given")
        return f"/rooms/{quote(room_id)}/send/{quote(event_type)}/{quote(txn_id)}"

    async def send_event(self, room_id: str, event_type: str, content: dict,
                         txn_id: Optional[int] = None, **kwargs) -> dict:
        if not room_id:
            raise ValueError("Room ID not given")
        elif not event_type:
            raise ValueError("Event type not given")
        await self.ensure_joined(room_id)
        await self._ensure_has_power_level_for(room_id, event_type)

        if self.client.is_real_user and self.client.real_user_content_key:
            content[self.client.real_user_content_key] = True
        if content.get("m.relates_to", "not None") is None:
            del content["m.relates_to"]

        txn_id = txn_id or str(self.client.txn_id) + str(int(time() * 1000))
        self.client.txn_id += 1

        url = self._get_event_url(room_id, event_type, txn_id)

        return await self.client.request("PUT", url, content, **kwargs)

    @staticmethod
    def _get_state_url(room_id: str, event_type: str, state_key: Optional[str] = "") -> str:
        if not room_id:
            raise ValueError("Room ID not given")
        elif not event_type:
            raise ValueError("Event type not given")
        url = f"/rooms/{quote(room_id)}/state/{quote(event_type)}"
        if state_key:
            url += f"/{quote(state_key)}"
        return url

    async def send_state_event(self, room_id: str, event_type: str, content: dict,
                               state_key: Optional[str] = "", **kwargs) -> dict:
        if not room_id:
            raise ValueError("Room ID not given")
        elif not event_type:
            raise ValueError("Event type not given")
        await self.ensure_joined(room_id)
        has_pl = await self._ensure_has_power_level_for(room_id, event_type, is_state_event=True)
        if has_pl:
            url = self._get_state_url(room_id, event_type, state_key)
            return await self.client.request("PUT", url, content, **kwargs)

    async def get_state_event(self, room_id: str, event_type: str, state_key: Optional[str] = ""
                              ) -> dict:
        if not room_id:
            raise ValueError("Room ID not given")
        elif not event_type:
            raise ValueError("Event type not given")
        await self.ensure_joined(room_id)
        url = self._get_state_url(room_id, event_type, state_key)
        content = await self.client.request("GET", url)
        self.state_store.update_state({
            "type": event_type,
            "room_id": room_id,
            "state_key": state_key,
            "content": content,
        })
        return content

    def join_room(self, room_id: str):
        if not room_id:
            raise ValueError("Room ID not given")
        return self.ensure_joined(room_id, ignore_cache=True)

    def _join_room_direct(self, room: str) -> Awaitable[dict]:
        if not room:
            raise ValueError("Room ID not given")
        return self.client.request("POST", f"/join/{quote(room)}")

    def leave_room(self, room_id: str) -> Awaitable[dict]:
        if not room_id:
            raise ValueError("Room ID not given")
        try:
            self.state_store.left(room_id, self.mxid)
            return self.client.request("POST", f"/rooms/{quote(room_id)}/leave")
        except MatrixRequestError as e:
            if "not in room" not in e.message:
                raise

    def get_room_memberships(self, room_id: str) -> Awaitable[dict]:
        if not room_id:
            raise ValueError("Room ID not given")
        return self.client.request("GET", f"/rooms/{quote(room_id)}/members")

    def get_room_joined_memberships(self, room_id: str) -> Awaitable[dict]:
        if not room_id:
            raise ValueError("Room ID not given")
        return self.client.request("GET", f"/rooms/{quote(room_id)}/joined_members")

    async def get_room_members(self, room_id: str, allowed_memberships: Tuple[str, ...] = ("join",)
                               ) -> List[str]:
        if allowed_memberships == ("join",):
            memberships = await self.get_room_joined_memberships(room_id)
            return list(memberships["joined"].keys())
        memberships = await self.get_room_memberships(room_id)
        return [membership["state_key"] for membership in memberships["chunk"] if
                membership["content"]["membership"] in allowed_memberships]

    async def get_room_state(self, room_id: str) -> dict:
        await self.ensure_joined(room_id)
        state = await self.client.request("GET", f"/rooms/{quote(room_id)}/state")
        # TODO update values based on state?
        return state

    # endregion
    # region Ensure functions

    async def ensure_joined(self, room_id: str, ignore_cache: bool = False):
        if not room_id:
            raise ValueError("Room ID not given")
        if not ignore_cache and self.state_store.is_joined(room_id, self.mxid):
            return
        await self.ensure_registered()
        try:
            await self._join_room_direct(room_id)
            self.state_store.joined(room_id, self.mxid)
        except MatrixRequestError as e:
            if e.errcode != "M_FORBIDDEN" or not self.bot:
                raise IntentError(f"Failed to join room {room_id} as {self.mxid}", e)
            try:
                await self.bot.invite(room_id, self.mxid)
                await self._join_room_direct(room_id)
                self.state_store.joined(room_id, self.mxid)
            except MatrixRequestError as e2:
                raise IntentError(f"Failed to join room {room_id} as {self.mxid}", e2)

    def _register(self) -> Awaitable[dict]:
        content = {"username": self.localpart}
        query_params = {"kind": "user"}
        return self.client.request("POST", "/register", content, query_params=query_params)

    async def ensure_registered(self):
        if self.state_store.is_registered(self.mxid):
            return
        try:
            await self._register()
        except MatrixRequestError as e:
            if e.errcode != "M_USER_IN_USE":
                self.log.exception(f"Failed to register {self.mxid}!")
                # raise IntentError(f"Failed to register {self.mxid}", e)
                return
        self.state_store.registered(self.mxid)

    async def _ensure_has_power_level_for(self, room_id: str, event_type: str,
                                          is_state_event: bool = False):
        if not room_id:
            raise ValueError("Room ID not given")
        elif not event_type:
            raise ValueError("Event type not given")

        if not self.state_store.has_power_levels(room_id):
            await self.get_power_levels(room_id)
        if self.state_store.has_power_level(room_id, self.mxid, event_type,
                                            is_state_event=is_state_event):
            return True
        elif not self.bot:
            self.log.warning(
                f"Power level of {self.mxid} is not enough for {event_type} in {room_id}")
            # raise IntentError(f"Power level of {self.mxid} is not enough"
            #                   f"for {event_type} in {room_id}")
        return False
        # TODO implement

    # endregion
