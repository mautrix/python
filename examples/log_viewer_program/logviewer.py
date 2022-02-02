from mautrix.errors import MExclusive, MUnknownToken
from mautrix.bridge.matrix import BaseMatrixHandler
from mautrix.bridge.config import BaseBridgeConfig
from mautrix.appservice import AppService
from mautrix.util.program import Program
from typing import Optional, Type
from mautrix.types import UserID
from mautrix.api import HTTPAPI
from aiohttp import web
import asyncio
import sys


class LogViewer(Program):
    az: AppService
    matrix_class: Type[BaseMatrixHandler]
    matrix: BaseMatrixHandler
    periodic_reconnect_task: Optional[asyncio.Task]
    config_class: Type[BaseBridgeConfig]
    config: BaseBridgeConfig

    def __init__(
        self,
        module: str = None,
        name: str = None,
        description: str = None,
        command: str = None,
        version: str = None,
        config_class: Type[BaseBridgeConfig] = None,
        matrix_class: Type[BaseMatrixHandler] = None,
    ) -> None:
        super().__init__(module, name, description, command, version, config_class)
        if matrix_class:
            self.matrix_class = matrix_class
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
            help="the path to save the generated registration to (not needed "
            "for running the bridge)",
        )

    def preinit(self) -> None:
        super().preinit()
        if self.args.generate_registration:
            self.generate_registration()
            sys.exit(0)

    def prepare(self) -> None:
        super().prepare()
        # self.prepare_db()
        self.prepare_appservice()
        self.matrix = self.matrix_class(bridge=self)

    def prepare_config(self) -> None:
        self.config = self.config_class(
            self.args.config, self.args.registration, self.args.base_config
        )
        if self.args.generate_registration:
            self.config._check_tokens = False
        self.load_and_update_config()

    def generate_registration(self) -> None:
        self.config.generate_registration()
        self.config.save()
        print(f"Registration generated and saved to {self.config.registration_path}")

    def prepare_appservice(self) -> None:
        mb = 1024 ** 2
        default_http_retry_count = self.config.get("homeserver.http_retry_count", None)
        if self.name not in HTTPAPI.default_ua:
            HTTPAPI.default_ua = f"{self.name}/{self.version} {HTTPAPI.default_ua}"
        self.az = AppService(
            server=self.config["homeserver.address"],
            domain=self.config["homeserver.domain"],
            verify_ssl=self.config["homeserver.verify_ssl"],
            id=self.config["appservice.id"],
            as_token=self.config["appservice.as_token"],
            hs_token=self.config["appservice.hs_token"],
            bot_localpart=self.config["appservice.bot_username"],
            default_ua=HTTPAPI.default_ua,
            log="logviewer.events",
            loop=self.loop,
            aiohttp_params={"client_max_size": self.config["appservice.max_body_size"] * mb},
        )

    async def start(self) -> None:
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

        await super().start()
        self.az.ready = True

    async def stop(self) -> None:
        await self.az.stop()
        await super().stop()

    async def get_puppet(self, user_id: UserID, create: bool = False) -> None:
        pass

    async def get_double_puppet(self, user_id: UserID) -> None:
        pass
