# Copyright (c) 2023 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Partly based on github.com/Cadair/python-appservice-framework (MIT license)
from __future__ import annotations

from typing import Any, Awaitable, Callable
from json import JSONDecodeError
import json
import logging

from aiohttp import web

from mautrix.types import (
    JSON,
    ASToDeviceEvent,
    DeviceID,
    DeviceLists,
    DeviceOTKCount,
    EphemeralEvent,
    Event,
    EventType,
    RoomAlias,
    SerializerError,
    UserID,
)
from mautrix.util import background_task

HandlerFunc = Callable[[Event], Awaitable]


class AppServiceServerMixin:
    log: logging.Logger

    hs_token: str
    ephemeral_events: bool
    encryption_events: bool
    synchronous_handlers: bool

    query_user: Callable[[UserID], JSON]
    query_alias: Callable[[RoomAlias], JSON]

    transactions: set[str]
    event_handlers: list[HandlerFunc]
    to_device_handler: HandlerFunc | None
    otk_handler: Callable[[dict[UserID, dict[DeviceID, DeviceOTKCount]]], Awaitable] | None
    device_list_handler: Callable[[DeviceLists], Awaitable] | None

    def __init__(
        self,
        ephemeral_events: bool = False,
        encryption_events: bool = False,
        log: logging.Logger | None = None,
        hs_token: str | None = None,
    ) -> None:
        if log is not None:
            self.log = log
        if hs_token is not None:
            self.hs_token = hs_token
        self.transactions = set()
        self.event_handlers = []
        self.to_device_handler = None
        self.otk_handler = None
        self.device_list_handler = None
        self.ephemeral_events = ephemeral_events
        self.encryption_events = encryption_events
        self.synchronous_handlers = False

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
        app.router.add_route("POST", "/_matrix/app/v1/ping", self._http_ping)

    def _check_token(self, request: web.Request) -> bool:
        try:
            token = request.rel_url.query["access_token"]
        except KeyError:
            try:
                token = request.headers["Authorization"].removeprefix("Bearer ")
            except KeyError:
                self.log.debug("No access_token nor Authorization header in request")
                return False

        if token != self.hs_token:
            self.log.debug(f"Incorrect hs_token in request")
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

    async def _http_ping(self, request: web.Request) -> web.Response:
        if not self._check_token(request):
            raise web.HTTPUnauthorized(
                content_type="application/json",
                text=json.dumps({"error": "Invalid auth token", "errcode": "M_UNKNOWN_TOKEN"}),
            )
        try:
            body = await request.json()
        except JSONDecodeError:
            raise web.HTTPBadRequest(
                content_type="application/json",
                text=json.dumps({"error": "Body is not JSON", "errcode": "M_NOT_JSON"}),
            )
        txn_id = body.get("transaction_id")
        self.log.info(f"Received ping from homeserver with transaction ID {txn_id}")
        return web.json_response({})

    @staticmethod
    def _get_with_fallback(
        json: dict[str, Any], field: str, unstable_prefix: str, default: Any = None
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

        txn_content_log = []
        try:
            events = data.pop("events")
            if events:
                txn_content_log.append(f"{len(events)} PDUs")
        except KeyError:
            raise web.HTTPBadRequest(
                content_type="application/json",
                text=json.dumps(
                    {"error": "Missing events object in body", "errcode": "M_BAD_JSON"}
                ),
            )

        if self.ephemeral_events:
            ephemeral = self._get_with_fallback(data, "ephemeral", "de.sorunome.msc2409")
            if ephemeral:
                txn_content_log.append(f"{len(ephemeral)} EDUs")
        else:
            ephemeral = None
        if self.encryption_events:
            to_device = self._get_with_fallback(data, "to_device", "de.sorunome.msc2409")
            device_lists = DeviceLists.deserialize(
                self._get_with_fallback(data, "device_lists", "org.matrix.msc3202")
            )
            otk_counts = {
                user_id: {
                    device_id: DeviceOTKCount.deserialize(count)
                    for device_id, count in devices.items()
                }
                for user_id, devices in self._get_with_fallback(
                    data, "device_one_time_keys_count", "org.matrix.msc3202", default={}
                ).items()
            }
            if to_device:
                txn_content_log.append(f"{len(to_device)} to-device events")
            if device_lists.changed:
                txn_content_log.append(f"{len(device_lists.changed)} device list changes")
            if otk_counts:
                txn_content_log.append(
                    f"{sum(len(vals) for vals in otk_counts.values())} OTK counts"
                )
        else:
            otk_counts = {}
            device_lists = None
            to_device = None

        if len(txn_content_log) > 2:
            txn_content_log = [", ".join(txn_content_log[:-1]), txn_content_log[-1]]
        if not txn_content_log:
            txn_description = "nothing?"
        else:
            txn_description = " and ".join(txn_content_log)
        self.log.debug(f"Handling transaction {transaction_id} with {txn_description}")

        try:
            output = await self.handle_transaction(
                transaction_id,
                events=events,
                extra_data=data,
                ephemeral=ephemeral,
                to_device=to_device,
                device_lists=device_lists,
                otk_counts=otk_counts,
            )
        except Exception:
            self.log.exception("Exception in transaction handler")
            output = None
        finally:
            self.log.debug(f"Finished handling transaction {transaction_id}")

        self.transactions.add(transaction_id)

        return web.json_response(output or {})

    @staticmethod
    def _fix_prev_content(raw_event: JSON) -> None:
        try:
            if raw_event["unsigned"] is None:
                del raw_event["unsigned"]
        except KeyError:
            pass
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
        to_device: list[JSON] | None = None,
        otk_counts: dict[UserID, dict[DeviceID, DeviceOTKCount]] | None = None,
        device_lists: DeviceLists | None = None,
    ) -> JSON:
        for raw_td in to_device or []:
            try:
                td = ASToDeviceEvent.deserialize(raw_td)
            except SerializerError:
                self.log.exception("Failed to deserialize to-device event %s", raw_td)
            else:
                try:
                    await self.to_device_handler(td)
                except Exception:
                    self.log.exception("Exception in Matrix to-device event handler")
        if device_lists and self.device_list_handler:
            try:
                await self.device_list_handler(device_lists)
            except Exception:
                self.log.exception("Exception in Matrix device list change handler")
        if otk_counts and self.otk_handler:
            try:
                await self.otk_handler(otk_counts)
            except Exception:
                self.log.exception("Exception in Matrix OTK count handler")
        for raw_edu in ephemeral or []:
            try:
                edu = EphemeralEvent.deserialize(raw_edu)
            except SerializerError:
                self.log.exception("Failed to deserialize ephemeral event %s", raw_edu)
            else:
                await self.handle_matrix_event(edu, ephemeral=True)
        for raw_event in events:
            try:
                self._fix_prev_content(raw_event)
                event = Event.deserialize(raw_event)
            except SerializerError:
                self.log.exception("Failed to deserialize event %s", raw_event)
            else:
                await self.handle_matrix_event(event)
        return {}

    async def handle_matrix_event(self, event: Event, ephemeral: bool = False) -> None:
        if ephemeral:
            event.type = event.type.with_class(EventType.Class.EPHEMERAL)
        elif getattr(event, "state_key", None) is not None:
            event.type = event.type.with_class(EventType.Class.STATE)
        else:
            event.type = event.type.with_class(EventType.Class.MESSAGE)

        async def try_handle(handler_func: HandlerFunc):
            try:
                await handler_func(event)
            except Exception:
                self.log.exception("Exception in Matrix event handler")

        if self.synchronous_handlers:
            for handler in self.event_handlers:
                await handler(event)
        else:
            for handler in self.event_handlers:
                background_task.create(try_handle(handler))

    def matrix_event_handler(self, func: HandlerFunc) -> HandlerFunc:
        self.event_handlers.append(func)
        return func
