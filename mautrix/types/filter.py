# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List

from attr import dataclass

from .event import EventType
from .primitive import RoomID, UserID
from .util import SerializableAttrs, SerializableEnum


class EventFormat(SerializableEnum):
    """
    Federation event format enum, as specified in the `create filter endpoint`_.

    .. _create filter endpoint:
        https://matrix.org/docs/spec/client_server/r0.5.0#post-matrix-client-r0-user-userid-filter
    """

    CLIENT = "client"
    FEDERATION = "federation"


@dataclass
class EventFilter(SerializableAttrs):
    """
    Event filter object, as specified in the `create filter endpoint`_.

    .. _create filter endpoint:
        https://matrix.org/docs/spec/client_server/r0.5.0#post-matrix-client-r0-user-userid-filter
    """

    limit: int = None
    """The maximum number of events to return."""

    not_senders: List[UserID] = None
    """A list of sender IDs to exclude. If this list is absent then no senders are excluded
    A matching sender will be excluded even if it is listed in the :attr:`senders` filter."""

    not_types: List[EventType] = None
    """A list of event types to exclude. If this list is absent then no event types are excluded.
    A matching type will be excluded even if it is listed in the :attr:`types` filter.
    A ``'*'`` can be used as a wildcard to match any sequence of characters."""

    senders: List[UserID] = None
    """A list of senders IDs to include. If this list is absent then all senders are included."""

    types: List[EventType] = None
    """A list of event types to include. If this list is absent then all event types are included.
    A ``'*'`` can be used as a wildcard to match any sequence of characters."""


@dataclass
class RoomEventFilter(EventFilter, SerializableAttrs):
    """
    Room event filter object, as specified in the `create filter endpoint`_.

    .. _create filter endpoint:
        https://matrix.org/docs/spec/client_server/r0.5.0#post-matrix-client-r0-user-userid-filter
    """

    lazy_load_members: bool = False
    """
    If ``True``, enables lazy-loading of membership events. See `Lazy-loading room members`_ for more information.

    .. _Lazy-loading room members:
        https://matrix.org/docs/spec/client_server/r0.5.0#lazy-loading-room-members
    """

    include_redundant_members: bool = False
    """
    If ``True``, sends all membership events for all events, even if they have already been sent
    to the client. Does not apply unless :attr:`lazy_load_members` is true.
    See `Lazy-loading room members`_ for more information."""

    not_rooms: List[RoomID] = None
    """A list of room IDs to exclude. If this list is absent then no rooms are excluded.
    A matching room will be excluded even if it is listed in the :attr:`rooms` filter."""

    rooms: List[RoomID] = None
    """A list of room IDs to include. If this list is absent then all rooms are included."""

    contains_url: bool = None
    """If ``True``, includes only events with a url key in their content. If ``False``, excludes
    those events. If omitted, ``url`` key is not considered for filtering."""


@dataclass
class StateFilter(RoomEventFilter, SerializableAttrs):
    """
    State event filter object, as specified in the `create filter endpoint`_. Currently this is the
    same as :class:`RoomEventFilter`.

    .. _create filter endpoint:
        https://matrix.org/docs/spec/client_server/r0.5.0#post-matrix-client-r0-user-userid-filter
    """

    pass


@dataclass
class RoomFilter(SerializableAttrs):
    """
    Room filter object, as specified in the `create filter endpoint`_.

    .. _create filter endpoint:
        https://matrix.org/docs/spec/client_server/r0.5.0#post-matrix-client-r0-user-userid-filter
    """

    not_rooms: List[RoomID] = None
    """A list of room IDs to exclude. If this list is absent then no rooms are excluded.
    A matching room will be excluded even if it is listed in the ``'rooms'`` filter.
    This filter is applied before the filters in :attr:`ephemeral`, :attr:`state`,
    :attr:`timeline` or :attr:`account_data`."""

    rooms: List[RoomID] = None
    """A list of room IDs to include. If this list is absent then all rooms are included.
    This filter is applied before the filters in :attr:`ephemeral`, :attr:`state`,
    :attr:`timeline` or :attr:`account_data`."""

    ephemeral: RoomEventFilter = None
    """The events that aren't recorded in the room history, e.g. typing and receipts,
    to include for rooms."""

    include_leave: bool = False
    """Include rooms that the user has left in the sync."""

    state: StateFilter = None
    """The state events to include for rooms."""

    timeline: RoomEventFilter = None
    """The message and state update events to include for rooms."""

    account_data: RoomEventFilter = None
    """The per user account data to include for rooms."""


@dataclass
class Filter(SerializableAttrs):
    """
    Base filter object, as specified in the `create filter endpoint`_.

    .. _create filter endpoint:
        https://matrix.org/docs/spec/client_server/r0.5.0#post-matrix-client-r0-user-userid-filter
    """

    event_fields: List[str] = None
    """List of event fields to include. If this list is absent then all fields are included.
    The entries may include ``.`` charaters to indicate sub-fields. So ``['content.body']`` will
    include the ``body`` field of the ``content`` object. A literal ``.`` character in a field name
    may be escaped using a ``\\``. A server may include more fields than were requested."""

    event_format: EventFormat = None
    """The format to use for events. ``'client'`` will return the events in a format suitable for
    clients. ``'federation'`` will return the raw event as receieved over federation. The default
    is :attr:`~EventFormat.CLIENT`."""

    presence: EventFilter = None
    """The presence updates to include."""

    account_data: EventFilter = None
    """The user account data that isn't associated with rooms to include."""

    room: RoomFilter = None
    """Filters to be applied to room data."""
