## v0.20.8 (2025-06-01)

* *(bridge)* Added support for [MSC4190] (thanks to [@surakin] in [#175]).
* *(appservice)* Renamed `push_ephemeral` in generated registrations to
  `receive_ephemeral` to match the accepted version of [MSC2409].
* *(bridge)* Fixed compatibility with breaking change in aiohttp 3.12.6.

[MSC4190]: https://github.com/matrix-org/matrix-spec-proposals/pull/2781
[@surakin]: https://github.com/surakin
[#175]: https://github.com/mautrix/python/pull/175

## v0.20.7 (2025-01-03)

* *(types)* Removed support for generating reply fallbacks to implement
  [MSC2781]. Stripping fallbacks is still supported.

[MSC2781]: https://github.com/matrix-org/matrix-spec-proposals/pull/2781

## v0.20.6 (2024-07-12)

* *(bridge)* Added `/register` call if `/versions` fails with `M_FORBIDDEN`.

## v0.20.5 (2024-07-09)

**Note:** The `bridge` module is deprecated as all bridges are being rewritten
in Go. See <https://mau.fi/blog/2024-h1-mautrix-updates/> for more info.

* *(client)* Added support for authenticated media downloads.
* *(bridge)* Stopped using cached homeserver URLs for double puppeting if one
  is set in the config file.
* *(crypto)* Fixed error when checking OTK counts before uploading new keys.
* *(types)* Added MSC2530 (captions) fields to `MediaMessageEventContent`.

## v0.20.4 (2024-01-09)

* Dropped Python 3.9 support.
* *(client)* Changed media download methods to log requests and to raise
  exceptions on non-successful status codes.

## v0.20.3 (2023-11-10)

* *(client)* Deprecated MSC2716 methods and added new Beeper-specific batch
  send methods, as upstream MSC2716 support has been abandoned.
* *(util.async_db)* Added `PRAGMA synchronous = NORMAL;` to default pragmas.
* *(types)* Fixed `guest_can_join` field name in room directory response
  (thanks to [@ashfame] in [#163]).

[@ashfame]: https://github.com/ashfame
[#163]: https://github.com/mautrix/python/pull/163

## v0.20.2 (2023-09-09)

* *(crypto)* Changed `OlmMachine.share_keys` to make the OTK count parameter
  optional. When omitted, the count is fetched from the server.
* *(appservice)* Added option to run appservice transaction event handlers
  synchronously.
* *(appservice)* Added `log` and `hs_token` parameters to `AppServiceServerMixin`
  to allow using it as a standalone class without extending.
* *(api)* Added support for setting appservice `user_id` and `device_id` query
  parameters manually without using `AppServiceAPI`.

## v0.20.1 (2023-08-29)

* *(util.program)* Removed `--base-config` flag in bridges, as there are no
  valid use cases (package data should always work) and it's easy to cause
  issues by pointing the flag at the wrong file.
* *(bridge)* Added support for the `com.devture.shared_secret_auth` login type
  for automatic double puppeting.
* *(bridge)* Dropped support for syncing with double puppets. MSC2409 is now
  the only way to receive ephemeral events.
* *(bridge)* Added support for double puppeting with arbitrary `as_token`s.

## v0.20.0 (2023-06-25)

* Dropped Python 3.8 support.
* **Breaking change *(.state_store)*** Removed legacy SQLAlchemy state store
  implementations.
* **Mildly breaking change *(util.async_db)*** Changed `SQLiteDatabase` to not
  remove prefix slashes from database paths.
  * Library users should use `sqlite:path.db` instead of `sqlite:///path.db`
    for relative paths, and `sqlite:/path.db` instead of `sqlite:////path.db`
    for absolute paths.
  * Bridge configs do this migration automatically.
* *(util.async_db)* Added warning log if using SQLite database path that isn't
  writable.
* *(util.program)* Fixed `manual_stop` not working if it's called during startup.
* *(client)* Stabilized support for asynchronous uploads.
  * `unstable_create_msc` was renamed to `create_mxc`, and the `max_stall_ms`
    parameters for downloading were renamed to `timeout_ms`.
* *(crypto)* Added option to not rotate keys when devices change.
* *(crypto)* Added option to remove all keys that were received before the
  automatic ratcheting was implemented (in v0.19.10).
* *(types)* Improved reply fallback removal to have a smaller chance of false
  positives for messages that don't use reply fallbacks.

## v0.19.16 (2023-05-26)

* *(appservice)* Fixed Python 3.8 compatibility.

## v0.19.15 (2023-05-24)

* *(client)* Fixed dispatching room ephemeral events (i.e. typing notifications) in syncer.

## v0.19.14 (2023-05-16)

* *(bridge)* Implemented appservice pinging using MSC2659.
* *(bridge)* Started reusing aiosqlite connection pool for crypto db.
  * This fixes the crypto pool getting stuck if the bridge exits unexpectedly
    (the default pool is closed automatically at any type of exit).

## v0.19.13 (2023-04-24)

* *(crypto)* Fixed bug with redacting megolm sessions when device is deleted.

## v0.19.12 (2023-04-18)

* *(bridge)* Fixed backwards-compatibility with new key deletion config options.

## v0.19.11 (2023-04-14)

* *(crypto)* Fixed bug in previous release which caused errors if the `max_age`
  of a megolm session was not known.
* *(crypto)* Changed key receiving handler to fetch encryption config from
  server if it's not cached locally (to find `max_age` and `max_messages` more
  reliably).

## v0.19.10 (2023-04-13)

* *(crypto, bridge)* Added options to automatically ratchet/delete megolm
  sessions to minimize access to old messages.

## v0.19.9 (2023-04-12)

* *(crypto)* Fixed bug in crypto store migration when using outbound sessions
  with max age higher than usual.

## v0.19.8 (2023-04-06)

* *(crypto)* Updated crypto store schema to match mautrix-go.
* *(types)* Fixed `set_thread_parent` adding reply fallbacks to the message body.

## v0.19.7 (2023-03-22)

* *(bridge, crypto)* Fixed key sharing trust checker not resolving cross-signing
  signatures when minimum trust level is set to cross-signed.

## v0.19.6 (2023-03-13)

* *(crypto)* Added cache checks to prevent invalidating group session when the
  server sends a duplicate member event in /sync.
* *(util.proxy)* Fixed `min_wait_seconds` behavior and added `max_wait_seconds`
  and `multiply_wait_seconds` to `proxy_with_retry`.

## v0.19.5 (2023-03-07)

* *(util.proxy)* Added utility for dynamic proxies (from mautrix-instagram/facebook).
* *(types)* Added default value for `upload_size` in `MediaRepoConfig` as the
  field is optional in the spec.
* *(bridge)* Changed ghost invite handling to only process one per room at a time
  (thanks to [@maltee1] in [#132]).

[#132]: https://github.com/mautrix/python/pull/132

## v0.19.4 (2023-02-12)

* *(types)* Changed `set_thread_parent` to inherit the existing thread parent
  if a `MessageEvent` is passed, as starting threads from a message in a thread
  is not allowed.
* *(util.background_task)* Added new utility for creating background tasks
  safely, by ensuring that the task is not garbage collected before finishing
  and logging uncaught exceptions immediately.

## v0.19.3 (2023-01-27)

* *(bridge)* Bumped default timeouts for decrypting incoming messages.

## v0.19.2 (2023-01-14)

* *(util.async_body)* Added utility for reading aiohttp response into a bytearray
  (so that the output is mutable, e.g. for decrypting or encrypting media).
* *(client.api)* Fixed retry loop for MSC3870 URL uploads not exiting properly
  after too many errors.

## v0.19.1 (2023-01-11)

* Marked Python 3.11 as supported. Python 3.8 support will likely be dropped in
  the coming months.
* *(client.api)* Added request payload memory optimization to MSC3870 URL uploads.
  * aiohttp will duplicate the entire request body if it's raw bytes, which
    wastes a lot of memory. The optimization is passing an iterator instead of
    raw bytes, so aiohttp won't accidentally duplicate the whole thing.
  * The main `HTTPAPI` has had the optimization for a while, but uploading to
    URL calls aiohttp manually.

## v0.19.0 (2023-01-10)

* **Breaking change *(appservice)*** Removed typing status from state store.
* **Breaking change *(appservice)*** Removed `is_typing` parameter from
  `IntentAPI.set_typing` to make the signature match `ClientAPI.set_typing`.
  `timeout=0` is equivalent to the old `is_typing=False`.
* **Breaking change *(types)*** Removed legacy fields in Beeper MSS events.
* *(bridge)* Removed accidentally nested reply loop when accepting invites as
  the bridge bot.
* *(bridge)* Fixed decoding JSON values in config override env vars.

## v0.18.9 (2022-12-14)

* *(util.async_db)* Changed aiosqlite connector to force-enable foreign keys,
  WAL mode and busy_timeout.
  * The values can be changed by manually specifying the same PRAGMAs in the
    `init_commands` db arg, e.g. `- PRAGMA foreign_keys = OFF`.
* *(types)* Added workaround to `StateEvent.deserialize` to handle Conduit's
  broken `unsigned` fields.
* *(client.state_store)* Fixed `set_power_level` to allow raw dicts the same
  way as `set_encryption_info` does (thanks to [@bramenn] in [#127]).

[@bramenn]: https://github.com/bramenn
[#127]: https://github.com/mautrix/python/pull/127

## v0.18.8 (2022-11-18)

* *(crypto.store.asyncpg)* Fixed bug causing `put_group_session` to fail when
  trying to log unique key errors.
* *(client)* Added wrapper for `create_room` to update the state store with
  initial state and invites (applies to anything extending `StoreUpdatingAPI`,
  such as the high-level `Client` and appservice `IntentAPI` classes).

## v0.18.7 (2022-11-08)

## v0.18.6 (2022-10-24)

* *(util.formatter)* Added conversion method for `<hr>` tag and defaulted to
  converting back to `---`.

## v0.18.5 (2022-10-20)

* *(appservice)* Added try blocks around [MSC3202] handler functions to log
  errors instead of failing the entire transaction. This matches the behavior
  of errors in normal appservice event handlers.

## v0.18.4 (2022-10-13)

* *(client.api)* Added option to pass custom data to `/createRoom` to enable
  using custom fields and testing MSCs without changing the library.
* *(client.api)* Updated [MSC3870] support to send file name in upload complete
  call.
* *(types)* Changed `set_edit` to clear reply metadata as edits can't change
  the reply status.
* *(util.formatter)* Fixed edge case causing negative entity lengths when
  splitting entity strings.

## v0.18.3 (2022-10-11)

* *(util.async_db)* Fixed mistake in default no-op database error handler
  causing the wrong exception to be raised.
* *(crypto.store.asyncpg)* Updated `put_group_session` to catch unique key
  errors and log instead of raising.
* *(client.api)* Updated [MSC3870] support to catch and retry on all
  connection errors instead of only non-200 status codes when uploading.

## v0.18.2 (2022-09-24)

* *(crypto)* Fixed handling key requests when using appservice-mode (MSC2409)
  encryption.
* *(appservice)* Added workaround for dumb servers that send `"unsigned": null`
  in events.

## v0.18.1 (2022-09-15)

* *(crypto)* Fixed error sharing megolm session if a single recipient device
  has ran out of one-time keys.

## v0.18.0 (2022-09-15)

* **Breaking change *(util.async_db)*** Added checks to prevent calling
  `.start()` on a database multiple times.
* *(appservice)* Fixed [MSC2409] support to read to-device events from the
  correct field.
* *(appservice)* Added support for automatically calling functions when a
  transaction contains [MSC2409] to-device events or [MSC3202] encryption data.
* *(bridge)* Added option to use [MSC2409] and [MSC3202] for end-to-bridge
  encryption. However, this may not work with the Synapse implementation as it
  hasn't been tested yet.
* *(bridge)* Replaced `homeserver` -> `asmux` flag with more generic `software`
  field.
* *(bridge)* Added support for overriding parts of config with environment
  variables.
  * If the value starts with `json::`, it'll be parsed as JSON instead of using
    as a raw string.
* *(client.api)* Added support for [MSC3870] for both uploading and downloading
  media.
* *(types)* Added `knock_restricted` join rule to `JoinRule` enum.
* *(crypto)* Added warning logs if claiming one-time keys for other users fails.

[MSC3870]: https://github.com/matrix-org/matrix-spec-proposals/pull/3870

## v0.17.8 (2022-08-22)

* *(crypto)* Fixed parsing `/keys/claim` responses with no `failures` field.
* *(bridge)* Fixed parsing e2ee key sharing allow/minimum level config.

## v0.17.7 (2022-08-22)

* *(util.async_db)* Added `init_commands` to run commands on each SQLite
  connection (e.g. to enable `PRAGMA`s). No-op on Postgres.
* *(bridge)* Added check to make sure e2ee keys are intact on server.
  If they aren't, the crypto database will be wiped and the bridge will stop.

## v0.17.6 (2022-08-17)

* *(bridge)* Added hidden option to use appservice login for double puppeting.
* *(client)* Fixed sync handling throwing an error if event parsing failed.
* *(errors)* Added `M_UNKNOWN_ENDPOINT` error code from [MSC3743]
* *(appservice)* Updated [MSC3202] support to handle one time keys correctly.

[MSC3743]: https://github.com/matrix-org/matrix-spec-proposals/pull/3743

## v0.17.5 (2022-08-15)

* *(types)* Added `m.read.private` to receipt types.
* *(appservice)* Stopped `ensure_registered` and `invite_user` raising
  `IntentError`s (now they raise the original Matrix error instead).

## v0.17.4 (2022-07-28)

* *(bridge)* Started rejecting reusing access tokens when enabling double
  puppeting. Reuse is detected by presence of encryption keys on the device.
* *(client.api)* Added wrapper method for the `/context` API.
* *(api, errors)* Implemented new error codes from [MSC3848].
* *(types)* Disabled deserializing `m.direct` content (it didn't work and it
  wasn't really necessary).
* *(client.state_store)* Updated `set_encryption_info` to allow raw dicts.
  This fixes the bug where sending a `m.room.encryption` event with a raw dict
  as the content would throw an error from the state store.
* *(crypto)* Fixed error when fetching keys for user with no cross-signing keys
  (thanks to [@maltee1] in [#109]).

[MSC3848]: https://github.com/matrix-org/matrix-spec-proposals/pull/3848
[#109]: https://github.com/mautrix/python/pull/109

## v0.17.3 (2022-07-12)

* *(types)* Updated `BeeperMessageStatusEventContent` fields.

## v0.17.2 (2022-07-06)

* *(api)* Updated request logging to log full URL instead of only path.
* *(bridge)* Fixed migrating key sharing allow flag to new config format.
* *(appservice)* Added `beeper_new_messages` flag for `batch_send` method.

## v0.17.1 (2022-07-05)

* *(crypto)* Fixed Python 3.8/9 compatibility broken in v0.17.0.
* *(crypto)* Added some tests for attachments and store code.
* *(crypto)* Improved logging when device change validation fails.

## v0.17.0 (2022-07-05)

* **Breaking change *(bridge)*** Added options to check cross-signing status
  for bridge users. This requires changes to the base config.
  * New options include requiring cross-signed devices (with TOFU) for sending
    and/or receiving messages, and an option to drop any unencrypted messages.
* **Breaking change *(crypto)*** Removed `sender_key` parameter from
  CryptoStore's `has_group_session` and `put_group_session`, and also
  OlmMachine's `wait_for_session`.
* **Breaking change *(crypto.store.memory)*** Updated the key of the
  `_inbound_sessions` dict to be (room_id, session_id), removing the identity
  key in the middle. This only affects custom stores based on the memory store.
* *(crypto)* Added basic cross-signing validation code.
* *(crypto)* Marked device_id and sender_key as deprecated in Megolm events
  as per Matrix 1.3.
* *(api)* Bumped request logs to `DEBUG` level.
  * Also added new `sensitive` parameter to the `request` method to prevent
    logging content in sensitive requests. The `login` method was updated to
    mark the content as sensitive if a password or token is provided.
* *(bridge.commands)* Switched the order of the user ID parameter in `set-pl`,
  `set-avatar` and `set-displayname`.

## v0.16.11 (2022-06-28)

* *(appservice)* Fixed the `extra_content` parameter in membership methods
  causing duplicate join events through the `ensure_joined` mechanism.

## v0.16.10 (2022-06-24)

* *(bridge)* Started requiring Matrix v1.1 support from homeservers.
* *(bridge)* Added hack to automatically send a read receipt for messages sent
  to Matrix with double puppeting (to work around weird unread count issues).

## v0.16.9 (2022-06-22)

* *(client)* Added support for knocking on rooms (thanks to [@maltee1] in [#105]).
* *(bridge)* Added config option to set key rotation settings with e2be.

[#105]: https://github.com/mautrix/python/pull/105

## v0.16.8 (2022-06-20)

* *(bridge)* Updated e2be helper to stop bridge if syncing fails.
* *(util.async_db)* Updated asyncpg connector to stop program if an asyncpg
  `InternalClientError` is thrown. These errors usually cause everything to
  get stuck.
  * The behavior can be disabled by passing `meow_exit_on_ice` = `false` in
    the `db_args`.

## v0.16.7 (2022-06-19)

* *(util.formatter)* Added support for parsing `img` tags
  * By default, the `alt` or `title` attribute will be used as plaintext.
* *(types)* Added `notifications` object to power level content class.
* *(bridge)* Added utility methods for handling incoming knocks in
  `MatrixHandler` (thanks to [@maltee1] in [#103]).
* *(appservice)* Updated `IntentAPI` to add the `fi.mau.double_puppet_source`
  to all state events sent with double puppeted intents (previously it was only
  added to non-state events).

[#103]: https://github.com/mautrix/python/pull/103

## v0.16.6 (2022-06-02)

* *(bridge)* Fixed double puppeting `start` method not handling some errors
  from /whoami correctly.
* *(types)* Added `com.beeper.message_send_status` event type for bridging
  status.

## v0.16.5 (2022-05-26)

* *(bridge.commands)* Added `reason` field for `CommandEvent.redact`.
* *(client.api)* Added `reason` field for the `unban_user` method
  (thanks to [@maltee1] in [#101]).
* *(bridge)* Changed automatic DM portal creation to only apply when the invite
  event specifies `"is_direct": true` (thanks to [@maltee1] in [#102]).
* *(util.program)* Changed `Program` to use create and set an event loop
  explicitly instead of using `get_event_loop`.
* *(util.program)* Added optional `exit_code` parameter to `manual_stop`.
* *(util.manhole)* Removed usage of loop parameters to fix Python 3.10
  compatibility.
* *(appservice.api)* Switched `IntentAPI.batch_send` method to use custom Event
  classes instead of the default ones (since some normal event fields aren't
  applicable when batch sending).

[@maltee1]: https://github.com/maltee1
[#101]: https://github.com/mautrix/python/pull/101
[#102]: https://github.com/mautrix/python/pull/102

## v0.16.4 (2022-05-10)

* *(types, bridge)* Dropped support for appservice login with unstable prefix.
* *(util.async_db)* Fixed some database start errors causing unnecessary noise
  in logs.
* *(bridge.commands)* Added helper method to redact bridge commands.

## v0.16.3 (2022-04-21)

* *(types)* Changed `set_thread_parent` to have an explicit option for
  disabling the thread-as-reply fallback.

## v0.16.2 (2022-04-21)

* *(types)* Added `get_thread_parent` and `set_thread_parent` helper methods
  for `MessageEventContent`.
* *(bridge)* Increased timeout for `MessageSendCheckpoint.send`.

## v0.16.1 (2022-04-17)

* **Breaking change** Removed `r0` path support.
  * The new `v3` paths are implemented since Synapse 1.48, Dendrite 0.6.5,
    and Conduit 0.4.0. Servers older than these are no longer supported.

## v0.16.0 (2022-04-11)

* **Breaking change *(types)*** Removed custom `REPLY` relation type and
  changed `RelatesTo` structure to match the actual event content.
  * Applications using `content.get_reply_to()` and `content.set_reply()` will
    keep working with no changes.
* *(types)* Added `THREAD` relation type and `is_falling_back` field to
  `RelatesTo`.

## v0.15.8 (2022-04-08)

* *(client.api)* Added experimental prometheus metric for file upload speed.
* *(util.async_db)* Improved type hints for `UpgradeTable.register`
* *(util.async_db)* Changed connection string log to redact database password.

## v0.15.7 (2022-04-05)

* *(api)* Added `file_name` parameter to `HTTPAPI.get_download_url`.

## v0.15.6 (2022-03-30)

* *(types)* Fixed removing nested (i.e. malformed) reply fallbacks generated by
  some clients.
* *(types)* Added automatic reply fallback trimming to `set_reply()` to prevent
  accidentally creating nested reply fallbacks.

## v0.15.5 (2022-03-28)

* *(crypto)* Changed default behavior of OlmMachine to ignore instead of reject
  key requests from other users.
* Fixed some type hints

## v0.15.3 & v0.15.4 (2022-03-25)

* *(client.api)* Fixed incorrect HTTP methods in async media uploads.

## v0.15.2 (2022-03-25)

* *(client.api)* Added support for async media uploads ([MSC2246]).
* Moved `async_getter_lock` decorator to `mautrix.util` (from `mautrix.bridge`).
  * The old import path will keep working.

[MSC2246]: https://github.com/matrix-org/matrix-spec-proposals/pull/2246

## v0.15.1 (2022-03-23)

* *(types)* Added `ensure_has_html` method for `TextMessageEventContent` to
  generate a HTML `formatted_body` from the plaintext `body` correctly (i.e.
  escaping HTML and replacing newlines).

## v0.15.0 (2022-03-16)

* **Breaking change** Removed Python 3.7 support.
* **Breaking change *(api)*** Removed `r0` from default path builders in order
  to update to `v3` and per-endpoint versioning.
  * The client API modules have been updated to specify v3 in the paths, other
    direct usage of `Path`, `ClientPath` and `MediaPath` will have to be
    updated manually. `UnstableClientPath` no longer exists and should be
    replaced with `Path.unstable`.
  * There's a temporary hacky backwards-compatibility layer which replaces /v3
    with /r0 if the server doesn't advertise support for Matrix v1.1 or higher.
    It can be activated by calling the `.versions()` method in `ClientAPI`.
    The bridge module calls that method automatically.
* **Breaking change *(util.formatter)*** Removed lxml-based HTML parser.
  * The parsed data format is still compatible with lxml, so it is possible to
    use lxml with `MatrixParser` by setting `lxml.html.fromstring` as the
    `read_html` method.
* **Breaking change *(crypto)*** Moved `TrustState`, `DeviceIdentity`,
  `OlmEventKeys` and `DecryptedOlmEvent` dataclasses from `crypto.types`
  into `types.crypto`.
* **Breaking change *(bridge)*** Made `User.get_puppet` abstract and added new
  abstract `User.get_portal_with` and `Portal.get_dm_puppet` methods.
* Added a redundant `__all__` to various `__init__.py` files to appease pyright.
* *(api)* Reduced aiohttp memory usage when uploading large files by making
  an in-memory async iterable instead of passing the bytes directly.
* *(bridge)* Removed legacy community utilities.
* *(bridge)* Added support for creating DM portals with minimal bridge-specific code.
* *(util.async_db)* Fixed counting number of db upgrades.
* *(util.async_db)* Added support for schema migrations that jump versions.
* *(util.async_db)* Added system for preventing using the same database for
  multiple programs.
  * To enable it, provide an unique program name as the `owner_name` parameter
    in `Database.create`.
  * Additionally, if `ignore_foreign_tables` is set to `True`, it will check
    for tables of some known software like Synapse and Dendrite.
  * The `bridge` module enables both options by default.
* *(util.db)* Module deprecated. The async_db module is recommended. However,
  the SQLAlchemy helpers will remain until maubot has switched to asyncpg.
* *(util.magic)* Allowed `bytearray` as an input type for the `mimetype` method.
* *(crypto.attachments)* Added method to encrypt a `bytearray` in-place to
  avoid unnecessarily duplicating data in memory.

## v0.14.10 (2022-02-01)

* *(bridge)* Fixed accidentally broken Python 3.7 compatibility.

## v0.14.9 (2022-02-01)

* *(client.api)* Added `reason` field to `leave_room` and `invite_user` methods.

## v0.14.8 (2022-01-31)

* *(util.formatter)* Deprecated the lxml-based HTML parser and made the
  htmlparser-based parser the default. The lxml-based parser will be removed
  in v0.15.
* *(client.api)* Fixed `filter_json` parameter in `get_messages` not being sent
  to the server correctly.
* *(bridge)* Added utilities for implementing disappearing messages.

## v0.14.7 (2022-01-29)

* *(client)* Fixed error inviting users with custom member event content if the
  server had disabled fetching profiles.
* *(util.utf16_surrogate)* Added utilities for adding/removing unicode
  surrogate pairs in strings.
* *(util.magic)* Added check to make sure the parameter to `mimetype()` is
  either `bytes` or `str`.

## v0.14.6 (2022-01-26)

* **Breaking change *(util.message_send_checkpoint)*** Changed order of `send`
  parameters to match `BridgeState.send` (this is not used by most software,
  which is why the breaking change is in a patch release).
* *(util.async_db)* Changed the default size of the aiosqlite thread pool to 1,
  as it doesn't reliably work with higher values.
* *(util.async_db)* Added logging for database queries that take a long time
  (>1 second).
* *(client)* Added logging for sync requests that take a long time
  (>40 seconds, with the timeout being 30 seconds).
* *(util.variation_selector)* Fixed variation selectors being incorrectly added
  even if the emoji had a skin tone selector.
* *(bridge)* Fixed the process getting stuck if a config error caused the
  bridge to stop itself without stopping the SQLite thread.
* Added pre-commit hooks to run black, isort and some other checks.

## v0.14.5 (2022-01-14)

* *(util.formatter)* Removed the default handler for room pill conversion.
  * This means they'll be formatted as normal links unless the bridge or other
    thing using the formatter overrides `room_pill_to_fstring`.
* *(types)* Fixed the `event_id` property of `MatrixURI`s throwing an error
  (instead of returning `None`) when the parsed link didn't contain a second
  part with an event ID.

## v0.14.4 (2022-01-13)

* Bumped minimum yarl version to 1.5. v1.4 and below didn't allow `URL.build()`
  with a scheme but no host, which is used in the `matrix:` URI generator that
  was added in v0.14.3.
* *(appservice)* Removed support for adding a `group_id` to user namespaces in
  registration files.
* *(types)* Updated `Serializable.parse_json` type hint to allow `bytes` in
  addition to `str` (because `json.loads` allows both).
* *(bridge)* Added `retry_num` parameter to `User.send_remote_checkpoint`.

## v0.14.3 (2022-01-05)

* *(types)* Added `MatrixURI` type to parse and build `matrix:` URIs and
  `https://matrix.to` URLs.
* *(util.formatter)* `matrix:` URIs are now supported in incoming messages
  (using the new parser mentioned above).
* *(util.variation_selector)* Switched to generating list of emoji using data
  directly from the Unicode spec instead of emojibase.
* *(util.formatter)* Whitespace in non-`pre` elements is now compressed into
  a single space. Newlines are also replaced with a space instead of removed
  completely. Whitespace after a block element is removed completely.
* *(util.ffmpeg)* Added option to override output path, which allows outputting
  to stdout (by specifying `-`).
* *(util.config)* Changed `ConfigUpdateHelper.copy` to ignore comments if the
  entity being copied is a commentable yaml object (e.g. map or list).

## v0.14.2 (2021-12-30)

* *(appservice)* Fixed `IntentAPI` throwing an error when `redact` was called
  with a `reason`, but without `extra_content`.

## v0.14.1 (2021-12-29)

* *(util.ffmpeg)* Added simple utility module that wraps ffmpeg and tempfiles
  to convert audio/video files to different formats, primarily intended for
  bridging. FFmpeg must be installed separately and be present in `$PATH`.

## v0.14.0 (2021-12-26)

* **Breaking change *(mautrix.util.formatter)*** Made `MatrixParser` async
  and non-static.
  * Being async is necessary for bridges that need to make database calls to
    convert mentions (e.g. Telegram has @username mentions, which can't be
    extracted from the Matrix user ID).
  * Being non-static allows passing additional context into the formatter by
    extending the class and setting instance variables.
* *(util.formatter)* Added support for parsing
  [spoilers](https://spec.matrix.org/v1.1/client-server-api/#spoiler-messages).
* *(crypto.olm)* Added `describe` method for `OlmSession`s.
* *(crypto)* Fixed sorting Olm sessions (now sorted by last successful decrypt
  time instead of alphabetically by session ID).
* *(crypto.store.asyncpg)* Fixed caching Olm sessions so that using the same
  session twice wouldn't cause corruption.
* *(crypto.attachments)* Added support for decrypting files from
  non-spec-compliant clients (e.g. FluffyChat) that have a non-zero counter
  part in the AES initialization vector.
* *(util.async_db)* Added support for using Postgres positional param syntax in
  the async SQLite helper (by regex-replacing `$<number>` with `?<number>`).
* *(util.async_db)* Added wrapper methods for `executemany` in `Database` and
  aiosqlite `TxnConnection`.
* *(bridge)* Changed portal cleanup to leave and forget rooms using double
  puppeting instead of just kicking the user.

## v0.13.3 (2021-12-15)

* Fixed type hints in the `mautrix.crypto.store` module.
* Added debug logs for detecting crypto sync handling slowness.

## v0.13.2 (2021-12-15)

* Switched message double puppet indicator convention from
  `"net.maunium.<bridge_type>.puppet": true` to `"fi.mau.double_puppet_source": "<bridge_type>"`.
* Added double puppet indicator to redactions made with `IntentAPI.redact`.

## v0.13.1 (2021-12-12)

* Changed lack of media encryption dependencies (pycryptodome) to be a fatal
  error like lack of normal encryption dependencies (olm) are in v0.13.0.
* Added base methods for implementing relay mode in bridges
  (started by [@Alejo0290] in [#72]).

[@Alejo0290]: https://github.com/Alejo0290
[#72]: https://github.com/mautrix/python/pull/72

## v0.13.0 (2021-12-09)

* Formatted all code using [black](https://github.com/psf/black)
  and [isort](https://github.com/PyCQA/isort).
* Added `power_level_override` parameter to `ClientAPI.create_room`.
* Added default implementations of `delete-portal` and `unbridge` commands for bridges
* Added automatic Olm session recreation if an incoming message fails to decrypt.
* Added automatic key re-requests in bridges if the Megolm session doesn't arrive on time.
* Changed `ClientAPI.send_text` to parse the HTML to generate a plaintext body
  instead of using the HTML directly when a separate plaintext body is not
  provided (also affects `send_notice` and `send_emote`).
* Changed lack of encryption dependencies to be a fatal error if encryption is
  enabled in bridge config.
* Fixed `StoreUpdatingAPI` not updating the local state store when using
  friendly membership methods like `kick_user`.
* Switched Bridge class to use async_db (asyncpg/aiosqlite) instead of the
  legacy SQLAlchemy db by default.
* Removed deprecated `ClientAPI.parse_mxid` method
  (use `ClientAPI.parse_user_id` instead).
* Renamed `ClientAPI.get_room_alias` to `ClientAPI.resolve_room_alias`.

## v0.12.5 (2021-11-30)

* Added wrapper for [MSC2716]'s `/batch_send` endpoint in `IntentAPI`.
* Added some Matrix request metrics (thanks to [@jaller94] in [#68]).
* Added utility method for adding variation selector 16 to emoji strings the
  same way as Element does (using emojibase data).

[MSC2716]: https://github.com/matrix-org/matrix-spec-proposals/pull/2716
[@jaller94]: https://github.com/jaller94
[#68]: https://github.com/mautrix/python/pull/68

## v0.12.4 (2021-11-25)

* *(util.formatter)* Added support for parsing Matrix HTML colors.

## v0.12.3 (2021-11-23)

* Added autogenerated docs with Sphinx.
  * Rendered version available at https://docs.mau.fi/python/latest/
    (also version-specific docs at https://docs.mau.fi/python/v0.12.3/).
* Added asyncpg to client state store unit tests.
* Fixed client state store `get_members` being broken on asyncpg (broken in 0.12.2).
* Fixed `get_members_filtered` not taking the `memberships` parameter into
  account in the memory store.

## v0.12.2 (2021-11-20)

* Added more control over which membership states to return in client state store.
* Added some basic tests for the client state store.
* Fixed `OlmMachine.account` property not being defined before calling `load`.

## v0.12.1 (2021-11-19)

* Added default (empty) value for `unsigned` in the event classes.
* Updated the `PgStateStore` in the client module to fully implement the crypto
  `StateStore` abstract class.
  * The crypto module now has a `PgCryptoStateStore` that combines the client
    `PgStateStore` with the abstract crypto state store.

## v0.12.0 (2021-11-19)

* **Breaking change (client):** The `whoami` method now returns a dataclass
  with `user_id` and `device_id` fields, instead of just returning the
  `user_id` as a string.
* Added `delete` method for crypto stores (useful when changing the device ID).
* Added `DECRYPTED` step for message send checkpoints.
* Added proper user agent to bridge state and message send checkpoint requests.

## v0.11.4 (2021-11-16)

* Improved default event filter in bridges
  * The filtering method is now `allow_matrix_event` instead of
    `filter_matrix_event` and the return value is reversed.
  * Most bridges now don't need to override the method, so the old method isn't
    used at all.
* Added support for the stable version of [MSC2778].

## v0.11.3 (2021-11-13)

* Updated registering appservice ghosts to use `inhibit_login` flag to prevent
  lots of unnecessary access tokens from being created.
  * If you want to log in as an appservice ghost, you should use [MSC2778]'s
    appservice login (e.g. like the [bridge e2ee module does](https://github.com/mautrix/python/blob/v0.11.2/mautrix/bridge/e2ee.py#L178-L182) for example)
* Fixed unnecessary warnings about message send endpoints in some cases where
  the endpoint wasn't configured.

## v0.11.2 (2021-11-11)

* Updated message send checkpoint system to handle all cases where messages are
  dropped or consumed by mautrix-python.

## v0.11.1 (2021-11-10)

* Fixed regression in Python 3.8 support in v0.11.0 due to `asyncio.Queue` type hinting.
* Made the limit of HTTP connections to the homeserver configurable
  (thanks to [@justinbot] in [#64]).

[#64]: https://github.com/mautrix/python/pull/64

## v0.11.0 (2021-11-09)

* Added support for message send checkpoints (as HTTP requests, similar to the
  bridge state reporting system) by [@sumnerevans].
* Added support for aiosqlite with the same interface as asyncpg.
  * This includes some minor breaking changes to the asyncpg interface.
* Made config writing atomic (using a tempfile) to prevent the config
  disappearing when disk is full.
* Changed prometheus to start before rest of `startup_actions`
  (thanks to [@Half-Shot] in [#63]).
* Stopped reporting `STARTING` bridge state on startup by [@sumnerevans].

[@Half-Shot]: https://github.com/Half-Shot
[#63]: https://github.com/mautrix/python/pull/63

## v0.10.11 (2021-10-26)

* Added support for custom bridge bot welcome messages
  (thanks to [@justinbot] in [#58]).

[@justinbot]: https://github.com/justinbot
[#58]: https://github.com/mautrix/python/pull/58

## v0.10.10 (2021-10-08)

* Added support for disabling bridge management commands based on custom rules
  (thanks to [@tadzik] in [#56]).

[@tadzik]: https://github.com/tadzik
[#56]: https://github.com/mautrix/python/pull/56

## v0.10.9 (2021-09-29)

* Changed `remove_room_alias` to ignore `M_NOT_FOUND` errors by default, to
  preserve Synapse behavior on spec-compliant server implementations.
  The `raise_404` argument can be set to `True` to not suppress the errors.
* Fixed bridge state pings returning `UNCONFIGURED` as a global state event.

## v0.10.8 (2021-09-23)

* **Breaking change (serialization):** Removed `Generic[T]` backwards
  compatibility from `SerializableAttrs` (announced in [v0.9.6](https://github.com/mautrix/python/releases/tag/v0.9.6)).
* Stopped using `self.log` in `Program` config load errors as the logger won't
  be initialized yet.
* Added check to ensure reply fallback removal is only attempted once.
* Fixed `remove_event_handler` throwing a `KeyError` if no event handlers had
  been registered for the specified event type.
* Fixed deserialization showing wrong key names on missing key errors.

## v0.10.7 (2021-08-31)

* Removed Python 3.9+ features that were accidentally used in v0.10.6.

## v0.10.6 (2021-08-30)

* Split `_http_handle_transaction` in `AppServiceServerMixin` to allow easier reuse.

## v0.10.5 (2021-08-25)

* Fixed `MemoryStateStore`'s `get_members()` implementation (thanks to [@hifi] in [#54]).
* Re-added `/_matrix/app/com.beeper.bridge_state` endpoint.

[@hifi]: https://github.com/hifi
[#54]: https://github.com/mautrix/python/pull/54

## v0.10.4 (2021-08-18)

* Improved support for sending member events manually
  (when using the `extra_content` field in join, invite, etc).
  * There's now a `fill_member_event` method that's called by manual member
    event sending that adds the displayname and avatar URL. Alternatively,
    `fill_member_event_callback` can be set to fill the member event manually.

## v0.10.3 (2021-08-14)

* **Breaking change:** The bridge status notification system now uses a
  `BridgeStateEvent` enum instead of the `ok` boolean.
* Added better log messages when bridge encryption error notice fails to send.
* Added manhole for all bridges.
* Dropped Python 3.6 support in manhole.
* Switched to using `PyCF_ALLOW_TOP_LEVEL_AWAIT` for manhole in Python 3.8+.

## v0.9.10 (2021-07-24)

* Fixed async `Database` class mutating the `db_args` dict passed to it.
* Fixed `None`/`null` values with factory defaults being deserialized into the
  `attr.Factory` object instead of the expected value.

## v0.9.9 (2021-07-16)

* **Breaking change:** Made the `is_direct` property required in the bridge
  `Portal` class. The property was first added in v0.8.4 and is used for
  handling `m.room.encryption` events (enabling encryption).
* Added PEP 561 typing info (by [@sumnerevans] in [#49]).
* Added support for [MSC3202] in appservice module.
* Made bridge state filling more customizable.
* Moved `BridgeState` class from `mautrix.bridge` to `mautrix.util.bridge_state`.
* Fixed receiving appservice transactions with `Authorization` header
  (i.e. fixed [MSC2832] support).

[MSC3202]: https://github.com/matrix-org/matrix-spec-proposals/pull/3202
[MSC2832]: https://github.com/matrix-org/matrix-spec-proposals/pull/2832
[@sumnerevans]: https://github.com/sumnerevans
[#49]: https://github.com/mautrix/python/pull/49

## v0.9.8 (2021-06-24)

* Added `remote_id` field to `push_bridge_state` method.

## v0.9.7 (2021-06-22)

* Added tests for `factory` and `hidden` serializable attrs.
* Added `login-matrix`, `logout-matrix`, `ping-matrix` and `clear-cache-matrix`
  commands in the bridge module. To enable the commands, bridges must implement
  the `User.get_puppet()` method to return the `Puppet` instance corresponding
  to the user's remote ID.
* Fixed logging events that were ignored due to lack of permissions of the sender.
* Fixed deserializing encrypted edit events ([mautrix/telegram#623]).

[mautrix/telegram#623]: https://github.com/mautrix/telegram/issues/623

## v0.9.6 (2021-06-20)

* Replaced `GenericSerializable` with a bound `TypeVar`.
  * This means that classes extending `SerializableAttrs` no longer have to use
    the `class Foo(SerializableAttrs['Foo'])` syntax to get type hints, just
    `class Foo(SerializableAttrs)` is enough.
  * Backwards compatibility for using the `['Foo']` syntax will be kept until v0.10.
* Added `field()` as a wrapper for `attr.ib()` that makes it easier to add
  custom metadata for serializable attrs things.
* Added some tests for type utilities.
* Changed attribute used to exclude links from output in HTML parser.
  * New attribute is `data-mautrix-exclude-plaintext` and works for basic
    formatting (e.g. `<strong>`) in addition to `<a>`.
  * The previous attribute wasn't actually checked correctly, so it never worked.

## v0.9.5 (2021-06-11)

* Added `SynapseAdminPath` to build `/_synapse/admin` paths.

## v0.9.4 (2021-06-09)

* Updated bridge status pushing utility to support `remote_id` and `remote_name`
  fields to specify which account on the remote network is bridged.

## v0.9.3 (2021-06-04)

* Switched to stable space prefixes.
* Added option to send arbitrary content with membership events.
* Added warning if media encryption dependencies aren't installed.
* Added support for pycryptodomex for media encryption.
* Added utilities for pushing bridge status to an arbitrary HTTP endpoint.

## v0.9.2 (2021-04-26)

* Changed `update_direct_chats` bridge method to only send updated `m.direct`
  data if the content was modified.

## v0.9.1 (2021-04-20)

* Added type classes for VoIP.
* Added methods for modifying push rules and room tags.
* Switched to `asyncio.create_task` everywhere (replacing the older
  `loop.create_task` and `asyncio.ensure_future`).

## v0.9.0 (2021-04-16)

* Added option to retry all HTTP requests when encountering a HTTP network
  error or gateway error response (502/503/504)
  * Disabled by default, you need to set the `default_retry_count` field in
    `HTTPAPI` (or `Client`), or the `default_http_retry_count` field in
    `AppService` to enable.
  * Can also be enabled with `HTTPAPI.request()`s `retry_count` parameter.
  * The `mautrix.util.network_retry` module was removed as it became redundant.
* Fixed GET requests having a body ([#44]).

[#44]: https://github.com/mautrix/python/issues/44

## v0.8.18 (2021-04-01)

* Made HTTP request user agents more configurable.
  * Bridges will now include the name and version by default.
* Added some event types and classes for space events.
* Fixed local power level check failing for `m.room.member` events.

## v0.8.17 (2021-03-22)

* Added warning log when giving up on decrypting message.
* Added mimetype magic utility that supports both file-magic and python-magic.
* Updated asmux DM endpoint (`net.maunium.asmux` -> `com.beeper.asmux`).
* Moved RowProxy and ResultProxy imports into type checking ([#46]).
  This should fix SQLAlchemy 1.4+, but SQLAlchemy databases will likely be
  deprecated entirely in the future.

[#46]: https://github.com/mautrix/python/issues/46

## v0.8.16 (2021-02-16)

* Made the Bridge class automatically fetch media repo config at startup.
  Bridges are recommended to check `bridge.media_config.upload_size` before
  even downloading remote media.

## v0.8.15 (2021-02-08)

* Fixed the high-level `Client` class to not try to update state if there' no
  `state_store` set.

## v0.8.14 (2021-02-07)

* Added option to override the asyncpg pool used in the async `Database` wrapper.

## v0.8.13 (2021-02-07)

* Stopped checking error message when checking if user is not registered on
  whoami. Now it only requires the `M_FORBIDDEN` errcode instead of a specific
  human-readable error message.
* Added handling for missing `unsigned` object in membership events
  (thanks to [@jevolk] in [#39]).
* Added warning message when receiving encrypted messages with end-to-bridge
  encryption disabled.
* Added utility for mutexes in caching async getters to prevent race conditions.

[@jevolk]: https://github.com/jevolk
[#39]: https://github.com/mautrix/python/pull/39

## v0.8.12 (2021-02-01)

* Added handling for `M_NOT_FOUND` errors when getting pinned messages.
* Fixed bridge message send retrying so it always uses the same transaction ID.
* Fixed high-level `Client` class to automatically update state store with
  events from sync.

## v0.8.11 (2021-01-22)

* Added automatic login retry if double puppeting token is invalid on startup
  or gets invalidated while syncing.
* Fixed ExtensibleEnum leaking keys between different types.
* Allowed changing bot used in ensure_joined.

## v0.8.10 (2021-01-22)

* Changed attr deserialization errors to log full data instead of only known
  fields when deserialization fails.

## v0.8.9 (2021-01-21)

* Allowed `postgresql://` scheme in end-to-bridge encryption database URL
  (in addition to `postgres://`).
* Slightly improved attr deserialization error messages.

## v0.8.8 (2021-01-19)

* Changed end-to-bridge encryption to fail if homeserver doesn't advertise
  appservice login. This breaks Synapse 1.21, but there have been plenty of
  releases since then.
* Switched BaseFileConfig to use the built-in [pkgutil] instead of
  pkg_resources (which requires setuptools).
* Added handling for `M_NOT_FOUND` errors when updating `m.direct` account data
  through double puppeting in bridges.
* Added logging of data when attr deserializing fails.
* Exposed ExtensibleEnum in `mautrix.types` module.

[pkgutil]: https://docs.python.org/3/library/pkgutil.html

## v0.8.7 (2021-01-15)

* Changed attr deserializer to deserialize optional missing fields into `None`
  instead of `attr.NOTHING` by default.
* Added option not to use transaction for asyncpg database upgrades.

## v0.8.6 (2020-12-31)

* Added logging when sync errors are resolved.
* Made `.well-known` fetching ignore the response content type header.
* Added handling for users enabling encryption in private chat portals.

## v0.8.5 (2020-12-06)

* Made SerializableEnum work with int values.
* Added TraceLogger type hints to command handling classes.

## v0.8.4 (2020-12-02)

* Added logging when sync errors are resolved.
* Made `.well-known` fetching ignore the response content type header.
* Added handling for users enabling encryption in private chat portals.

## v0.8.3 (2020-11-17)

* Fixed typo in HTML reply fallback generation when target message is plaintext.
* Made `CommandEvent.mark_read` async instead of returning an awaitable,
  because sometimes it didn't return an awaitable.

## v0.8.2 (2020-11-10)

* Added utility function for retrying network calls
  (`from mautrix.util.network_retry import call_with_net_retry`).
* Updated `Portal._send_message` to use aforementioned utility function.

## v0.8.1 (2020-11-09)

* Changed `Portal._send_message` to retry after 5 seconds (up to 5 attempts
  total by default) if server returns 502/504 error or the connection fails.

## v0.8.0 (2020-11-07)

* Added support for cross-server double puppeting
  (thanks to [@ShadowJonathan] in [#26]).
* Added support for receiving ephemeral events pushed directly ([MSC2409]).
* Added `opt_prometheus` utility to add support for metrics without a hard
  dependency on the prometheus_client library.
* Added `formatted()` helper method to get the `formatted_body` of a text message.
* Bridge command system improvements
  (thanks to [@witchent] in [#29], [#30] and [#31]).
  * `CommandEvent`s now know which portal they were ran in. They also have a
    `main_intent` property that gets the portal's main intent or the bridge bot.
  * `CommandEvent.reply()` will now use the portal's main intent if the bridge
    bot is not in the room.
  * The `needs_auth` and `needs_admin` permissions are now included here
    instead of separately in each bridge.
  * Added `discard-megolm-session` command.
  * Moved `set-pl` and `clean-rooms` commands from mautrix-telegram.
* Switched to using yarl instead of manually concatenating base URL with path.
* Switched to appservice login ([MSC2778]) instead of shared secret login for
  bridge bot login in the end-to-bridge encryption helper.
* Switched to `TEXT` instead of `VARCHAR(255)` in all databases ([#28]).
* Changed replies to use a custom `net.maunium.reply` relation type instead of `m.reference`.
* Fixed potential db unique key conflicts when the membership state caches were
  updated from `get_joined_members`.
* Fixed database connection errors causing sync loops to stop completely.
* Fixed `EventType`s sometimes having `None` instead of
  `EventType.Class.UNKNOWN` as the type class.
* Fixed regex escaping in bridge registration generation.

[MSC2778]: https://github.com/matrix-org/matrix-spec-proposals/pull/2778
[MSC2409]: https://github.com/matrix-org/matrix-spec-proposals/pull/2409
[@ShadowJonathan]: https://github.com/ShadowJonathan
[@witchent]: https://github.com/witchent
[#26]: https://github.com/mautrix/python/pull/26
[#28]: https://github.com/mautrix/python/issues/28
[#29]: https://github.com/mautrix/python/pull/29
[#30]: https://github.com/mautrix/python/pull/30
[#31]: https://github.com/mautrix/python/pull/31

## v0.7.14 (2020-10-27)

* Wrapped union types in `NewType` to allow `setattr`.
  This fixes Python 3.6 and 3.9 compatibility.

## v0.7.13 (2020-10-09)

* Extended session wait time when handling encrypted messages in bridges:
  it'll now wait for 5 seconds, then send an error, then wait for 10 more
  seconds. If the keys arrive in those 10 seconds, the message is bridged
  and the error is redacted, otherwise the error is edited.

## v0.7.11 (2020-10-02)

* Lock olm sessions between encrypting and sending to make sure messages go out
  in the correct order.

## v0.7.10 (2020-09-29)

* Fixed deserializing the `info` object in media msgtypes into dataclasses.

## v0.7.9 (2020-09-28)

* Added parameter to change how long `EncryptionManager.decrypt()` should wait
  for the megolm session to arrive.
* Changed `get_displayname` and `get_avatar_url` to ignore `M_NOT_FOUND` errors.
* Updated type hint of `set_reply` to allow `EventID`s.

## v0.7.8 (2020-09-27)

* Made the `UUID` type de/serializable by default.

## v0.7.7 (2020-09-25)

* Added utility method for waiting for incoming group sessions in OlmMachine.
* Made end-to-bridge encryption helper wait for incoming group sessions for 3 seconds.

## v0.7.6 (2020-09-22)

* Fixed bug where parsing invite fails if `unsigned` is not set or null.
* Added trace logs when bridge module ignores messages.

## v0.7.5 (2020-09-19)

* Added utility for measuring async method time in prometheus.

## v0.7.4 (2020-09-19)

* Made `sender_device` optional in decrypted olm events.
* Added opt_prometheus utility for using prometheus as an optional dependency.
* Added Matrix event time processing metric for bridges when prometheus is installed.

## v0.7.3 (2020-09-17)

* Added support for telling the user about decryption errors in bridge module.

## v0.7.2 (2020-09-12)

* Added bridge config option to pass custom arguments to SQLAlchemy's `create_engine`.

## v0.7.1 (2020-09-09)

* Added optional automatic prometheus config to the `Program` class.

## v0.7.0 (2020-09-04)

* Added support for e2ee key sharing in `OlmMachine`
  (both sending and responding to requests).
* Added option for automatically sharing keys from bridges.
* Added account data get/set methods for `ClientAPI`.
* Added helper for bridges to update `m.direct` account data.
* Added default user ID and alias namespaces for bridge registration generation.
* Added asyncpg-based client state store implementation.
* Added filtering query parameters to `ClientAPI.get_members`.
* Changed attachment encryption methods to return `EncryptedFile` objects
  instead of dicts.
* Changed `SimpleLock` to use `asyncio.Event` instead of `asyncio.Future`.
* Made SQLAlchemy optional for bridges.
* Fixed error when profile endpoint responses are missing keys.

## v0.6.1 (2020-07-30)

* Fixed disabling notifications in many rooms at the same time.

## v0.6.0 (2020-07-27)

* Added native end-to-end encryption module.
  * Switched e2be helper to use native e2ee instead of matrix-nio.
  * Includes crypto stores based on pickle and asyncpg.
  * Added e2ee helper to high-level client module.
* Added support for getting `prev_content` from the top level in addition to `unsigned`.

## v0.5.8 (2020-07-27)

* Fixed deserializer using `attr.NOTHING` instead of `None` when there's no default value.

## v0.5.7 (2020-06-16)

* Added `alt_aliases` to canonical alias state event content
  (added in Matrix client-server spec r0.6.1).

## v0.5.6 (2020-06-15)

* Added support for adding aliases for bridge commands.

## v0.5.5 (2020-06-15)

* Added option to set default event type class in `EventType.find()`.

## v0.5.4 (2020-06-09)

* Fixed notification disabler breaking when not using double puppeting.

## v0.5.3 (2020-06-08)

* Added `NotificationDisabler` utility class for easily disabling notifications
  while a bridge backfills messages.

## v0.5.2 (2020-06-08)

* Added support for automatically calling `ensure_registered` if `whoami` says
  the bridge bot is not registered in `Bridge.wait_for_connection`.

## v0.5.1 (2020-06-05)

* Moved initializing end-to-bridge encryption to before other startup actions.

## v0.5.0 (2020-06-03)

* Added extensible enum class ([#14]).
* Added some asyncpg utilities.
* Added basic config validation support to disallow default values.
* Added matrix-nio based end-to-bridge encryption helper for bridges.
* Added option to use TLS for appservice listener.
* Added support for `Authorization` header from homeserver in appservice
  transaction handler.
* Added option to override appservice transaction handling method.
* Split `Bridge` initialization class into a more abstract `Program`.
* Split config loading.

[#14]: https://github.com/mautrix/python/issues/14

## v0.4.2 (2020-02-14)

* Added option to add custom arguments for programs based on the `Bridge` class.
* Added method for stopping a `Bridge`.
* Made `Obj` picklable.

## v0.4.1 (2020-01-07)

* Removed unfinished `enum.py`.
* Increased default config line wrapping width.
* Fixed default visibility when adding rooms and users with bridge community helper.

## v0.4.0 (2019-12-28)

* Initial "stable" release of the major restructuring.
  * Package now includes the Matrix client framework and other utilities
    instead of just an appservice module.
  * Package renamed from mautrix-appservice to mautrix.
  * Switched license from MIT to MPLv2.

## v0.3.11 (2019-06-20)

* Update state store after sending state event. This is required for some
  servers like t2bot.io that have disabled echoing state events to appservices.

## v0.3.10.dev1 (2019-05-23)

* Hacky fix for null `m.relates_to`'s.

## v0.3.9 (2019-05-11)

* Only use json.dumps() in request() if content is json-serializable.

## v0.3.8 (2019-02-13)

* Added missing room/event ID quotings.

## v0.3.7 (2018-09-28)

* Fixed `get_room_members()` returning `dict_keys` rather than `list` when
  getting only joined members.

## v0.3.6 (2018-08-06

* Fixed `get_room_joined_memberships()` (thanks to [@turt2live] in [#6]).

[@turt2live]: https://github.com/turt2live
[#6]: https://github.com/mautrix/python/pull/6

## v0.3.5 (2018-08-06)

* Added parameter to change aiohttp Application parameters.
* Fixed `get_power_levels()` with state store implementations that don't throw
  a `ValueError` on cache miss.

## v0.3.4 (2018-08-05)

* Updated `get_room_members()` to use `/joined_members` instead of `/members`
  when possible.

## v0.3.3 (2018-07-25)

* Updated some type hints.

## v0.3.2 (2018-07-23)

* Fixed HTTPAPI init for real users.
* Fixed content-type for empty objects.

## v0.3.1 (2018-07-22)

* Added support for real users.

## v0.3.0 (2018-07-10)

* Made `StateStore` into an abstract class for easier custom storage backends.
* Fixed response of `/transaction` to return empty object with 200 OK's as per spec.
* Fixed URL parameter encoding.
* Exported `IntentAPI` for type hinting.

## v0.2.0 (2018-06-24)

* Switched to GPLv3 to MIT license.
* Updated state store to store full member events rather than just the
  membership status.

## v0.1.5 (2018-05-06)

* Made room avatar in `set_room_avatar()` optional to allow unsetting avatar.

## v0.1.4 (2018-04-26)

* Added `send_sticker()`.

## v0.1.3 (2018-03-29)

* Fixed AppService log parameter type hint.
* Fixed timestamp handling.

## v0.1.2 (2018-03-29)

* Return 400 Bad Request if user/room query doesn't have user ID/alias field (respectively).
* Added support for timestamp massaging and source URLs.

## v0.1.1 (2018-03-11)

* Added type hints.
* Added power level checks to `set_state_event()`.
* Renamed repo to mautrix-appservice-python (PyPI package is still mautrix-appservice).

## v0.1.0 (2018-03-08)

* Initial version. Transferred from mautrix-telegram.
