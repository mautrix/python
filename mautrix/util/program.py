# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Iterable, Awaitable, Optional, Type, Union, Tuple, AsyncIterable, Any
from itertools import chain
from time import time
import argparse
import inspect
import logging
import logging.config
import asyncio
import signal
import copy
import sys

from .config import BaseFileConfig, BaseValidatableConfig, ConfigValueError, BaseMissingError

try:
    import uvloop
except ImportError:
    uvloop = None

try:
    import prometheus_client as prometheus
except ImportError:
    prometheus = None


NewTask = Union[Awaitable[Any], Iterable[Awaitable[Any]], AsyncIterable[Awaitable[Any]]]
TaskList = Iterable[Awaitable[Any]]


class Program:
    """
    A generic main class for programs that handles argument parsing, config loading, logger setup
    and general startup/shutdown lifecycle.
    """

    loop: asyncio.AbstractEventLoop
    log: logging.Logger
    parser: argparse.ArgumentParser
    args: argparse.Namespace

    config_class: Type[BaseFileConfig]
    config: BaseFileConfig

    startup_actions: TaskList
    shutdown_actions: TaskList

    module: str
    name: str
    version: str
    command: str
    description: str

    def __init__(self, module: Optional[str] = None, name: Optional[str] = None,
                 description: Optional[str] = None, command: Optional[str] = None,
                 version: Optional[str] = None, config_class: Optional[Type[BaseFileConfig]] = None
                 ) -> None:
        if module:
            self.module = module
        if name:
            self.name = name
        if description:
            self.description = description
        if command:
            self.command = command
        if version:
            self.version = version
        if config_class:
            self.config_class = config_class
        self.startup_actions = []
        self.shutdown_actions = []
        self._automatic_prometheus = True

    def run(self) -> None:
        """
        Prepare and run the program. This is the main entrypoint and the only function that should
        be called manually.
        """
        self._prepare()
        self._run()

    def _prepare(self) -> None:
        start_ts = time()

        self.preinit()

        self.log.info(f"Initializing {self.name} {self.version}")
        try:
            self.prepare()
        except Exception:
            self.log.critical("Unexpected error in initialization", exc_info=True)
            sys.exit(1)
        end_ts = time()
        self.log.info(f"Initialization complete in {round(end_ts - start_ts, 2)} seconds")

    def preinit(self) -> None:
        """
        First part of startup: parse command-line arguments, load and update config, prepare logger.
        Exceptions thrown here will crash the program immediately. Asyncio must not be used at this
        stage, as the loop is only initialized later.
        """
        self.prepare_arg_parser()
        self.args = self.parser.parse_args()

        self.prepare_config()
        self.prepare_log()
        self.check_config()

    def prepare_arg_parser(self) -> None:
        """Pre-init lifecycle method. Extend this if you want custom command-line arguments."""
        self.parser = argparse.ArgumentParser(description=self.description, prog=self.command)
        self.parser.add_argument("-c", "--config", type=str, default="config.yaml",
                                 metavar="<path>", help="the path to your config file")
        self.parser.add_argument("-b", "--base-config", type=str,
                                 default=f"pkg://{self.module}/example-config.yaml",
                                 metavar="<path>", help="the path to the example config "
                                                        "(for automatic config updates)")
        self.parser.add_argument("-n", "--no-update", action="store_true",
                                 help="Don't save updated config to disk")

    def prepare_config(self) -> None:
        """Pre-init lifecycle method. Extend this if you want to customize config loading."""
        self.config = self.config_class(self.args.config, self.args.base_config)
        self.load_and_update_config()

    def load_and_update_config(self) -> None:
        self.config.load()
        try:
            self.config.update(save=not self.args.no_update)
        except BaseMissingError:
            self.log.exception("Failed to read base config. Try specifying the correct path with "
                               "the --base-config flag.")
            sys.exit(12)

    def check_config(self) -> None:
        """Pre-init lifecycle method. Extend this if you want to customize config validation."""
        if not isinstance(self.config, BaseValidatableConfig):
            return
        try:
            self.config.check_default_values()
        except ConfigValueError as e:
            self.log.fatal(f"Configuration error: {e}")
            sys.exit(11)

    def prepare_log(self) -> None:
        """Pre-init lifecycle method. Extend this if you want to customize logging setup."""
        logging.config.dictConfig(copy.deepcopy(self.config["logging"]))
        self.log = logging.getLogger("mau.init")

    def prepare(self) -> None:
        """
        Lifecycle method where the primary program initialization happens.
        Use this to fill startup_actions with async startup tasks.
        """
        self.prepare_loop()

    def prepare_loop(self) -> None:
        """Init lifecycle method where the asyncio event loop is created."""
        if uvloop is not None:
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            self.log.debug("Using uvloop for asyncio")

        self.loop = asyncio.get_event_loop()

    def start_prometheus(self) -> None:
        try:
            enabled = self.config["metrics.enabled"]
            listen_port = self.config["metrics.listen_port"]
        except KeyError:
            return
        if not enabled:
            return
        elif not prometheus:
            self.log.warning("Metrics are enabled in config, "
                             "but prometheus_client is not installed")
            return
        prometheus.start_http_server(listen_port)

    def _run(self) -> None:
        signal.signal(signal.SIGINT, signal.default_int_handler)
        signal.signal(signal.SIGTERM, signal.default_int_handler)

        try:
            self.log.debug("Running startup actions...")
            start_ts = time()
            self.loop.run_until_complete(self.start())
            end_ts = time()
            self.log.info(f"Startup actions complete in {round(end_ts - start_ts, 2)} seconds, "
                           "now running forever")
            self._stop_task = self.loop.create_future()
            self.loop.run_until_complete(self._stop_task)
            self.log.debug("manual_stop() called, stopping...")
        except KeyboardInterrupt:
            self.log.debug("Interrupt received, stopping...")
        except Exception:
            self.log.critical("Unexpected error in main event loop", exc_info=True)
            sys.exit(2)
        self.prepare_stop()
        self.loop.run_until_complete(self.stop())
        self.prepare_shutdown()
        self.log.info("Everything stopped, shutting down")
        sys.exit(0)

    async def start(self) -> None:
        """
        First lifecycle method called inside the asyncio event loop. Extend this if you want more
        control over startup than just filling startup_actions in the prepare step.
        """
        await asyncio.gather(*(self.startup_actions or []))
        if self._automatic_prometheus:
            self.start_prometheus()

    def prepare_stop(self) -> None:
        """
        Lifecycle method that is called before awaiting :meth:`stop`.
        Useful for filling shutdown_actions.
        """

    async def stop(self) -> None:
        """
        Lifecycle method used to stop things that need awaiting to stop. Extend this if you want
        more control over shutdown than just filling shutdown_actions in the prepare_stop method.
        """
        await asyncio.gather(*(self.shutdown_actions or []))

    def prepare_shutdown(self) -> None:
        """Lifecycle method that is called right before ``sys.exit(0)``."""

    def manual_stop(self) -> None:
        """Tell the event loop to cleanly stop and run the stop lifecycle steps."""
        self._stop_task.set_result(None)

    def add_startup_actions(self, *actions: NewTask) -> None:
        self.startup_actions = self._add_actions(self.startup_actions, actions)

    def add_shutdown_actions(self, *actions: NewTask) -> None:
        self.shutdown_actions = self._add_actions(self.shutdown_actions, actions)

    async def _unpack_async_iterator(self, iterable: AsyncIterable[Awaitable[Any]]) -> None:
        tasks = []
        async for task in iterable:
            if inspect.isawaitable(task):
                tasks.append(asyncio.ensure_future(task, loop=self.loop))
        await asyncio.gather(*tasks)

    def _add_actions(self, to: TaskList, add: Tuple[NewTask, ...]) -> TaskList:
        for item in add:
            if inspect.isasyncgen(item):
                to.append(self._unpack_async_iterator(item))
            elif inspect.isawaitable(item):
                if isinstance(to, list):
                    to.append(item)
                else:
                    to = chain(to, [item])
            elif isinstance(item, list):
                if isinstance(to, list):
                    to += item
                else:
                    to = chain(to, item)
            else:
                to = chain(to, item)
        return to
