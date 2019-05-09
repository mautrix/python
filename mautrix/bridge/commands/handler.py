# Copyright (c) 2019 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Awaitable, Callable, Dict, List, Any, Type, NamedTuple, Optional
import time
import asyncio
import logging
import traceback

import commonmark

from mautrix.types import RoomID, EventID
from mautrix.appservice import AppService
from ..user import BaseUser
from ..config import BaseBridgeConfig

command_handlers: Dict[str, 'CommandHandler'] = {}

HelpSection = NamedTuple('HelpSection', name=str, order=int, description=str)
HelpCacheKey = NamedTuple('HelpCacheKey', is_management=bool, is_portal=bool)

SECTION_GENERAL = HelpSection("General", 0, "")


class HtmlEscapingRenderer(commonmark.HtmlRenderer):
    def __init__(self, allow_html: bool = False):
        super().__init__()
        self.allow_html = allow_html

    def lit(self, s):
        if self.allow_html:
            return super().lit(s)
        return super().lit(s.replace("<", "&lt;").replace(">", "&gt;"))

    def image(self, node, entering):
        prev = self.allow_html
        self.allow_html = True
        super().image(node, entering)
        self.allow_html = prev


md_parser = commonmark.Parser()
md_renderer = HtmlEscapingRenderer()


def ensure_trailing_newline(s: str) -> str:
    """Returns the passed string, but with a guaranteed trailing newline."""
    return s + ("" if s[-1] == "\n" else "\n")


class CommandEvent:
    """Holds information about a command issued in a Matrix room.

    When a Matrix command was issued to the bot, CommandEvent will hold
    information regarding the event.

    Attributes:
        room_id: The id of the Matrix room in which the command was issued.
        event_id: The id of the matrix event which contained the command.
        sender: The user who issued the command.
        command: The issued command.
        args: Arguments given with the issued command.
        is_management: Determines whether the room in which the command wa
            issued is a management room.
        is_portal: Determines whether the room in which the command was issued
            is a portal.
    """

    az: AppService
    log: logging.Logger
    loop: asyncio.AbstractEventLoop
    config: BaseBridgeConfig
    processor: 'CommandProcessor'
    command_prefix: str
    room_id: RoomID
    event_id: EventID
    sender: 'BaseUser'
    command: str
    args: List[str]
    is_management: bool
    is_portal: bool

    def __init__(self, processor: 'CommandProcessor', room_id: RoomID, event_id: EventID,
                 sender: 'BaseUser', command: str, args: List[str], is_management: bool,
                 is_portal: bool) -> None:
        self.az = processor.az
        self.log = processor.log
        self.loop = processor.loop
        self.config = processor.config
        self.processor = processor
        self.command_prefix = processor.command_prefix
        self.room_id = room_id
        self.event_id = event_id
        self.sender = sender
        self.command = command
        self.args = args
        self.is_management = is_management
        self.is_portal = is_portal

    async def get_help_key(self) -> HelpCacheKey:
        """
        Get the help cache key for the given CommandEvent.

        Help messages are generated dynamically from the CommandHandlers that have been added so
        that they would only contain relevant commands. The help cache key is tuple-unpacked and
        passed to :meth:`CommandHandler.has_permission` when generating the help page. After the
        first generation, the page is cached using the help cache key.

        If you override this property or :meth:`CommandHandler.has_permission`, make sure to
        override the other too to handle the changes properly.

        When you override this property or otherwise extend CommandEvent, remember to pass the
        extended CommandEvent class when initializing your CommandProcessor.
        """
        return HelpCacheKey(is_management=self.is_management, is_portal=self.is_portal)

    @property
    def print_error_traceback(self) -> bool:
        """
        Whether or not the stack traces of unhandled exceptions during the handling of this command
        should be sent to the user. If false, the error message will simply tell the user to check
        the logs.

        Bridges may want to limit tracebacks to bridge admins.
        """
        return self.is_management

    def reply(self, message: str, allow_html: bool = False, render_markdown: bool = True
              ) -> Awaitable[EventID]:
        """Write a reply to the room in which the command was issued.

        Replaces occurences of "$cmdprefix" in the message with the command
        prefix and replaces occurences of "$cmdprefix+sp " with the command
        prefix if the command was not issued in a management room.
        If allow_html and render_markdown are both False, the message will not
        be rendered to html and sending of html is disabled.

        Args:
            message: The message to post in the room.
            allow_html: Escape html in the message or don't render html at all
                if markdown is disabled.
            render_markdown: Use markdown formatting to render the passed
                message to html.

        Returns:
            Handler for the message sending function.
        """
        message = self._replace_command_prefix(message)
        html = self._render_message(message, allow_html=allow_html,
                                    render_markdown=render_markdown)

        return self.az.intent.send_notice(self.room_id, message, html=html)

    def mark_read(self) -> Awaitable[None]:
        """Marks the command as read by the bot."""
        return self.az.intent.mark_read(self.room_id, self.event_id)

    def _replace_command_prefix(self, message: str) -> str:
        """Returns the string with the proper command prefix entered."""
        message = message.replace("$cmdprefix+sp ",
                                  "" if self.is_management else f"{self.command_prefix} ")
        return message.replace("$cmdprefix", self.command_prefix)

    @staticmethod
    def _render_message(message: str, allow_html: bool, render_markdown: bool) -> Optional[str]:
        """Renders the message as HTML.

        Args:
            allow_html: Flag to allow custom HTML in the message.
            render_markdown: If true, markdown styling is applied to the message.

        Returns:
            The message rendered as HTML.
            None is returned if no styled output is required.
        """
        html = ""
        if render_markdown:
            md_renderer.allow_html = allow_html
            html = md_renderer.render(md_parser.parse(message))
        elif allow_html:
            html = message
        return ensure_trailing_newline(html) if html else None


class CommandHandler:
    """A command which can be executed from a Matrix room.

    The command manages its permission and help texts.
    When called, it will check the permission of the command event and execute
    the command or, in case of error, report back to the user.

    Attributes:
        management_only: Whether the command can exclusively be issued in a
            management room.
        name: The name of this command.
        help_section: Section of the help in which this command will appear.
    """
    management_only: bool
    name: str

    _help_text: str
    _help_args: str
    help_section: HelpSection

    def __init__(self, handler: Callable[[CommandEvent], Awaitable[Any]], management_only: bool,
                 name: str, help_text: str, help_args: str, help_section: HelpSection, **kwargs
                 ) -> None:
        """
        Args:
            handler: The function handling the execution of this command.
            management_only: Whether the command can exclusively be issued
                in a management room.
            name: The name of this command.
            help_text: The text displayed in the help for this command.
            help_args: Help text for the arguments of this command.
            help_section: Section of the help in which this command will appear.
        """
        for key, value in kwargs.items():
            setattr(self, key, value)
        self._handler = handler
        self.management_only = management_only
        self.name = name
        self._help_text = help_text
        self._help_args = help_args
        self.help_section = help_section

    async def get_permission_error(self, evt: CommandEvent) -> Optional[str]:
        """Returns the reason why the command could not be issued.

        Args:
            evt: The event for which to get the error information.

        Returns:
            A string describing the error or None if there was no error.
        """
        if self.management_only and not evt.is_management:
            return (f"`{evt.command}` is a restricted command: "
                    "you may only run it in management rooms.")
        return None

    def has_permission(self, key: HelpCacheKey) -> bool:
        """Checks the permission for this command with the given status.

        Args:
            key: The help cache key. See meth:`CommandEvent.get_cache_key`.

        Returns:
            True if a user with the given state is allowed to issue the
            command.
        """
        return not self.management_only or key.is_management

    async def __call__(self, evt: CommandEvent) -> Any:
        """Executes the command if evt was issued with proper rights.

        Args:
            evt: The CommandEvent for which to check permissions.

        Returns:
            The result of the command or the error message function.
        """
        error = await self.get_permission_error(evt)
        if error is not None:
            return await evt.reply(error)
        return await self._handler(evt)

    @property
    def has_help(self) -> bool:
        """Returns true if this command has a help text."""
        return bool(self.help_section) and bool(self._help_text)

    @property
    def help(self) -> str:
        """Returns the help text to this command."""
        return f"**{self.name}** {self._help_args} - {self._help_text}"


def command_handler(_func: Optional[Callable[[CommandEvent], Awaitable[Dict]]] = None, *,
                    management_only: bool = False, name: Optional[str] = None,
                    help_text: str = "", help_args: str = "", help_section: HelpSection = None,
                    _handler_class: Type[CommandHandler] = CommandHandler, **kwargs
                    ) -> Callable[[Callable[[CommandEvent], Awaitable[Optional[Dict]]]],
                                  CommandHandler]:
    """Decorator to create CommandHandlers"""

    def decorator(func: Callable[[CommandEvent], Awaitable[Optional[Dict]]]) -> CommandHandler:
        actual_name = name or func.__name__.replace("_", "-")
        handler = _handler_class(func, management_only, actual_name, help_text, help_args,
                                 help_section, **kwargs)
        command_handlers[handler.name] = handler
        return handler

    return decorator if _func is None else decorator(_func)


class CommandProcessor:
    """Handles the raw commands issued by a user to the Matrix bot."""

    log = logging.getLogger("mau.commands")
    az: AppService
    config: BaseBridgeConfig
    loop: asyncio.AbstractEventLoop
    event_class: Type[CommandEvent]
    _ref_no: int

    def __init__(self, az: AppService, config: BaseBridgeConfig,
                 event_class: Type[CommandEvent] = CommandEvent,
                 loop: asyncio.AbstractEventLoop = None) -> None:
        self.az = az
        self.config = config
        self.loop = loop or asyncio.get_event_loop()
        self.command_prefix = self.config["bridge.command_prefix"]
        self.event_class = event_class
        self._ref_no = int(time.time())

    @property
    def ref_no(self) -> int:
        """
        Reference number for a command handling exception to help sysadmins find the error when
        receiving user reports.
        """
        self._ref_no += 1
        return self._ref_no

    async def handle(self, room: RoomID, event_id: EventID, sender: 'BaseUser',
                     command: str, args: List[str], is_management: bool, is_portal: bool
                     ) -> None:
        """Handles the raw commands issued by a user to the Matrix bot.

        If the command is not known, it might be a followup command and is
        delegated to a command handler registered for that purpose in the
        senders command_status as "next".

        Args:
            room: ID of the Matrix room in which the command was issued.
            event_id: ID of the event by which the command was issued.
            sender: The sender who issued the command.
            command: The issued command, case insensitive.
            args: Arguments given with the command.
            is_management: Whether the room is a management room.
            is_portal: Whether the room is a portal.

        Returns:
            The result of the error message function or None if no error
            occured. Unknown and delegated commands do not count as errors.
        """
        if not command_handlers or "unknown-command" not in command_handlers:
            raise ValueError("command_handlers are not properly initialized.")

        evt = self.event_class(self, room, event_id, sender, command, args,
                               is_management, is_portal)
        orig_command = command
        command = command.lower()
        try:
            handler = command_handlers[command]
        except KeyError:
            if sender.command_status and "next" in sender.command_status:
                args.insert(0, orig_command)
                evt.command = ""
                handler = sender.command_status["next"]
            else:
                handler = command_handlers["unknown-command"]
        try:
            await handler(evt)
        except Exception:
            ref_no = self.ref_no
            self.log.exception("Unhandled error while handling command "
                               f"{evt.command} {' '.join(args)} from {sender.mxid} (ref: {ref_no})")
            if evt.print_error_traceback:
                await evt.reply("Unhandled error while handling command:\n\n"
                                "```traceback\n"
                                f"{traceback.format_exc()}"
                                "```")
            else:
                await evt.reply("Unhandled error while handling command. "
                                f"Check logs for more details (ref: {ref_no}).")
        return None
