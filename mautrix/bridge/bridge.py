# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, Type, Dict, Any
from abc import ABC, abstractmethod
import sys

from aiohttp import web

from mautrix.types import RoomID, UserID
from mautrix.appservice import AppService, ASStateStore
from mautrix.api import HTTPAPI
from mautrix import __version__ as __mautrix_version__

from ..util.program import Program
from ..util.bridge_state import BridgeState, BridgeStateEvent, GlobalBridgeState
from .commands.manhole import ManholeState
from .config import BaseBridgeConfig
from .matrix import BaseMatrixHandler
from .portal import BasePortal
from .user import BaseUser
from .puppet import BasePuppet

try:
    from .state_store.sqlalchemy import SQLBridgeStateStore
    from ..util.db import Base

    import sqlalchemy as sql
    from sqlalchemy.engine.base import Engine
except ImportError:
    Base = SQLBridgeStateStore = sql = Engine = None

try:
    import uvloop
except ImportError:
    uvloop = None


class Bridge(Program, ABC):
    db: 'Engine'
    az: AppService
    state_store_class: Type[ASStateStore] = SQLBridgeStateStore
    state_store: ASStateStore
    config_class: Type[BaseBridgeConfig]
    config: BaseBridgeConfig
    matrix_class: Type[BaseMatrixHandler]
    matrix: BaseMatrixHandler
    repo_url: str
    markdown_version: str
    real_user_content_key: Optional[str] = None
    manhole: Optional[ManholeState]

    def __init__(self, module: str = None, name: str = None, description: str = None,
                 command: str = None, version: str = None,
                 real_user_content_key: Optional[str] = None,
                 config_class: Type[BaseBridgeConfig] = None,
                 matrix_class: Type[BaseMatrixHandler] = None,
                 state_store_class: Type[ASStateStore] = None) -> None:
        super().__init__(module, name, description, command, version, config_class)
        if real_user_content_key:
            self.real_user_content_key = real_user_content_key
        if matrix_class:
            self.matrix_class = matrix_class
        if state_store_class:
            self.state_store_class = state_store_class
        self.manhole = None

    def prepare_arg_parser(self) -> None:
        super().prepare_arg_parser()
        self.parser.add_argument("-g", "--generate-registration", action="store_true",
                                 help="generate registration and quit")
        self.parser.add_argument("-r", "--registration", type=str, default="registration.yaml",
                                 metavar="<path>",
                                 help="the path to save the generated registration to (not needed "
                                      "for running the bridge)")

    def preinit(self) -> None:
        super().preinit()
        if self.args.generate_registration:
            self.generate_registration()
            sys.exit(0)

    def prepare(self) -> None:
        super().prepare()
        self.prepare_db()
        self.prepare_appservice()
        self.prepare_bridge()

    def prepare_config(self) -> None:
        self.config = self.config_class(self.args.config, self.args.registration,
                                        self.args.base_config)
        if self.args.generate_registration:
            self.config._check_tokens = False
        self.load_and_update_config()

    def generate_registration(self) -> None:
        self.config.generate_registration()
        self.config.save()
        print(f"Registration generated and saved to {self.config.registration_path}")

    def make_state_store(self) -> None:
        if self.state_store_class is None:
            raise RuntimeError("state_store_class is not set")
        elif SQLBridgeStateStore and issubclass(self.state_store_class, SQLBridgeStateStore):
            self.state_store = self.state_store_class(self.get_puppet, self.get_double_puppet)
        else:
            self.state_store = self.state_store_class()

    def prepare_appservice(self) -> None:
        self.make_state_store()
        mb = 1024 ** 2
        default_http_retry_count = self.config.get("homeserver.http_retry_count", None)
        self.az = AppService(server=self.config["homeserver.address"],
                             domain=self.config["homeserver.domain"],
                             verify_ssl=self.config["homeserver.verify_ssl"],
                             connection_limit=self.config["homeserver.connection_limit"],

                             id=self.config["appservice.id"],
                             as_token=self.config["appservice.as_token"],
                             hs_token=self.config["appservice.hs_token"],

                             tls_cert=self.config.get("appservice.tls_cert", None),
                             tls_key=self.config.get("appservice.tls_key", None),

                             bot_localpart=self.config["appservice.bot_username"],
                             ephemeral_events=self.config["appservice.ephemeral_events"],

                             default_ua=f"{self.name}/{self.version} {HTTPAPI.default_ua}",
                             default_http_retry_count=default_http_retry_count,

                             log="mau.as",
                             loop=self.loop,

                             state_store=self.state_store,

                             real_user_content_key=self.real_user_content_key,

                             aiohttp_params={
                                 "client_max_size": self.config["appservice.max_body_size"] * mb
                             })
        self.az.app.router.add_post("/_matrix/app/com.beeper.bridge_state", self.get_bridge_state)

    def prepare_db(self) -> None:
        if not sql:
            raise RuntimeError("SQLAlchemy is not installed")
        self.db = sql.create_engine(self.config["appservice.database"],
                                    **self.config["appservice.database_opts"])
        Base.metadata.bind = self.db
        if not self.db.has_table("alembic_version"):
            self.log.critical("alembic_version table not found. "
                              "Did you forget to `alembic upgrade head`?")
            sys.exit(10)

    def prepare_bridge(self) -> None:
        self.matrix = self.matrix_class(bridge=self)

    async def start(self) -> None:
        self.log.debug("Starting appservice...")
        await self.az.start(self.config["appservice.hostname"], self.config["appservice.port"])
        await self.matrix.wait_for_connection()

        await self.matrix.init_encryption()
        self.add_startup_actions(self.matrix.init_as_bot())
        await super().start()
        self.az.ready = True

        status_endpoint = self.config["homeserver.status_endpoint"]
        if status_endpoint and await self.count_logged_in_users() == 0:
            state = BridgeState(state_event=BridgeStateEvent.UNCONFIGURED).fill()
            await state.send(status_endpoint, self.az.as_token, self.log)

    async def stop(self) -> None:
        if self.manhole:
            self.manhole.close()
            self.manhole = None
        await self.az.stop()
        await super().stop()
        if self.matrix.e2ee:
            await self.matrix.e2ee.stop()

    async def get_bridge_state(self, req: web.Request) -> web.Response:
        if not self.az._check_token(req):
            return web.json_response({"error": "Invalid auth token"}, status=401)
        try:
            user = await self.get_user(UserID(req.url.query["user_id"]), create=False)
        except KeyError:
            user = None
        if user is None:
            return web.json_response({"error": "User not found"}, status=404)
        try:
            states = await user.get_bridge_states()
        except NotImplementedError:
            return web.json_response({"error": "Bridge status not implemented"}, status=501)
        for state in states:
            await user.fill_bridge_state(state)
        global_state = BridgeState(state_event=BridgeStateEvent.RUNNING).fill()
        evt = GlobalBridgeState(remote_states={state.remote_id: state for state in states},
                                bridge_state=global_state)
        return web.json_response(evt.serialize())

    @abstractmethod
    async def get_user(self, user_id: UserID, create: bool = True) -> Optional['BaseUser']:
        pass

    @abstractmethod
    async def get_portal(self, room_id: RoomID) -> Optional['BasePortal']:
        pass

    @abstractmethod
    async def get_puppet(self, user_id: UserID, create: bool = False) -> Optional['BasePuppet']:
        pass

    @abstractmethod
    async def get_double_puppet(self, user_id: UserID) -> Optional['BasePuppet']:
        pass

    @abstractmethod
    def is_bridge_ghost(self, user_id: UserID) -> bool:
        pass

    @abstractmethod
    async def count_logged_in_users(self) -> int:
        return 0

    async def manhole_global_namespace(self, user_id: UserID) -> Dict[str, Any]:
        own_user = await self.get_user(user_id, create=False)
        try:
            own_puppet = await own_user.get_puppet()
        except NotImplementedError:
            own_puppet = None
        return {
            "bridge": self,
            "manhole": self.manhole,
            "own_user": own_user,
            "own_puppet": own_puppet,
        }

    @property
    def manhole_banner_python_version(self) -> str:
        return f"Python {sys.version} on {sys.platform}"

    @property
    def manhole_banner_program_version(self) -> str:
        return f"{self.name} {self.version} with mautrix-python {__mautrix_version__}"

    def manhole_banner(self, user_id: UserID) -> str:
        return (f"{self.manhole_banner_python_version}\n"
                f"{self.manhole_banner_program_version}\n\n"
                f"Manhole opened by {user_id}\n")
