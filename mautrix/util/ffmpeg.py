# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from typing import Iterable
from pathlib import Path
import asyncio
import mimetypes
import os
import shutil
import tempfile

try:
    from . import magic
except ImportError:
    magic = None


def _abswhich(program: str) -> str | None:
    path = shutil.which(program)
    return os.path.abspath(path) if path else None


class ConverterError(ChildProcessError):
    pass


class NotInstalledError(ConverterError):
    def __init__(self) -> None:
        super().__init__("failed to transcode media: ffmpeg is not installed")


ffmpeg_path = _abswhich("ffmpeg")
ffmpeg_default_params = ("-hide_banner", "-loglevel", "warning")


async def convert_path(
    input_file: os.PathLike[str] | str,
    output_extension: str | None,
    input_args: Iterable[str] | None = None,
    output_args: Iterable[str] | None = None,
    remove_input: bool = False,
    output_path_override: os.PathLike[str] | str | None = None,
) -> Path | bytes:
    """
    Convert a media file on the disk using ffmpeg.

    Args:
        input_file: The full path to the file.
        output_extension: The extension that the output file should be.
        input_args: Arguments to tell ffmpeg how to parse the input file.
        output_args: Arguments to tell ffmpeg how to convert the file to reach the wanted output.
        remove_input: Whether the input file should be removed after converting.
                      Not compatible with ``output_path_override``.
        output_path_override: A custom output path to use
                              (instead of using the input path with a different extension).

    Returns:
        The path to the converted file, or the stdout if ``output_path_override`` was set to ``-``.

    Raises:
        ConverterError: if ffmpeg returns a non-zero exit code.
    """
    if ffmpeg_path is None:
        raise NotInstalledError()

    if output_path_override:
        output_file = output_path_override
        if remove_input:
            raise ValueError("remove_input can't be specified with output_path_override")
    elif not output_extension:
        raise ValueError("output_extension or output_path_override is required")
    else:
        input_file = Path(input_file)
        output_file = input_file.parent / f"{input_file.stem}{output_extension}"
    proc = await asyncio.create_subprocess_exec(
        ffmpeg_path,
        *ffmpeg_default_params,
        *(input_args or ()),
        "-i",
        str(input_file),
        *(output_args or ()),
        str(output_file),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err_text = stderr.decode("utf-8") if stderr else f"unknown ({proc.returncode})"
        raise ConverterError(f"ffmpeg error: {err_text}")
    elif stderr:
        # TODO log warnings?
        pass
    if remove_input and isinstance(input_file, Path):
        input_file.unlink(missing_ok=True)
    return stdout if output_file == "-" else output_file


async def convert_bytes(
    data: bytes,
    output_extension: str,
    input_args: Iterable[str] | None = None,
    output_args: Iterable[str] | None = None,
    input_mime: str | None = None,
) -> bytes:
    """
    Convert media file data using ffmpeg.

    Args:
        data: The bytes of the file to convert.
        output_extension: The extension that the output file should be.
        input_args: Arguments to tell ffmpeg how to parse the input file.
        output_args: Arguments to tell ffmpeg how to convert the file to reach the wanted output.
        input_mime: The mime type of the input data. If not specified, will be guessed using magic.

    Returns:
        The converted file as bytes.

    Raises:
        ConverterError: if ffmpeg returns a non-zero exit code.
    """
    if ffmpeg_path is None:
        raise NotInstalledError()

    if input_mime is None:
        if magic is None:
            raise ValueError("input_mime was not specified and magic is not installed")
        input_mime = magic.mimetype(data)
    input_extension = mimetypes.guess_extension(input_mime)
    with tempfile.TemporaryDirectory(prefix="mautrix_ffmpeg_") as tmpdir:
        input_file = Path(tmpdir) / f"data{input_extension}"
        with open(input_file, "wb") as file:
            file.write(data)
        output_file = await convert_path(
            input_file=input_file,
            output_extension=output_extension,
            input_args=input_args,
            output_args=output_args,
        )
        with open(output_file, "rb") as file:
            return file.read()


__all__ = [
    "ffmpeg_path",
    "ffmpeg_default_params",
    "ConverterError",
    "NotInstalledError",
    "convert_bytes",
    "convert_path",
]
