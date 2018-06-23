# -*- coding: future_fstrings -*-
from urllib.parse import quote
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
from .errors import MatrixError, MatrixRequestError, IntentError


class HTTPAPI:
    def __init__(self, base_url: str, domain: str = None, bot_mxid: str = None, token: str = None,
                 identity: str = None, log: Logger = None, state_store: StateStore = None,
                 client_session: ClientSession = None, child: bool = False):
        self.base_url = base_url
        self.token = token
        self.identity = identity
        self.validate_cert = True
        self.session = client_session

        self.domain = domain
        self.bot_mxid = bot_mxid
        self._bot_intent = None
        self.state_store = state_store

        if child:
            self.log = log
        else:
            self.intent_log = log.getChild("intent")
            self.log = log.getChild("api")
            self.txn_id = 0
            self.children = {}

    def user(self, user: str) -> "ChildHTTPAPI":
        try:
            return self.children[user]
        except KeyError:
            child = ChildHTTPAPI(user, self)
            self.children[user] = child
            return child

    def bot_intent(self) -> "IntentAPI":
        if self._bot_intent:
            return self._bot_intent
        return IntentAPI(self.bot_mxid, self, state_store=self.state_store, log=self.intent_log)

    def intent(self, user: str) -> "IntentAPI":
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
        content = content or {}
        headers = headers or {}
        query_params = query_params or {}
        query_params["access_token"] = self.token

        if timestamp is not None:
            if isinstance(timestamp, datetime):
                timestamp = int(timestamp.replace(tzinfo=timezone.utc).timestamp() * 1000)
            query_params["ts"] = timestamp
        if external_url is not None:
            content["external_url"] = external_url

        method = method.upper()
        if method not in ["GET", "PUT", "DELETE", "POST"]:
            raise MatrixError("Unsupported HTTP method: %s" % method)

        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        if headers["Content-Type"] == "application/json":
            content = json.dumps(content)

        if self.identity:
            query_params["user_id"] = self.identity

        self._log_request(method, path, content, query_params)

        endpoint = self.base_url + api_path + path
        return self._send(method, endpoint, content, query_params, headers or {})

    def get_download_url(self, mxcurl: str) -> str:
        if mxcurl.startswith('mxc://'):
            return f"{self.base_url}/_matrix/media/r0/download/{mxcurl[6:]}"
        else:
            raise ValueError("MXC URL did not begin with 'mxc://'")

    async def get_display_name(self, user_id: str) -> Optional[str]:
        content = await self.request("GET", f"/profile/{user_id}/displayname")
        return content.get('displayname', None)

    async def get_avatar_url(self, user_id: str) -> Optional[str]:
        content = await self.request("GET", f"/profile/{user_id}/avatar_url")
        return content.get('avatar_url', None)

    async def get_room_id(self, room_alias: str) -> Optional[str]:
        content = await self.request("GET", f"/directory/room/{quote(room_alias)}")
        return content.get("room_id", None)

    def set_typing(self, room_id: str, is_typing: bool = True, timeout: int = 5000,
                   user: str = None) -> Awaitable[dict]:
        content = {
            "typing": is_typing
        }
        if is_typing:
            content["timeout"] = timeout
        user = user or self.identity
        return self.request("PUT", f"/rooms/{room_id}/typing/{user}", content)


class ChildHTTPAPI(HTTPAPI):
    def __init__(self, user: str, parent: HTTPAPI):
        super().__init__(parent.base_url, parent.domain, parent.bot_mxid, parent.token, user,
                         parent.log, parent.state_store, parent.session, child=True)
        self.parent = parent

    @property
    def txn_id(self) -> int:
        return self.parent.txn_id

    @txn_id.setter
    def txn_id(self, value: int):
        self.parent.txn_id = value


class IntentAPI:
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

    def user(self, user: str) -> "IntentAPI":
        if not self.bot:
            return self.client.intent(user)
        else:
            self.log.warning("Called IntentAPI#user() of child intent object.")
            return self.bot.client.intent(user)

    # region User actions

    async def get_joined_rooms(self) -> List[str]:
        await self.ensure_registered()
        response = await self.client.request("GET", "/joined_rooms")
        return response["joined_rooms"]

    async def set_display_name(self, name: str) -> dict:
        await self.ensure_registered()
        content = {"displayname": name}
        return await self.client.request("PUT", f"/profile/{self.mxid}/displayname", content)

    async def set_presence(self, status: str = "online", ignore_cache: bool = False
                           ) -> Optional[dict]:
        await self.ensure_registered()
        if not ignore_cache and self.state_store.has_presence(self.mxid, status):
            return None
        content = {
            "presence": status
        }
        resp = await self.client.request("PUT", f"/presence/{self.mxid}/status", content)
        self.state_store.set_presence(self.mxid, status)
        return resp

    async def set_avatar(self, url: str) -> dict:
        await self.ensure_registered()
        content = {"avatar_url": url}
        return await self.client.request("PUT", f"/profile/{self.mxid}/avatar_url", content)

    async def upload_file(self, data: bytes, mime_type: Optional[str] = None) -> dict:
        await self.ensure_registered()
        if magic:
            mime_type = mime_type or magic.from_buffer(data, mime=True)
        return await self.client.request("POST", "", content=data,
                                         headers={"Content-Type": mime_type},
                                         api_path="/_matrix/media/r0/upload")

    async def download_file(self, url: str) -> bytes:
        await self.ensure_registered()
        url = self.client.get_download_url(url)
        async with self.client.session.get(url) as response:
            return await response.read()

    # endregion
    # region Room actions

    async def create_room(self, alias: Optional[str] = None, is_public: bool = False,
                          name: Optional[str] = None, topic: Optional[str] = None,
                          is_direct: bool = False, invitees: Optional[List[str]] = None,
                          initial_state: Optional[dict] = None,
                          guests_can_join: bool = False) -> dict:
        await self.ensure_registered()
        content = {
            "visibility": "private",
            "is_direct": is_direct,
            "preset": "public_chat" if is_public else "private_chat",
            "guests_can_join": guests_can_join,
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

        return await self.client.request("POST", "/createRoom", content)

    def _invite_direct(self, room_id: str, user_id: str) -> Awaitable[dict]:
        content = {"user_id": user_id}
        return self.client.request("POST", "/rooms/" + room_id + "/invite", content)

    async def invite(self, room_id: str, user_id: str, check_cache: bool = False
                     ) -> Optional[dict]:
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

    def set_room_avatar(self, room_id: str, avatar_url: str, info: Optional[dict] = None, **kwargs
                        ) -> Awaitable[dict]:
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

    async def get_power_levels(self, room_id: str, ignore_cache: bool = False) -> dict:
        await self.ensure_joined(room_id)
        if not ignore_cache:
            try:
                return self.state_store.get_power_levels(room_id)
            except KeyError:
                pass
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
        response = await self.client.request("GET", f"/rooms/{room_id}/state/m.room.pinned_events")
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
        return await self.client.request("GET", f"/rooms/{room_id}/event/{event_id}")

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
        resp = await self.client.request("PUT", f"/rooms/{room_id}/typing/{self.mxid}", content)
        self.state_store.set_typing(room_id, self.mxid, is_typing, timeout)
        return resp

    async def mark_read(self, room_id: str, event_id: str) -> dict:
        await self.ensure_joined(room_id)
        return await self.client.request("POST", f"/rooms/{room_id}/receipt/m.read/{event_id}",
                                         content={})

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
                  msgtype: str = "m.text", relates_to: Optional[str] = None, **kwargs
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

    async def get_room_members(self, room_id: str, allowed_memberships: Tuple[str] = ("join",)
                               ) -> List[str]:
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
