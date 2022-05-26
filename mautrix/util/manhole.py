# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Based on https://github.com/nhoad/aiomanhole Copyright (c) 2014, Nathan Hoad
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, Union
from abc import ABC, abstractmethod
from io import BytesIO, StringIO
from socket import SOL_SOCKET
from types import CodeType
import ast
import asyncio
import codeop
import contextlib
import functools
import inspect
import logging
import os
import pwd
import struct
import sys
import traceback

try:
    from socket import SO_PEERCRED
except ImportError:
    SO_PEERCRED = None

log = logging.getLogger("mau.manhole")


TOP_LEVEL_AWAIT = sys.version_info >= (3, 8)
ASYNC_EVAL_WRAPPER: str = """
async def __eval_async_expr():
    try:
        pass
    finally:
        globals().update(locals())
"""


def compile_async(tree: ast.AST) -> CodeType:
    flags = 0
    if TOP_LEVEL_AWAIT:
        flags += ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
        node_to_compile = tree
    else:
        insert_returns(tree.body)
        wrapper_node: ast.AST = ast.parse(ASYNC_EVAL_WRAPPER, "<async eval wrapper>", "single")
        method_stmt = wrapper_node.body[0]
        try_stmt = method_stmt.body[0]
        try_stmt.body = tree.body
        node_to_compile = wrapper_node
    return compile(node_to_compile, "<manhole input>", "single", flags=flags)


# From https://gist.github.com/nitros12/2c3c265813121492655bc95aa54da6b9
def insert_returns(body: List[ast.AST]) -> None:
    if isinstance(body[-1], ast.Expr):
        body[-1] = ast.Return(body[-1].value)
        ast.fix_missing_locations(body[-1])
    elif isinstance(body[-1], ast.If):
        insert_returns(body[-1].body)
        insert_returns(body[-1].orelse)
    elif isinstance(body[-1], (ast.With, ast.AsyncWith)):
        insert_returns(body[-1].body)


class StatefulCommandCompiler(codeop.CommandCompiler):
    """A command compiler that buffers input until a full command is available."""

    buf: BytesIO

    def __init__(self) -> None:
        super().__init__()
        self.compiler = functools.partial(
            compile, optimize=1, flags=ast.PyCF_ONLY_AST | codeop.PyCF_DONT_IMPLY_DEDENT
        )
        self.buf = BytesIO()

    def is_partial_command(self) -> bool:
        return bool(self.buf.getvalue())

    def __call__(self, source: bytes, **kwargs: Any) -> Optional[CodeType]:
        buf = self.buf
        if self.is_partial_command():
            buf.write(b"\n")
        buf.write(source)

        code = self.buf.getvalue().decode("utf-8")
        codeobj = super().__call__(code, **kwargs)

        if codeobj:
            self.reset()
            return compile_async(codeobj)
        return None

    def reset(self) -> None:
        self.buf.seek(0)
        self.buf.truncate(0)


class Interpreter(ABC):
    @abstractmethod
    def __init__(self, namespace: Dict[str, Any], banner: Union[bytes, str]) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    async def __call__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        pass


class AsyncInterpreter(Interpreter):
    """An interactive asynchronous interpreter."""

    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    namespace: Dict[str, Any]
    banner: bytes
    compiler: StatefulCommandCompiler
    running: bool

    def __init__(self, namespace: Dict[str, Any], banner: Union[bytes, str]) -> None:
        super().__init__(namespace, banner)
        self.namespace = namespace
        self.banner = banner if isinstance(banner, bytes) else str(banner).encode("utf-8")
        self.compiler = StatefulCommandCompiler()

    async def send_exception(self) -> None:
        """When an exception has occurred, write the traceback to the user."""
        self.compiler.reset()

        exc = traceback.format_exc()
        self.writer.write(exc.encode("utf-8"))

        await self.writer.drain()

    async def execute(self, codeobj: CodeType) -> Tuple[Any, str]:
        with contextlib.redirect_stdout(StringIO()) as buf:
            if TOP_LEVEL_AWAIT:
                value = eval(codeobj, self.namespace)
                if codeobj.co_flags & inspect.CO_COROUTINE:
                    value = await value
            else:
                exec(codeobj, self.namespace)
                value = await eval("__eval_async_expr()", self.namespace)

        return value, buf.getvalue()

    async def handle_one_command(self) -> None:
        """Process a single command. May have many lines."""

        while True:
            await self.write_prompt()
            codeobj = await self.read_command()

            if codeobj is not None:
                await self.run_command(codeobj)
                return

    async def run_command(self, codeobj: CodeType) -> None:
        """Execute a compiled code object, and write the output back to the client."""
        try:
            value, stdout = await self.execute(codeobj)
        except Exception:
            await self.send_exception()
            return
        else:
            await self.send_output(value, stdout)

    async def write_prompt(self) -> None:
        writer = self.writer

        if self.compiler.is_partial_command():
            writer.write(b"... ")
        else:
            writer.write(b">>> ")

        await writer.drain()

    async def read_command(self) -> Optional[CodeType]:
        """Read a command from the user line by line.

        Returns a code object suitable for execution.
        """

        reader = self.reader

        line = await reader.readline()
        if line == b"":
            raise ConnectionResetError()

        try:
            # skip the newline to make CommandCompiler work as advertised
            codeobj = self.compiler(line.rstrip(b"\n"))
        except SyntaxError:
            await self.send_exception()
            return None

        return codeobj

    async def send_output(self, value: str, stdout: str) -> None:
        """Write the output or value of the expression back to user.

        >>> 5
        5
        >>> print('cash rules everything around me')
        cash rules everything around me
        """

        writer = self.writer

        if value is not None:
            writer.write(f"{value!r}\n".encode("utf-8"))

        if stdout:
            writer.write(stdout.encode("utf-8"))

        await writer.drain()

    def close(self) -> None:
        if self.running:
            self.writer.close()
            self.running = False

    async def __call__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Main entry point for an interpreter session with a single client."""
        self.reader = reader
        self.writer = writer
        self.running = True

        if self.banner:
            writer.write(self.banner)
            await writer.drain()

        while self.running:
            try:
                await self.handle_one_command()
            except ConnectionResetError:
                writer.close()
                self.running = False
                break
            except Exception:
                log.exception("Exception in manhole REPL")
                self.writer.write(traceback.format_exc())
                await self.writer.drain()


class InterpreterFactory:
    namespace: Dict[str, Any]
    banner: bytes
    interpreter_class: Type[Interpreter]
    clients: List[Interpreter]
    whitelist: Set[int]
    _conn_id: int

    def __init__(
        self,
        namespace: Dict[str, Any],
        banner: Union[bytes, str],
        interpreter_class: Type[Interpreter],
        whitelist: Set[int],
    ) -> None:
        self.namespace = namespace or {}
        self.banner = banner
        self.interpreter_class = interpreter_class
        self.clients = []
        self.whitelist = whitelist
        self._conn_id = 0

    @property
    def conn_id(self) -> int:
        self._conn_id += 1
        return self._conn_id

    async def __call__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        sock = writer.transport.get_extra_info("socket")
        # TODO support non-linux OSes
        # I think FreeBSD uses SCM_CREDS
        creds = sock.getsockopt(SOL_SOCKET, SO_PEERCRED, struct.calcsize("3i"))
        pid, uid, gid = struct.unpack("3i", creds)
        user_info = pwd.getpwuid(uid)
        username = f"{user_info.pw_name} ({uid})" if user_info and user_info.pw_name else uid
        if len(self.whitelist) > 0 and uid not in self.whitelist:
            writer.write(b"You are not whitelisted to use the manhole.")
            log.warning(f"Non-whitelisted user {username} tried to connect from PID {pid}")
            await writer.drain()
            writer.close()
            return

        namespace = {**self.namespace}
        interpreter = self.interpreter_class(namespace=namespace, banner=self.banner)
        namespace["exit"] = interpreter.close
        self.clients.append(interpreter)
        conn_id = self.conn_id

        log.info(f"Manhole connection OPENED: {conn_id} from PID {pid} by {username}")
        await asyncio.create_task(interpreter(reader, writer))
        log.info(f"Manhole connection CLOSED: {conn_id} from PID {pid} by {username}")
        self.clients.remove(interpreter)


async def start_manhole(
    path: str,
    banner: str = "",
    namespace: Optional[Dict[str, Any]] = None,
    loop: asyncio.AbstractEventLoop = None,
    whitelist: Set[int] = None,
) -> Tuple[asyncio.AbstractServer, Callable[[], None]]:
    """
    Starts a manhole server on a given UNIX address.

    Args:
        path: The path to create the UNIX socket at.
        banner: The banner to show when clients connect.
        namespace: The globals to provide to connected clients.
        loop: The asyncio event loop to use.
        whitelist: List of user IDs to allow connecting.
    """
    if not SO_PEERCRED:
        raise ValueError("SO_PEERCRED is not supported on this platform")
    factory = InterpreterFactory(
        namespace=namespace,
        banner=banner,
        interpreter_class=AsyncInterpreter,
        whitelist=whitelist,
    )
    server = await asyncio.start_unix_server(factory, path=path)
    os.chmod(path, 0o666)

    def stop():
        for client in factory.clients:
            client.close()
        server.close()

    return server, stop
