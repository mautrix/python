# Copyright (c) 2021 Tulir Asokan
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from mautrix.api import Method, Path
from mautrix.types import (
    PushAction,
    PushCondition,
    PushRule,
    PushRuleID,
    PushRuleKind,
    PushRuleScope,
)

from ..base import BaseClientAPI


class PushRuleMethods(BaseClientAPI):
    """
    Methods in section 13.13 Push Notifications of the spec. These methods are used for modifying
    what triggers push notifications.

    See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#id89>`__"""

    async def get_push_rule(
        self, scope: PushRuleScope, kind: PushRuleKind, rule_id: PushRuleID
    ) -> PushRule:
        """
        Retrieve a single specified push rule.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#get-matrix-client-r0-pushrules-scope-kind-ruleid>`__

        Args:
            scope: The scope of the push rule.
            kind: The kind of rule.
            rule_id: The identifier of the rule.

        Returns:
            The push rule information.
        """
        resp = await self.api.request(Method.GET, Path.pushrules[scope][kind][rule_id])
        return PushRule.deserialize(resp)

    async def set_push_rule(
        self,
        scope: PushRuleScope,
        kind: PushRuleKind,
        rule_id: PushRuleID,
        actions: list[PushAction],
        pattern: str | None = None,
        before: PushRuleID | None = None,
        after: PushRuleID | None = None,
        conditions: list[PushCondition] = None,
    ) -> None:
        """
        Create or modify a push rule.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#put-matrix-client-r0-pushrules-scope-kind-ruleid>`__

        Args:
            scope: The scope of the push rule.
            kind: The kind of rule.
            rule_id: The identifier for the rule.
            before:
            after:
            actions: The actions to perform when the conditions for the rule are met.
            pattern: The glob-style pattern to match against for ``content`` rules.
            conditions: The conditions for the rule for ``underride`` and ``override`` rules.
        """
        query = {}
        if after:
            query["after"] = after
        if before:
            query["before"] = before
        content = {"actions": [act.serialize() for act in actions]}
        if conditions:
            content["conditions"] = [cond.serialize() for cond in conditions]
        if pattern:
            content["pattern"] = pattern
        await self.api.request(
            Method.PUT, Path.pushrules[scope][kind][rule_id], query_params=query, content=content
        )

    async def remove_push_rule(
        self, scope: PushRuleScope, kind: PushRuleKind, rule_id: PushRuleID
    ) -> None:
        """
        Remove a push rule.

        See also: `API reference <https://matrix.org/docs/spec/client_server/r0.6.1#delete-matrix-client-r0-pushrules-scope-kind-ruleid>`__

        Args:
            scope: The scope of the push rule.
            kind: The kind of rule.
            rule_id: The identifier of the rule.
        """
        await self.api.request(Method.DELETE, Path.pushrules[scope][kind][rule_id])
