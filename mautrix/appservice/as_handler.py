# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Partly based on github.com/Cadair/python-appservice-framework (MIT license)
from __future__ import annotations

from typing import Any, Awaitable, Callable
from json import JSONDecodeError
import asyncio
import json
import logging

from aiohttp import web

from mautrix.types import (
    JSON,
    DeviceLists,
    DeviceOTKCount,
    EphemeralEvent,
    Event,
    RoomAlias,
    SerializerError,
    UserID,
)

HandlerFunc = Callable[[Event], Awaitable]


class AppServiceServerMixin:
    loop: asyncio.AbstractEventLoop
    log: logging.Logger

    hs_token: str
    ephemeral_events: bool

    query_user: Callable[[UserID], JSON]
    query_alias: Callable[[RoomAlias], JSON]

    transactions: set[str]
    event_handlers: list[HandlerFunc]

    def __init__(self, ephemeral_events: bool = False) -> None:
        self.transactions = set()
        self.event_handlers = []
        self.ephemeral_events = ephemeral_events

        async def default_query_handler(_):
            return None

        self.query_user = default_query_handler
        self.query_alias = default_query_handler

    def register_routes(self, app: web.Application) -> None:
        app.router.add_route(
            "PUT", "/transactions/{transaction_id}", self._http_handle_transaction
        )
        app.router.add_route("GET", "/rooms/{alias}", self._http_query_alias)
        app.router.add_route("GET", "/users/{user_id}", self._http_query_user)
        app.router.add_route(
            "PUT", "/_matrix/app/v1/transactions/{transaction_id}", self._http_handle_transaction
        )
        app.router.add_route("GET", "/_matrix/app/v1/rooms/{alias}", self._http_query_alias)
        app.router.add_route("GET", "/_matrix/app/v1/users/{user_id}", self._http_query_user)

    def _check_token(self, request: web.Request) -> bool:
        try:
            token = request.rel_url.query["access_token"]
        except KeyError:
            try:
                token = request.headers["Authorization"].removeprefix("Bearer ")
            except (KeyError, AttributeError):
                return False

        if token != self.hs_token:
            return False

        return True

    async def _http_query_user(self, request: web.Request) -> web.Response:
        if not self._check_token(request):
            return web.json_response({"error": "Invalid auth token"}, status=401)

        try:
            user_id = request.match_info["user_id"]
        except KeyError:
            return web.json_response({"error": "Missing user_id parameter"}, status=400)

        try:
            response = await self.query_user(user_id)
        except Exception:
            self.log.exception("Exception in user query handler")
            return web.json_response({"error": "Internal appservice error"}, status=500)

        if not response:
            return web.json_response({}, status=404)
        return web.json_response(response)

    async def _http_query_alias(self, request: web.Request) -> web.Response:
        if not self._check_token(request):
            return web.json_response({"error": "Invalid auth token"}, status=401)

        try:
            alias = request.match_info["alias"]
        except KeyError:
            return web.json_response({"error": "Missing alias parameter"}, status=400)

        try:
            response = await self.query_alias(alias)
        except Exception:
            self.log.exception("Exception in alias query handler")
            return web.json_response({"error": "Internal appservice error"}, status=500)

        if not response:
            return web.json_response({}, status=404)
        return web.json_response(response)

    @staticmethod
    def _get_with_fallback(
        json: Dict[str, Any], field: str, unstable_prefix: str, default: Any = None
    ) -> Any:
        try:
            return json.pop(field)
        except KeyError:
            try:
                return json.pop(f"{unstable_prefix}.{field}")
            except KeyError:
                return default

    async def _read_transaction_header(self, request: web.Request) -> tuple[str, dict[str, Any]]:
        if not self._check_token(request):
            raise web.HTTPUnauthorized(
                content_type="application/json",
                text=json.dumps({"error": "Invalid auth token", "errcode": "M_UNKNOWN_TOKEN"}),
            )

        transaction_id = request.match_info["transaction_id"]
        if transaction_id in self.transactions:
            raise web.HTTPOk(content_type="application/json", text="{}")

        try:
            return transaction_id, await request.json()
        except JSONDecodeError:
            raise web.HTTPBadRequest(
                content_type="application/json",
                text=json.dumps({"error": "Body is not JSON", "errcode": "M_NOT_JSON"}),
            )

    async def _http_handle_transaction(self, request: web.Request) -> web.Response:
        transaction_id, data = await self._read_transaction_header(request)

        try:
            events = data.pop("events")
        except KeyError:
            raise web.HTTPBadRequest(
                content_type="application/json",
                text=json.dumps(
                    {"error": "Missing events object in body", "errcode": "M_BAD_JSON"}
                ),
            )

        ephemeral = (
            self._get_with_fallback(data, "ephemeral", "de.sorunome.msc2409")
            if self.ephemeral_events
            else None
        )
        device_lists = DeviceLists.deserialize(
            self._get_with_fallback(data, "device_lists", "org.matrix.msc3202")
        )
        otk_counts = {
            user_id: DeviceOTKCount.deserialize(count)
            for user_id, count in self._get_with_fallback(
                data, "device_one_time_keys_count", "org.matrix.msc3202", default={}
            ).items()
        }

        try:
            output = await self.handle_transaction(
                transaction_id,
                events=events,
                extra_data=data,
                ephemeral=ephemeral,
                device_lists=device_lists,
                device_otk_count=otk_counts,
            )
        except Exception:
            self.log.exception("Exception in transaction handler")
            output = None

        self.transactions.add(transaction_id)

        return web.json_response(output or {})

    @staticmethod
    def _fix_prev_content(raw_event: JSON) -> None:
        try:
            raw_event["unsigned"]["prev_content"]
        except KeyError:
            try:
                raw_event.setdefault("unsigned", {})["prev_content"] = raw_event["prev_content"]
            except KeyError:
                pass

    async def handle_transaction(
        self,
        txn_id: str,
        *,
        events: list[JSON],
        extra_data: JSON,
        ephemeral: list[JSON] | None = None,
        device_otk_count: dict[UserID, DeviceOTKCount] | None = None,
        device_lists: DeviceLists | None = None,
    ) -> JSON:
        for raw_edu in ephemeral or []:
            try:
                edu = EphemeralEvent.deserialize(raw_edu)
            except SerializerError:
                self.log.exception("Failed to deserialize ephemeral event %s", raw_edu)
            else:
                self.handle_matrix_event(edu)
        for raw_event in events:
            try:
                self._fix_prev_content(raw_event)
                event = Event.deserialize(raw_event)
            except SerializerError:
                self.log.exception("Failed to deserialize event %s", raw_event)
            else:
                self.handle_matrix_event(event)
        return {}

    def handle_matrix_event(self, event: Event) -> None:
        if event.type.is_state and event.state_key is None:
            self.log.debug(f"Not sending {event.event_id} to handlers: expected state_key.")
            return

        async def try_handle(handler_func: HandlerFunc):
            try:
                await handler_func(event)
            except Exception:
                self.log.exception("Exception in Matrix event handler")

        for handler in self.event_handlers:
            asyncio.create_task(try_handle(handler))

    def matrix_event_handler(self, func: HandlerFunc) -> HandlerFunc:
        self.event_handlers.append(func)
        return func
