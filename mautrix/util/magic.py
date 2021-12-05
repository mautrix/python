# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Union
import functools

import magic

try:
    _from_buffer = functools.partial(magic.from_buffer, mime=True)
    _from_filename = functools.partial(magic.from_file, mime=True)
except AttributeError:
    _from_buffer = lambda data: magic.detect_from_content(data).mime_type
    _from_filename = lambda file: magic.detect_from_filename(file).mime_type


def mimetype(data: Union[bytes, str]) -> str:
    if isinstance(data, str):
        return _from_filename(data)
    return _from_buffer(data)
