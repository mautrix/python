# Copyright (c) 2023 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Coroutine
import asyncio
import logging

_tasks = set()
log = logging.getLogger("mau.background_task")


async def catch(coro: Coroutine, caller: str) -> None:
    try:
        await coro
    except Exception:
        log.exception(f"Uncaught error in background task (created in {caller})")


# Logger.findCaller finds the 3rd stack frame, so add an intermediate function
# to get the caller of create().
def _find_caller() -> tuple[str, int, str, None]:
    return log.findCaller()


def create(coro: Coroutine, *, name: str | None = None, catch_errors: bool = True) -> asyncio.Task:
    """
    Create a background asyncio task safely, ensuring a reference is kept until the task completes.
    It also catches and logs uncaught errors (unless disabled via the parameter).

    Args:
        coro: The coroutine to wrap in a task and execute.
        name: An optional name for the created task.
        catch_errors: Should the task be wrapped in a try-except block to log any uncaught errors?

    Returns:
        An asyncio Task object wrapping the given coroutine.
    """
    if catch_errors:
        try:
            file_name, line_number, function_name, _ = _find_caller()
            caller = f"{function_name} at {file_name}:{line_number}"
        except ValueError:
            caller = "unknown function"
        task = asyncio.create_task(catch(coro, caller), name=name)
    else:
        task = asyncio.create_task(coro, name=name)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return task
