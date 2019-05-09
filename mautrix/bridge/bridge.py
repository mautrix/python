# Copyright (c) 2019 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Iterable, Awaitable, Optional, Type
import argparse
import logging
import logging.config
import asyncio
import signal
import copy
import sys

import sqlalchemy as sql
from sqlalchemy.engine.base import Engine

from mautrix.appservice import AppService
from .db import SQLStateStore, Base
from .config import BaseBridgeConfig
from .matrix import BaseMatrixHandler

try:
    import uvloop
except ImportError:
    uvloop = None


class Bridge:
    loop: asyncio.AbstractEventLoop
    log: logging.Logger
    parser: argparse.ArgumentParser
    db: Engine
    az: AppService
    state_store_class: Type[SQLStateStore] = SQLStateStore
    state_store: SQLStateStore
    config_class: Type[BaseBridgeConfig]
    config: BaseBridgeConfig
    matrix_class: Type[BaseMatrixHandler]
    matrix: BaseMatrixHandler
    startup_actions: Optional[Iterable[Awaitable]]
    shutdown_actions: Optional[Iterable[Awaitable]]
    name: str
    version: str
    command: str
    description: str
    real_user_content_key: Optional[str] = None

    def __init__(self, name: str = None, description: str = None, command: str = None,
                 version: str = None, real_user_content_key: Optional[str] = None,
                 config_class: Type[BaseBridgeConfig] = None,
                 matrix_class: Type[BaseMatrixHandler] = None,
                 state_store_class: Type[SQLStateStore] = None) -> None:
        self.parser = argparse.ArgumentParser(description=description or self.description,
                                              prog=command or self.command)
        self.parser.add_argument("-c", "--config", type=str, default="config.yaml",
                                 metavar="<path>", help="the path to your config file")
        self.parser.add_argument("-b", "--base-config", type=str, default="example-config.yaml",
                                 metavar="<path>", help="the path to the example config "
                                                        "(for automatic config updates)")
        self.parser.add_argument("-g", "--generate-registration", action="store_true",
                                 help="generate registration and quit")
        self.parser.add_argument("-r", "--registration", type=str, default="registration.yaml",
                                 metavar="<path>",
                                 help="the path to save the generated registration to (not needed "
                                      "for running the bridge)")

        if name:
            self.name = name
        if real_user_content_key:
            self.real_user_content_key = real_user_content_key
        if version:
            self.version = version
        if config_class:
            self.config_class = config_class
        if matrix_class:
            self.matrix_class = matrix_class
        if state_store_class:
            self.state_store_class = state_store_class
        self.startup_actions = None
        self.shutdown_actions = None

    def run(self) -> None:
        self._prepare()
        self._run()

    def _prepare(self) -> None:
        args = self.parser.parse_args()

        self.prepare_config(args.config, args.registration, args.base_config)

        if args.generate_registration:
            self.generate_registration()
            sys.exit(0)

        self.prepare_log()
        self.prepare_loop()
        self.prepare_appservice()
        self.prepare_db()
        self.prepare_bridge()

    def prepare_config(self, config: str, registration: str, base_config: str) -> None:
        self.config = self.config_class(config, registration, base_config)
        self.config.load()
        self.config.update()

    def generate_registration(self) -> None:
        self.config.generate_registration()
        self.config.save()
        print(f"Registration generated and saved to {self.config.registration_path}")

    def prepare_log(self) -> None:
        logging.config.dictConfig(copy.deepcopy(self.config["logging"]))
        self.log = logging.getLogger("mau.init")
        self.log.debug(f"Initializing {self.name} {self.version}")

    def prepare_loop(self) -> None:
        if uvloop:
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            self.log.debug("Using uvloop for asyncio")

        self.loop = asyncio.get_event_loop()

    def prepare_appservice(self) -> None:
        self.state_store = self.state_store_class()
        mb = 1024 ** 2
        self.az = AppService(server=self.config["homeserver.address"],
                             domain=self.config["homeserver.domain"],
                             verify_ssl=self.config["homeserver.verify_ssl"],

                             as_token=self.config["appservice.as_token"],
                             hs_token=self.config["appservice.hs_token"],

                             bot_localpart=self.config["appservice.bot_username"],

                             log="mau.as",
                             loop=self.loop,

                             state_store=self.state_store,

                             real_user_content_key=self.real_user_content_key,

                             aiohttp_params={
                                 "client_max_size": self.config["appservice.max_body_size"] * mb
                             })

        signal.signal(signal.SIGINT, signal.default_int_handler)
        signal.signal(signal.SIGTERM, signal.default_int_handler)

    def prepare_db(self) -> None:
        self.db = sql.create_engine(self.config["appservice.database"])
        Base.metadata.bind = self.db

    def prepare_bridge(self) -> None:
        self.matrix = self.matrix_class(az=self.az, config=self.config, loop=self.loop)

    def _run(self) -> None:
        try:
            self.log.debug("Running startup actions...")
            self.loop.run_until_complete(self.start())
            self.log.debug("Startup actions complete, running forever")
            self.loop.run_forever()
        except KeyboardInterrupt:
            self.log.debug("Interrupt received, stopping...")
            self.loop.run_until_complete(self.stop())
            self.prepare_shutdown()
            self.log.info("Everything stopped, shutting down")
            sys.exit(0)
        except Exception:
            self.log.critical("Unexpected error in main event loop", exc_info=True)
            sys.exit(1)

    async def start(self) -> None:
        self.log.debug("Starting appservice...")
        await self.az.start(self.config["appservice.hostname"], self.config["appservice.port"])
        await asyncio.gather(self.matrix.init_as_bot(), *(self.startup_actions or []),
                             loop=self.loop)

    async def stop(self) -> None:
        await self.az.stop()
        await asyncio.gather(*(self.startup_actions or []), loop=self.loop)

    def prepare_shutdown(self) -> None:
        pass
