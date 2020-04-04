# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Optional, Type
from itertools import chain
import sys

import sqlalchemy as sql
from sqlalchemy.engine.base import Engine

from mautrix.appservice import AppService
from ..util.db import Base
from ..util.program import Program
from .db import SQLStateStore
from .config import BaseBridgeConfig
from .matrix import BaseMatrixHandler

try:
    import uvloop
except ImportError:
    uvloop = None


class Bridge(Program):
    db: Engine
    az: AppService
    state_store_class: Type[SQLStateStore] = SQLStateStore
    state_store: SQLStateStore
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
                 state_store_class: Type[SQLStateStore] = None) -> None:
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
        self.prepare_appservice()
        self.prepare_db()
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

    def prepare_appservice(self) -> None:
        self.state_store = self.state_store_class()
        mb = 1024 ** 2
        self.az = AppService(server=self.config["homeserver.address"],
                             domain=self.config["homeserver.domain"],
                             verify_ssl=self.config["homeserver.verify_ssl"],

                             as_token=self.config["appservice.as_token"],
                             hs_token=self.config["appservice.hs_token"],

                             tls_cert=self.config.get("appservice.tls_cert", None),
                             tls_key=self.config.get("appservice.tls_key", None),

                             bot_localpart=self.config["appservice.bot_username"],

                             log="mau.as",
                             loop=self.loop,

                             state_store=self.state_store,

                             real_user_content_key=self.real_user_content_key,

                             aiohttp_params={
                                 "client_max_size": self.config["appservice.max_body_size"] * mb
                             })

    def prepare_db(self) -> None:
        self.db = sql.create_engine(self.config["appservice.database"])
        Base.metadata.bind = self.db
        if not self.db.has_table("alembic_version"):
            self.log.critical("alembic_version table not found. "
                              "Did you forget to `alembic upgrade head`?")
            sys.exit(10)

    def prepare_bridge(self) -> None:
        self.matrix = self.matrix_class(az=self.az, config=self.config, loop=self.loop, bridge=self)

    async def start(self) -> None:
        self.log.debug("Starting appservice...")
        await self.az.start(self.config["appservice.hostname"], self.config["appservice.port"])
        await self.matrix.wait_for_connection()
        self.add_startup_actions(self.matrix.init_as_bot())
        await super().start()
        self.az.ready = True

    async def stop(self) -> None:
        await self.az.stop()
        await super().stop()
