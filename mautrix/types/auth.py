# Copyright (c) 2020 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import Union, Optional, List, NewType
from attr import dataclass
import attr

from .primitive import UserID, DeviceID, JSON
from .util import SerializableAttrs, ExtensibleEnum, deserializer, Obj


class LoginType(ExtensibleEnum):
    """
    A login type, as specified in the `POST /login endpoint`_

    .. _POST /login endpoint:
        https://matrix.org/docs/spec/client_server/r0.6.1#post-matrix-client-r0-login
    """
    PASSWORD: 'LoginType' = "m.login.password"
    TOKEN: 'LoginType' = "m.login.token"
    SSO: 'LoginType' = "m.login.sso"

    JWT: 'LoginType' = "org.matrix.login.jwt"
    APPSERVICE: 'LoginType' = "uk.half-shot.msc2778.login.application_service"


@dataclass
class LoginFlow(SerializableAttrs['LoginFlow']):
    """
    A login flow, as specified in the `GET /login endpoint`_

    .. _GET /login endpoint:
        https://matrix.org/docs/spec/client_server/r0.6.1#get-matrix-client-r0-login
    """
    type: LoginType


@dataclass
class LoginFlowList(SerializableAttrs['LoginFlowList']):
    flows: List[LoginFlow]

    def supports_type(self, type: LoginType) -> bool:
        for flow in self.flows:
            if flow.type == type:
                return True
        return False


class UserIdentifierType(ExtensibleEnum):
    """
    A user identifier type, as specified in the `Identifier types`_ section of the login spec.

    .. _Identifier types:
        https://matrix.org/docs/spec/client_server/latest#identifier-types
    """
    MATRIX_USER: 'UserIdentifierType' = "m.id.user"
    THIRD_PARTY: 'UserIdentifierType' = "m.id.thirdparty"
    PHONE: 'UserIdentifierType' = "m.id.phone"


@dataclass
class MatrixUserIdentifier(SerializableAttrs['MatrixUserIdentifier']):
    """
    A client can identify a user using their Matrix ID. This can either be the fully qualified
    Matrix user ID, or just the localpart of the user ID.

    Attributes:
        user: The Matrix user ID or localpart
    """

    user: str
    type: UserIdentifierType = UserIdentifierType.MATRIX_USER


@dataclass
class ThirdPartyIdentifier(SerializableAttrs['ThirdPartyIdentifier']):
    """
    A client can identify a user using a 3PID associated with the user's account on the homeserver,
    where the 3PID was previously associated using the `/account/3pid`_ API. See the `3PID Types`_
    Appendix for a list of Third-party ID media.

    .. _/account/3pid:
        https://matrix.org/docs/spec/client_server/latest#post-matrix-client-r0-account-3pid
    .. _3PID Types:
        https://matrix.org/docs/spec/appendices.html#pid-types
    """
    medium: str
    address: str
    type: UserIdentifierType = UserIdentifierType.THIRD_PARTY


@dataclass
class PhoneIdentifier(SerializableAttrs['PhoneIdentifier']):
    """
    A client can identify a user using a phone number associated with the user's account, where the
    phone number was previously associated using the `/account/3pid`_ API. The phone number can be
    passed in as entered by the user; the homeserver will be responsible for canonicalising it.
    If the client wishes to canonicalise the phone number, then it can use the ``m.id.thirdparty``
    identifier type with a ``medium`` of ``msisdn`` instead.

    .. _/account/3pid:
        https://matrix.org/docs/spec/client_server/latest#post-matrix-client-r0-account-3pid
    """
    country: str
    phone: str
    type: UserIdentifierType = UserIdentifierType.PHONE


UserIdentifier = NewType('UserIdentifier',
                         Union[MatrixUserIdentifier, ThirdPartyIdentifier, PhoneIdentifier])


@deserializer(UserIdentifier)
def deserialize_user_identifier(data: JSON) -> Union[UserIdentifier, Obj]:
    try:
        identifier_type = UserIdentifierType.deserialize(data["type"])
    except KeyError:
        return Obj(**data)
    if identifier_type == UserIdentifierType.MATRIX_USER:
        return MatrixUserIdentifier.deserialize(data)
    elif identifier_type == UserIdentifierType.THIRD_PARTY:
        return ThirdPartyIdentifier.deserialize(data)
    elif identifier_type == UserIdentifierType.PHONE:
        return PhoneIdentifier.deserialize(data)
    else:
        return Obj(**data)


setattr(UserIdentifier, "deserialize", deserialize_user_identifier)


@dataclass
class DiscoveryServer(SerializableAttrs['DiscoveryServer']):
    base_url: Optional[str] = None


@dataclass
class DiscoveryIntegrationServer(SerializableAttrs['DiscoveryIntegrations']):
    ui_url: Optional[str] = None
    api_url: Optional[str] = None


@dataclass
class DiscoveryIntegrations(SerializableAttrs['DiscoveryIntegrations']):
    managers: List[DiscoveryIntegrationServer] = attr.ib(factory=lambda: [])


@dataclass
class DiscoveryInformation(SerializableAttrs['DiscoveryInformation']):
    homeserver: Optional[DiscoveryServer] = attr.ib(metadata={"json": "m.homeserver"},
                                                    factory=DiscoveryServer)
    identity_server: Optional[DiscoveryServer] = attr.ib(metadata={"json": "m.identity_server"},
                                                         factory=DiscoveryServer)
    integrations: Optional[DiscoveryServer] = attr.ib(metadata={"json": "m.integrations"},
                                                      factory=DiscoveryIntegrations)


@dataclass
class LoginResponse(SerializableAttrs['LoginResponse']):
    """
    The response for a login request, as specified in the `POST /login endpoint`_

    .. POST /login endpoint:
        https://matrix.org/docs/spec/client_server/r0.6.1#post-matrix-client-r0-login
    """
    user_id: UserID
    device_id: DeviceID
    access_token: str
    well_known: DiscoveryInformation = attr.ib(factory=DiscoveryInformation)
