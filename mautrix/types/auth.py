# Copyright (c) 2022 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from typing import List, NewType, Optional, Union

from attr import dataclass

from .primitive import JSON, DeviceID, UserID
from .util import ExtensibleEnum, Obj, SerializableAttrs, deserializer, field


class LoginType(ExtensibleEnum):
    """
    A login type, as specified in the `POST /login endpoint`_

    .. _POST /login endpoint:
        https://spec.matrix.org/v1.2/client-server-api/#post_matrixclientv3login
    """

    PASSWORD: "LoginType" = "m.login.password"
    TOKEN: "LoginType" = "m.login.token"
    SSO: "LoginType" = "m.login.sso"
    APPSERVICE: "LoginType" = "m.login.application_service"

    UNSTABLE_JWT: "LoginType" = "org.matrix.login.jwt"


@dataclass
class LoginFlow(SerializableAttrs):
    """
    A login flow, as specified in the `GET /login endpoint`_

    .. _GET /login endpoint:
        https://spec.matrix.org/v1.2/client-server-api/#get_matrixclientv3login
    """

    type: LoginType


@dataclass
class LoginFlowList(SerializableAttrs):
    flows: List[LoginFlow]

    def get_first_of_type(self, *types: LoginType) -> Optional[LoginFlow]:
        for flow in self.flows:
            if flow.type in types:
                return flow
        return None

    def supports_type(self, *types: LoginType) -> bool:
        return self.get_first_of_type(*types) is not None


class UserIdentifierType(ExtensibleEnum):
    """
    A user identifier type, as specified in the `Identifier types`_ section of the login spec.

    .. _Identifier types:
        https://spec.matrix.org/v1.2/client-server-api/#identifier-types
    """

    MATRIX_USER: "UserIdentifierType" = "m.id.user"
    THIRD_PARTY: "UserIdentifierType" = "m.id.thirdparty"
    PHONE: "UserIdentifierType" = "m.id.phone"


@dataclass
class MatrixUserIdentifier(SerializableAttrs):
    """
    A client can identify a user using their Matrix ID. This can either be the fully qualified
    Matrix user ID, or just the localpart of the user ID.
    """

    user: str
    """The Matrix user ID or localpart"""

    type: UserIdentifierType = UserIdentifierType.MATRIX_USER


@dataclass
class ThirdPartyIdentifier(SerializableAttrs):
    """
    A client can identify a user using a 3PID associated with the user's account on the homeserver,
    where the 3PID was previously associated using the `/account/3pid`_ API. See the `3PID Types`_
    Appendix for a list of Third-party ID media.

    .. _/account/3pid:
        https://spec.matrix.org/v1.2/client-server-api/#post_matrixclientv3account3pid
    .. _3PID Types:
        https://spec.matrix.org/v1.2/appendices/#3pid-types
    """

    medium: str
    address: str
    type: UserIdentifierType = UserIdentifierType.THIRD_PARTY


@dataclass
class PhoneIdentifier(SerializableAttrs):
    """
    A client can identify a user using a phone number associated with the user's account, where the
    phone number was previously associated using the `/account/3pid`_ API. The phone number can be
    passed in as entered by the user; the homeserver will be responsible for canonicalising it.
    If the client wishes to canonicalise the phone number, then it can use the ``m.id.thirdparty``
    identifier type with a ``medium`` of ``msisdn`` instead.

    .. _/account/3pid:
        https://spec.matrix.org/v1.2/client-server-api/#post_matrixclientv3account3pid
    """

    country: str
    phone: str
    type: UserIdentifierType = UserIdentifierType.PHONE


UserIdentifier = NewType(
    "UserIdentifier", Union[MatrixUserIdentifier, ThirdPartyIdentifier, PhoneIdentifier]
)


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
class DiscoveryServer(SerializableAttrs):
    base_url: Optional[str] = None


@dataclass
class DiscoveryIntegrationServer(SerializableAttrs):
    ui_url: Optional[str] = None
    api_url: Optional[str] = None


@dataclass
class DiscoveryIntegrations(SerializableAttrs):
    managers: List[DiscoveryIntegrationServer] = field(factory=lambda: [])


@dataclass
class DiscoveryInformation(SerializableAttrs):
    """
    .well-known discovery information, as specified in the `GET /.well-known/matrix/client endpoint`_

    .. _GET /.well-known/matrix/client endpoint:
        https://spec.matrix.org/v1.2/client-server-api/#getwell-knownmatrixclient
    """

    homeserver: Optional[DiscoveryServer] = field(json="m.homeserver", factory=DiscoveryServer)
    identity_server: Optional[DiscoveryServer] = field(
        json="m.identity_server", factory=DiscoveryServer
    )
    integrations: Optional[DiscoveryServer] = field(
        json="m.integrations", factory=DiscoveryIntegrations
    )


@dataclass
class LoginResponse(SerializableAttrs):
    """
    The response for a login request, as specified in the `POST /login endpoint`_

    .. _POST /login endpoint:
        https://spec.matrix.org/v1.2/client-server-api/#post_matrixclientv3login
    """

    user_id: UserID
    device_id: DeviceID
    access_token: str
    well_known: DiscoveryInformation = field(factory=DiscoveryInformation)


@dataclass
class WhoamiResponse(SerializableAttrs):
    """
    The response for a whoami request, as specified in the `GET /account/whoami endpoint`_

    .. _GET /account/whoami endpoint:
        https://spec.matrix.org/v1.2/client-server-api/#get_matrixclientv3accountwhoami
    """

    user_id: UserID
    device_id: Optional[DeviceID] = None
    is_guest: bool = False
