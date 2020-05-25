# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Based on https://github.com/nhoad/aiomanhole Copyright (c) 2014, Nathan Hoad
from typing import Any, Tuple, Optional, Dict, Union, List, Set, Callable, Type
from socket import SOL_SOCKET
from abc import ABC, abstractmethod
from io import BytesIO, StringIO
from types import CodeType
import contextlib
import functools
import traceback
import logging
import asyncio
import struct
import codeop
import pwd
import ast
import sys
import os

try:
    from socket import SO_PEERCRED
except ImportError:
    SO_PEERCRED = None

log = logging.getLogger("mau.manhole")


class AwaitTransformer(ast.NodeTransformer):
    def visit_Call(self, node: ast.Call) -> Union[ast.Call, ast.Await]:
        if ((not isinstance(node.func, ast.Name) or node.func.id != AWAIT_FUNC_NAME
             or len(node.args) != 1 or len(node.keywords) != 0)):
            return node
        return ast.copy_location(ast.Await(value=node.args[0]), node)


class AwaitFallback:
    def __str__(self) -> str:
        return "magical await() AST transformer"

    def __repr__(self) -> str:
        return "magical await() AST transformer"

    def __call__(self, *args, **kwargs) -> Any:
        if len(args) != 1:
            raise TypeError(f"{AWAIT_FUNC_NAME}() takes 1 positional argument "
                            f"but {len(args)} were given")
        elif len(kwargs) > 0:
            raise TypeError(f"{AWAIT_FUNC_NAME}() got an unexpected keyword argument "
                            f"'{list(kwargs.keys())[0]}'")
        raise RuntimeError("AST transforming appears to have failed")


# Python 3.6 doesn't even support parsing top-level awaits, so we use an AST transformer to
# convert `await(coro)` into `await coro`.
# Python 3.7 and up allow parsing top-level awaits and only throw errors if you try to execute them.
AWAIT_TRANSFORM = sys.version_info < (3, 7)
AWAIT_FUNC_NAME = "await"
AWAIT_FALLBACK = AwaitFallback()

ASYNC_EVAL_WRAPPER: str = """
async def __eval_async_expr():
    try:
        pass
    finally:
        globals().update(locals())
"""


def asyncify(tree: ast.AST, wrapper: str = ASYNC_EVAL_WRAPPER, module: str = "<ast>") -> CodeType:
    # TODO in python 3.8+, switch to ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
    if AWAIT_TRANSFORM:
        AwaitTransformer().visit(tree)
    insert_returns(tree.body)
    wrapper_node: ast.AST = ast.parse(wrapper, "<async eval wrapper>", "single")
    method_stmt = wrapper_node.body[0]
    try_stmt = method_stmt.body[0]
    try_stmt.body = tree.body
    return compile(wrapper_node, module, "single")


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
    wrapper: str = ASYNC_EVAL_WRAPPER

    def __init__(self) -> None:
        super().__init__()
        self.compiler = functools.partial(compile, optimize=1,
                                          flags=ast.PyCF_ONLY_AST | codeop.PyCF_DONT_IMPLY_DEDENT)
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
            return asyncify(codeobj, wrapper=self.wrapper)
        return None

    def reset(self) -> None:
        self.buf.seek(0)
        self.buf.truncate(0)


class Interpreter(ABC):
    @abstractmethod
    def __init__(self, namespace: Dict[str, Any], banner: Union[bytes, str],
                 loop: asyncio.AbstractEventLoop) -> None:
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
    loop: asyncio.AbstractEventLoop
    running: bool

    def __init__(self, namespace: Dict[str, Any], banner: Union[bytes, str],
                 loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(namespace, banner, loop)
        self.namespace = namespace
        self.banner = banner if isinstance(banner, bytes) else str(banner).encode("utf-8")
        self.compiler = StatefulCommandCompiler()
        self.loop = loop

    async def send_exception(self) -> None:
        """When an exception has occurred, write the traceback to the user."""
        self.compiler.reset()

        exc = traceback.format_exc()
        self.writer.write(exc.encode("utf-8"))

        await self.writer.drain()

    async def execute(self, codeobj: CodeType) -> Tuple[Any, str]:
        exec(codeobj, self.namespace)
        with contextlib.redirect_stdout(StringIO()) as buf:
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
    loop: asyncio.AbstractEventLoop
    interpreter_class: Type[Interpreter]
    clients: List[Interpreter]
    whitelist: Set[int]
    _conn_id: int

    def __init__(self, namespace: Dict[str, Any], banner: Union[bytes, str],
                 interpreter_class: Type[Interpreter], loop: asyncio.AbstractEventLoop,
                 whitelist: Set[int]) -> None:
        self.namespace = namespace or {}
        self.banner = banner
        self.loop = loop
        self.interpreter_class = interpreter_class
        self.clients = []
        self.whitelist = whitelist
        self._conn_id = 0

    @property
    def conn_id(self) -> int:
        self._conn_id += 1
        return self._conn_id

    async def __call__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
                       ) -> None:
        sock = writer.transport.get_extra_info("socket")
        # TODO support non-linux OSes
        # I think FreeBSD uses SCM_CREDS
        creds = sock.getsockopt(SOL_SOCKET, SO_PEERCRED, struct.calcsize('3i'))
        pid, uid, gid = struct.unpack('3i', creds)
        user_info = pwd.getpwuid(uid)
        username = f"{user_info.pw_name} ({uid})" if user_info and user_info.pw_name else uid
        if len(self.whitelist) > 0 and uid not in self.whitelist:
            writer.write(b"You are not whitelisted to use the manhole.")
            log.warning(f"Non-whitelisted user {username} tried to connect from PID {pid}")
            await writer.drain()
            writer.close()
            return

        namespace = {**self.namespace}
        if AWAIT_TRANSFORM:
            namespace[AWAIT_FUNC_NAME] = AWAIT_FALLBACK
        interpreter = self.interpreter_class(namespace=namespace, banner=self.banner,
                                             loop=self.loop)
        namespace["exit"] = interpreter.close
        self.clients.append(interpreter)
        conn_id = self.conn_id

        log.info(f"Manhole connection OPENED: {conn_id} from PID {pid} by {username}")
        await asyncio.ensure_future(interpreter(reader, writer))
        log.info(f"Manhole connection CLOSED: {conn_id} from PID {pid} by {username}")
        self.clients.remove(interpreter)


async def start_manhole(path: str, banner: str = "", namespace: Optional[Dict[str, Any]] = None,
                        loop: asyncio.AbstractEventLoop = None, whitelist: Set[int] = None,
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
    loop = loop or asyncio.get_event_loop()
    factory = InterpreterFactory(namespace=namespace, banner=banner,
                                 interpreter_class=AsyncInterpreter, loop=loop,
                                 whitelist=whitelist)
    server = await asyncio.start_unix_server(factory, path=path, loop=loop)
    os.chmod(path, 0o666)

    def stop():
        for client in factory.clients:
            client.close()
        server.close()

    return server, stop
