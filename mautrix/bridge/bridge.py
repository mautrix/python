# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, Type, Any
from abc import ABC, abstractmethod
import sys

from mautrix.types import RoomID, UserID
from mautrix.appservice import AppService, ASStateStore

from ..util.program import Program
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
        self.az = AppService(server=self.config["homeserver.address"],
                             domain=self.config["homeserver.domain"],
                             verify_ssl=self.config["homeserver.verify_ssl"],

                             id=self.config["appservice.id"],
                             as_token=self.config["appservice.as_token"],
                             hs_token=self.config["appservice.hs_token"],

                             tls_cert=self.config.get("appservice.tls_cert", None),
                             tls_key=self.config.get("appservice.tls_key", None),

                             bot_localpart=self.config["appservice.bot_username"],
                             ephemeral_events=self.config["appservice.ephemeral_events"],

                             log="mau.as",
                             loop=self.loop,

                             state_store=self.state_store,

                             real_user_content_key=self.real_user_content_key,

                             aiohttp_params={
                                 "client_max_size": self.config["appservice.max_body_size"] * mb
                             })

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

    async def stop(self) -> None:
        await self.az.stop()
        await super().stop()
        if self.matrix.e2ee:
            await self.matrix.e2ee.stop()

    @abstractmethod
    async def get_user(self, user_id: UserID, create: bool = True) -> 'BaseUser':
        pass

    @abstractmethod
    async def get_portal(self, room_id: RoomID) -> 'BasePortal':
        pass

    @abstractmethod
    async def get_puppet(self, user_id: UserID, create: bool = False) -> 'BasePuppet':
        pass

    @abstractmethod
    async def get_double_puppet(self, user_id: UserID) -> 'BasePuppet':
        pass

    @abstractmethod
    def is_bridge_ghost(self, user_id: UserID) -> bool:
        pass
