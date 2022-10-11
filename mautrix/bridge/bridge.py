# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any
from abc import ABC, abstractmethod
from enum import Enum
import sys

from aiohttp import web

from mautrix import __version__ as __mautrix_version__
from mautrix.api import HTTPAPI
from mautrix.appservice import AppService, ASStateStore
from mautrix.client.state_store.asyncpg import PgStateStore as PgClientStateStore
from mautrix.errors import MExclusive, MUnknownToken
from mautrix.types import RoomID, UserID
from mautrix.util.async_db import Database, DatabaseException, UpgradeTable
from mautrix.util.bridge_state import BridgeState, BridgeStateEvent, GlobalBridgeState
from mautrix.util.program import Program

from .. import bridge as br
from .state_store.asyncpg import PgBridgeStateStore

try:
    import uvloop
except ImportError:
    uvloop = None


class HomeserverSoftware(Enum):
    STANDARD = "standard"
    ASMUX = "asmux"
    HUNGRY = "hungry"

    @property
    def is_hungry(self) -> bool:
        return self == self.HUNGRY

    @property
    def is_asmux(self) -> bool:
        return self == self.ASMUX


class Bridge(Program, ABC):
    db: Database
    az: AppService
    state_store_class: type[ASStateStore] = PgBridgeStateStore
    state_store: ASStateStore
    upgrade_table: UpgradeTable
    config_class: type[br.BaseBridgeConfig]
    config: br.BaseBridgeConfig
    matrix_class: type[br.BaseMatrixHandler]
    matrix: br.BaseMatrixHandler
    repo_url: str
    markdown_version: str
    manhole: br.commands.manhole.ManholeState | None
    homeserver_software: HomeserverSoftware

    def __init__(
        self,
        module: str = None,
        name: str = None,
        description: str = None,
        command: str = None,
        version: str = None,
        config_class: type[br.BaseBridgeConfig] = None,
        matrix_class: type[br.BaseMatrixHandler] = None,
        state_store_class: type[ASStateStore] = None,
    ) -> None:
        super().__init__(module, name, description, command, version, config_class)
        if matrix_class:
            self.matrix_class = matrix_class
        if state_store_class:
            self.state_store_class = state_store_class
        self.manhole = None

    def prepare_arg_parser(self) -> None:
        super().prepare_arg_parser()
        self.parser.add_argument(
            "-g",
            "--generate-registration",
            action="store_true",
            help="generate registration and quit",
        )
        self.parser.add_argument(
            "-r",
            "--registration",
            type=str,
            default="registration.yaml",
            metavar="<path>",
            help=(
                "the path to save the generated registration to "
                "(not needed for running the bridge)"
            ),
        )
        self.parser.add_argument(
            "--ignore-unsupported-database",
            action="store_true",
            help="Run even if the database schema is too new",
        )
        self.parser.add_argument(
            "--ignore-foreign-tables",
            action="store_true",
            help="Run even if the database contains tables from other programs (like Synapse)",
        )

    def preinit(self) -> None:
        super().preinit()
        if self.args.generate_registration:
            self.generate_registration()
            sys.exit(0)

    def prepare(self) -> None:
        if self.config.env:
            self.log.debug(
                "Loaded config overrides from environment: %s", list(self.config.env.keys())
            )
        super().prepare()
        try:
            self.homeserver_software = HomeserverSoftware(self.config["homeserver.software"])
        except Exception:
            self.log.fatal("Invalid value for homeserver.software in config")
            sys.exit(11)
        self.prepare_db()
        self.prepare_appservice()
        self.prepare_bridge()

    def prepare_config(self) -> None:
        self.config = self.config_class(
            self.args.config,
            self.args.registration,
            self.args.base_config,
            env_prefix=self.module.upper(),
        )
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
        elif issubclass(self.state_store_class, PgBridgeStateStore):
            self.state_store = self.state_store_class(
                self.db, self.get_puppet, self.get_double_puppet
            )
        else:
            self.state_store = self.state_store_class()

    def prepare_appservice(self) -> None:
        self.make_state_store()
        mb = 1024**2
        default_http_retry_count = self.config.get("homeserver.http_retry_count", None)
        if self.name not in HTTPAPI.default_ua:
            HTTPAPI.default_ua = f"{self.name}/{self.version} {HTTPAPI.default_ua}"
        self.az = AppService(
            server=self.config["homeserver.address"],
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
            encryption_events=self.config["bridge.encryption.appservice"],
            default_ua=HTTPAPI.default_ua,
            default_http_retry_count=default_http_retry_count,
            log="mau.as",
            loop=self.loop,
            state_store=self.state_store,
            bridge_name=self.name,
            aiohttp_params={"client_max_size": self.config["appservice.max_body_size"] * mb},
        )
        self.az.app.router.add_post("/_matrix/app/com.beeper.bridge_state", self.get_bridge_state)

    def prepare_db(self) -> None:
        if not hasattr(self, "upgrade_table") or not self.upgrade_table:
            raise RuntimeError("upgrade_table is not set")
        self.db = Database.create(
            self.config["appservice.database"],
            upgrade_table=self.upgrade_table,
            db_args=self.config["appservice.database_opts"],
            owner_name=self.name,
            ignore_foreign_tables=self.args.ignore_foreign_tables,
        )

    def prepare_bridge(self) -> None:
        self.matrix = self.matrix_class(bridge=self)

    def _log_db_error(self, e: Exception) -> None:
        self.log.critical("Failed to initialize database", exc_info=e)
        if isinstance(e, DatabaseException) and e.explanation:
            self.log.info(e.explanation)
        sys.exit(25)

    async def start_db(self) -> None:
        if hasattr(self, "db") and isinstance(self.db, Database):
            self.log.debug("Starting database...")
            ignore_unsupported = self.args.ignore_unsupported_database
            self.db.upgrade_table.allow_unsupported = ignore_unsupported
            try:
                await self.db.start()
                if isinstance(self.state_store, PgClientStateStore):
                    self.state_store.upgrade_table.allow_unsupported = ignore_unsupported
                    await self.state_store.upgrade_table.upgrade(self.db)
                if self.matrix.e2ee:
                    self.matrix.e2ee.crypto_db.allow_unsupported = ignore_unsupported
                    self.matrix.e2ee.crypto_db.override_pool(self.db)
            except Exception as e:
                self._log_db_error(e)

    async def stop_db(self) -> None:
        if hasattr(self, "db") and isinstance(self.db, Database):
            await self.db.stop()

    async def start(self) -> None:
        await self.start_db()

        self.log.debug("Starting appservice...")
        await self.az.start(self.config["appservice.hostname"], self.config["appservice.port"])
        try:
            await self.matrix.wait_for_connection()
        except MUnknownToken:
            self.log.critical(
                "The as_token was not accepted. Is the registration file installed "
                "in your homeserver correctly?"
            )
            sys.exit(16)
        except MExclusive:
            self.log.critical(
                "The as_token was accepted, but the /register request was not. "
                "Are the homeserver domain and username template in the config "
                "correct, and do they match the values in the registration?"
            )
            sys.exit(16)

        await self.matrix.init_encryption()
        self.add_startup_actions(self.matrix.init_as_bot())
        await super().start()
        self.az.ready = True

        status_endpoint = self.config["homeserver.status_endpoint"]
        if status_endpoint and await self.count_logged_in_users() == 0:
            state = BridgeState(state_event=BridgeStateEvent.UNCONFIGURED).fill()
            await state.send(status_endpoint, self.az.as_token, self.log)

    async def system_exit(self) -> None:
        if hasattr(self, "db") and isinstance(self.db, Database):
            self.log.trace("Stopping database due to SystemExit")
            await self.db.stop()

    async def stop(self) -> None:
        if self.manhole:
            self.manhole.close()
            self.manhole = None
        await self.az.stop()
        await super().stop()
        if self.matrix.e2ee:
            await self.matrix.e2ee.stop()
        await self.stop_db()

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
        evt = GlobalBridgeState(
            remote_states={state.remote_id: state for state in states}, bridge_state=global_state
        )
        return web.json_response(evt.serialize())

    @abstractmethod
    async def get_user(self, user_id: UserID, create: bool = True) -> br.BaseUser | None:
        pass

    @abstractmethod
    async def get_portal(self, room_id: RoomID) -> br.BasePortal | None:
        pass

    @abstractmethod
    async def get_puppet(self, user_id: UserID, create: bool = False) -> br.BasePuppet | None:
        pass

    @abstractmethod
    async def get_double_puppet(self, user_id: UserID) -> br.BasePuppet | None:
        pass

    @abstractmethod
    def is_bridge_ghost(self, user_id: UserID) -> bool:
        pass

    @abstractmethod
    async def count_logged_in_users(self) -> int:
        return 0

    async def manhole_global_namespace(self, user_id: UserID) -> dict[str, Any]:
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
        return (
            f"{self.manhole_banner_python_version}\n"
            f"{self.manhole_banner_program_version}\n\n"
            f"Manhole opened by {user_id}\n"
        )
