# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Any, Awaitable, Callable, NamedTuple, Type
import asyncio
import logging
import time
import traceback

from mautrix.appservice import AppService, IntentAPI
from mautrix.types import EventID, MessageEventContent, RoomID
from mautrix.util import markdown
from mautrix.util.logging import TraceLogger

from ... import bridge as br

command_handlers: dict[str, CommandHandler] = {}
command_aliases: dict[str, CommandHandler] = {}

HelpSection = NamedTuple("HelpSection", name=str, order=int, description=str)
HelpCacheKey = NamedTuple(
    "HelpCacheKey", is_management=bool, is_portal=bool, is_admin=bool, is_logged_in=bool
)

SECTION_GENERAL = HelpSection("General", 0, "")
SECTION_AUTH = HelpSection("Authentication", 10, "")
SECTION_ADMIN = HelpSection("Administration", 50, "")
SECTION_RELAY = HelpSection("Relay mode management", 15, "")


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
        content: The raw content in the command event.
        portal: The portal the command was sent to.
        is_management: Determines whether the room in which the command was
            issued in is a management room.
        has_bridge_bot: Whether or not the bridge bot is in the room.
    """

    bridge: bridge.Bridge
    az: AppService
    log: TraceLogger
    loop: asyncio.AbstractEventLoop
    config: br.BaseBridgeConfig
    processor: CommandProcessor
    command_prefix: str
    room_id: RoomID
    event_id: EventID
    sender: br.BaseUser
    command: str
    args: list[str]
    content: MessageEventContent
    portal: br.BasePortal | None
    is_management: bool
    has_bridge_bot: bool

    def __init__(
        self,
        processor: CommandProcessor,
        room_id: RoomID,
        event_id: EventID,
        sender: br.BaseUser,
        command: str,
        args: list[str],
        content: MessageEventContent,
        portal: br.BasePortal | None,
        is_management: bool,
        has_bridge_bot: bool,
    ) -> None:
        self.bridge = processor.bridge
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
        self.content = content
        self.portal = portal
        self.is_management = is_management
        self.has_bridge_bot = has_bridge_bot

    @property
    def is_portal(self) -> bool:
        return self.portal is not None

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
        return HelpCacheKey(
            is_management=self.is_management,
            is_portal=self.portal is not None,
            is_admin=self.sender.is_admin,
            is_logged_in=await self.sender.is_logged_in(),
        )

    @property
    def print_error_traceback(self) -> bool:
        """
        Whether or not the stack traces of unhandled exceptions during the handling of this command
        should be sent to the user. If false, the error message will simply tell the user to check
        the logs.

        Bridges may want to limit tracebacks to bridge admins.
        """
        return self.sender.is_admin

    @property
    def main_intent(self) -> IntentAPI:
        return self.portal.main_intent if self.portal else self.az.intent

    def reply(
        self, message: str, allow_html: bool = False, render_markdown: bool = True
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
        html = self._render_message(
            message, allow_html=allow_html, render_markdown=render_markdown
        )
        if self.has_bridge_bot:
            return self.az.intent.send_notice(self.room_id, message, html=html)
        else:
            return self.main_intent.send_notice(self.room_id, message, html=html)

    async def mark_read(self) -> None:
        """Marks the command as read by the bot."""
        if self.has_bridge_bot:
            await self.az.intent.mark_read(self.room_id, self.event_id)

    def _replace_command_prefix(self, message: str) -> str:
        """Returns the string with the proper command prefix entered."""
        message = message.replace(
            "$cmdprefix+sp ", "" if self.is_management else f"{self.command_prefix} "
        )
        return message.replace("$cmdprefix", self.command_prefix)

    @staticmethod
    def _render_message(message: str, allow_html: bool, render_markdown: bool) -> str | None:
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
            html = markdown.render(message, allow_html=allow_html)
        elif allow_html:
            html = message
        return ensure_trailing_newline(html) if html else None


CommandHandlerFunc = Callable[[CommandEvent], Awaitable[Any]]
IsEnabledForFunc = Callable[[CommandEvent], bool]


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

    name: str

    management_only: bool
    needs_admin: bool
    needs_auth: bool
    is_enabled_for: IsEnabledForFunc

    _help_text: str
    _help_args: str
    help_section: HelpSection

    def __init__(
        self,
        handler: CommandHandlerFunc,
        management_only: bool,
        name: str,
        help_text: str,
        help_args: str,
        help_section: HelpSection,
        needs_auth: bool,
        needs_admin: bool,
        is_enabled_for: IsEnabledForFunc = lambda _: True,
        **kwargs,
    ) -> None:
        """
        Args:
            handler: The function handling the execution of this command.
            management_only: Whether the command can exclusively be issued
                in a management room.
            needs_auth: Whether the command needs the bridge to be authed already
            needs_admin: Whether the command needs the issuer to be bridge admin
            name: The name of this command.
            help_text: The text displayed in the help for this command.
            help_args: Help text for the arguments of this command.
            help_section: Section of the help in which this command will appear.
        """
        for key, value in kwargs.items():
            setattr(self, key, value)
        self._handler = handler
        self.management_only = management_only
        self.needs_admin = needs_admin
        self.needs_auth = needs_auth
        self.name = name
        self._help_text = help_text
        self._help_args = help_args
        self.help_section = help_section
        self.is_enabled_for = is_enabled_for

    async def get_permission_error(self, evt: CommandEvent) -> str | None:
        """Returns the reason why the command could not be issued.

        Args:
            evt: The event for which to get the error information.

        Returns:
            A string describing the error or None if there was no error.
        """
        if self.management_only and not evt.is_management:
            return (
                f"`{evt.command}` is a restricted command: "
                "you may only run it in management rooms."
            )
        elif self.needs_admin and not evt.sender.is_admin:
            return "This command requires administrator privileges."
        elif self.needs_auth and not await evt.sender.is_logged_in():
            return "This command requires you to be logged in."
        return None

    def has_permission(self, key: HelpCacheKey) -> bool:
        """Checks the permission for this command with the given status.

        Args:
            key: The help cache key. See meth:`CommandEvent.get_cache_key`.

        Returns:
            True if a user with the given state is allowed to issue the
            command.
        """
        return (
            (not self.management_only or key.is_management)
            and (not self.needs_admin or key.is_admin)
            and (not self.needs_auth or key.is_logged_in)
        )

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


def command_handler(
    _func: CommandHandlerFunc | None = None,
    *,
    management_only: bool = False,
    name: str | None = None,
    help_text: str = "",
    help_args: str = "",
    help_section: HelpSection = None,
    aliases: list[str] | None = None,
    _handler_class: Type[CommandHandler] = CommandHandler,
    needs_auth: bool = True,
    needs_admin: bool = False,
    is_enabled_for: IsEnabledForFunc = lambda _: True,
    **kwargs,
) -> Callable[[CommandHandlerFunc], CommandHandler]:
    """Decorator to create CommandHandlers"""

    def decorator(func: CommandHandlerFunc) -> CommandHandler:
        actual_name = name or func.__name__.replace("_", "-")
        handler = _handler_class(
            func,
            management_only=management_only,
            name=actual_name,
            help_text=help_text,
            help_args=help_args,
            help_section=help_section,
            needs_auth=needs_auth,
            needs_admin=needs_admin,
            is_enabled_for=is_enabled_for,
            **kwargs,
        )
        command_handlers[handler.name] = handler
        if aliases:
            for alias in aliases:
                command_aliases[alias] = handler
        return handler

    return decorator if _func is None else decorator(_func)


class CommandProcessor:
    """Handles the raw commands issued by a user to the Matrix bot."""

    log: TraceLogger = logging.getLogger("mau.commands")
    az: AppService
    config: br.BaseBridgeConfig
    loop: asyncio.AbstractEventLoop
    event_class: Type[CommandEvent]
    bridge: bridge.Bridge
    _ref_no: int

    def __init__(
        self, bridge: bridge.Bridge, event_class: Type[CommandEvent] = CommandEvent
    ) -> None:
        self.az = bridge.az
        self.config = bridge.config
        self.loop = bridge.loop or asyncio.get_event_loop()
        self.command_prefix = self.config["bridge.command_prefix"]
        self.bridge = bridge
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

    @staticmethod
    def _run_handler(
        handler: Callable[[CommandEvent], Awaitable[Any]], evt: CommandEvent
    ) -> Awaitable[Any]:
        return handler(evt)

    async def handle(
        self,
        room_id: RoomID,
        event_id: EventID,
        sender: br.BaseUser,
        command: str,
        args: list[str],
        content: MessageEventContent,
        portal: br.BasePortal | None,
        is_management: bool,
        has_bridge_bot: bool,
    ) -> None:
        """Handles the raw commands issued by a user to the Matrix bot.

        If the command is not known, it might be a followup command and is
        delegated to a command handler registered for that purpose in the
        senders command_status as "next".

        Args:
            room_id: ID of the Matrix room in which the command was issued.
            event_id: ID of the event by which the command was issued.
            sender: The sender who issued the command.
            command: The issued command, case insensitive.
            args: Arguments given with the command.
            content: The raw content in the command event.
            portal: The portal the command was sent to.
            is_management: Whether the room is a management room.
            has_bridge_bot: Whether or not the bridge bot is in the room.

        Returns:
            The result of the error message function or None if no error
            occured. Unknown and delegated commands do not count as errors.
        """
        if not command_handlers or "unknown-command" not in command_handlers:
            raise ValueError("command_handlers are not properly initialized.")

        evt = self.event_class(
            processor=self,
            room_id=room_id,
            event_id=event_id,
            sender=sender,
            command=command,
            args=args,
            content=content,
            portal=portal,
            is_management=is_management,
            has_bridge_bot=has_bridge_bot,
        )
        orig_command = command
        command = command.lower()

        handler = command_handlers.get(command, command_aliases.get(command))
        if handler is None or not handler.is_enabled_for(evt):
            if sender.command_status and "next" in sender.command_status:
                args.insert(0, orig_command)
                evt.command = ""
                handler = sender.command_status["next"]
            else:
                handler = command_handlers["unknown-command"]

        try:
            await self._run_handler(handler, evt)
        except Exception:
            ref_no = self.ref_no
            self.log.exception(
                "Unhandled error while handling command "
                f"{evt.command} {' '.join(args)} from {sender.mxid} (ref: {ref_no})"
            )
            if evt.print_error_traceback:
                await evt.reply(
                    "Unhandled error while handling command:\n\n"
                    "```traceback\n"
                    f"{traceback.format_exc()}"
                    "```"
                )
            else:
                await evt.reply(
                    "Unhandled error while handling command. "
                    f"Check logs for more details (ref: {ref_no})."
                )
            raise
        return None
