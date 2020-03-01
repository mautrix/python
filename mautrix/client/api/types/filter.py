# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List
from attr import dataclass

from .util import SerializableAttrs, SerializableEnum
from .event import EventType
from .primitive import RoomID, UserID


class EventFormat(SerializableEnum):
    """
    Federation event format enum, as specified in the `create filter endpoint`_.

    .. _create filter endpoint:
        https://matrix.org/docs/spec/client_server/r0.5.0#post-matrix-client-r0-user-userid-filter
    """
    CLIENT = "client"
    FEDERATION = "federation"


@dataclass
class EventFilter(SerializableAttrs['EventFilter']):
    """
    Event filter object, as specified in the `create filter endpoint`_.

    Attributes:
        limit: The maximum number of events to return.
        not_senders: A list of sender IDs to exclude. If this list is absent then no senders are
            excluded. A matching sender will be excluded even if it is listed in the :attr:`senders`
            filter.
        not_types: A list of event types to exclude. If this list is absent then no event types are
            excluded. A matching type will be excluded even if it is listed in the :attr:`types`
            filter. A ``'*'`` can be used as a wildcard to match any sequence of characters.
        senders: A list of senders IDs to include. If this list is absent then all senders are
            included.
        types: A list of event types to include. If this list is absent then all event types are
            included. A ``'*'`` can be used as a wildcard to match any sequence of characters.

    .. _create filter endpoint:
        https://matrix.org/docs/spec/client_server/r0.5.0#post-matrix-client-r0-user-userid-filter
    """
    limit: int = None
    not_senders: List[UserID] = None
    not_types: List[EventType] = None
    senders: List[UserID] = None
    types: List[EventType] = None


@dataclass
class RoomEventFilter(EventFilter, SerializableAttrs['RoomEventFilter']):
    """
    Room event filter object, as specified in the `create filter endpoint`_.

    Attributes:
        lazy_load_members: If ``True``, enables lazy-loading of membership events. See `Lazy-loading
            room members`_ for more information.
        include_redundant_members: If ``True``, sends all membership events for all events,
            even if they have already been sent to the client. Does not apply unless
            :attr:`lazy_load_members` is true. See `Lazy-loading room members`_ for more
            information.
        not_rooms: A list of room IDs to exclude. If this list is absent then no rooms are excluded.
            A matching room will be excluded even if it is listed in the :attr:`rooms` filter.
        rooms: A list of room IDs to include. If this list is absent then all rooms are included.
        contains_url: If ``True``, includes only events with a url key in their content. If
            ``False``, excludes those events. If omitted, ``url`` key is not considered for
            filtering.

    .. _create filter endpoint:
        https://matrix.org/docs/spec/client_server/r0.5.0#post-matrix-client-r0-user-userid-filter
    .. _Lazy-loading room members:
        https://matrix.org/docs/spec/client_server/r0.5.0#lazy-loading-room-members
    """
    lazy_load_members: bool = False
    include_redundant_members: bool = False
    not_rooms: List[RoomID] = None
    rooms: List[RoomID] = None
    contains_url: bool = None


@dataclass
class StateFilter(RoomEventFilter, SerializableAttrs['RoomEventFilter']):
    """
    State event filter object, as specified in the `create filter endpoint`_. Currently this is the
    same as :class:`RoomEventFilter`.

    .. _create filter endpoint:
        https://matrix.org/docs/spec/client_server/r0.5.0#post-matrix-client-r0-user-userid-filter
    """
    pass


@dataclass
class RoomFilter(SerializableAttrs['RoomFilter']):
    """
    Room filter object, as specified in the `create filter endpoint`_.

    Attributes:
        not_rooms: A list of room IDs to exclude. If this list is absent then no rooms are excluded.
            A matching room will be excluded even if it is listed in the ``'rooms'`` filter. This
            filter is applied before the filters in :attr:`ephemeral`, :attr:`state`,
            :attr:`timeline` or :attr:`account_data`.
        rooms: A list of room IDs to include. If this list is absent then all rooms are included.
            This filter is applied before the filters in :attr:`ephemeral`, :attr:`state`,
            :attr:`timeline` or :attr:`account_data`.
        ephemeral: The events that aren't recorded in the room history, e.g. typing and receipts,
            to include for rooms.
        include_leave: Include rooms that the user has left in the sync.
        state: The state events to include for rooms.
        timeline: The message and state update events to include for rooms.
        account_data: The per user account data to include for rooms.

    .. _create filter endpoint:
        https://matrix.org/docs/spec/client_server/r0.5.0#post-matrix-client-r0-user-userid-filter
    """
    not_rooms: List[RoomID] = None
    rooms: List[RoomID] = None
    ephemeral: RoomEventFilter = None
    include_leave: bool = False
    state: StateFilter = None
    timeline: RoomEventFilter = None
    account_data: RoomEventFilter = None


@dataclass
class Filter(SerializableAttrs['Filter']):
    """
    Base filter object, as specified in the `create filter endpoint`_.

    Attributes:
        event_fields: List of event fields to include. If this list is absent then all fields are
            included. The entries may include ``.`` charaters to indicate sub-fields. So
            ``['content.body']`` will include the ``body`` field of the ``content`` object. A
            literal ``.`` character in a field name may be escaped using a ``\\``. A server may
            include more fields than were requested.
        event_format: The format to use for events. ``'client'`` will return the events in a format
            suitable for clients. ``'federation'`` will return the raw event as receieved over
            federation. The default is :attr:`~EventFormat.CLIENT`.
        presence: The presence updates to include.
        account_data: The user account data that isn't associated with rooms to include.
        room: Filters to be applied to room data.

    .. _create filter endpoint:
        https://matrix.org/docs/spec/client_server/r0.5.0#post-matrix-client-r0-user-userid-filter
    """
    event_fields: List[str] = None
    event_format: EventFormat = None
    presence: EventFilter = None
    account_data: EventFilter = None
    room: RoomFilter = None
