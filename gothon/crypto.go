// Copyright (c) 2026 Tulir Asokan
//
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/.

package main

import (
	"context"
	"encoding/json/jsontext"
	"errors"
	"fmt"
	"time"

	"maunium.net/go/mautrix"
	"maunium.net/go/mautrix/crypto"
	"maunium.net/go/mautrix/event"
	"maunium.net/go/mautrix/id"
)

const initialSessionWaitTimeout = 3 * time.Second
const extendedSessionWaitTimeout = 22 * time.Second

// Crypto is the end-to-end encryption state of a client. It has its own mautrix-go client with
// the access token, so that the token is never sent with requests that Python makes to other URLs.
type Crypto struct {
	Client     *mautrix.Client
	Machine    *crypto.OlmMachine
	StateStore *mautrix.MemoryStateStore
	Syncer     *mautrix.DefaultSyncer
}

type InitCryptoParams struct {
	ClientID    uint64         `json:"client_id"`
	UserID      id.UserID      `json:"user_id"`
	DeviceID    id.DeviceID    `json:"device_id"`
	AccessToken string         `json:"access_token"`
	Database    DatabaseParams `json:"database"`
	AccountID   string         `json:"account_id"`
	PickleKey   string         `json:"pickle_key"`
	Log         LogParams      `json:"log"`
}

type InitCryptoResult struct {
	Fingerprint string `json:"fingerprint"`
}

func initCrypto(ctx context.Context, params *InitCryptoParams) (*InitCryptoResult, error) {
	client, err := getClient(params.ClientID)
	if err != nil {
		return nil, err
	}
	db, err := openDatabase(ctx, params.Database)
	if err != nil {
		return nil, err
	}
	log := newLogger(params.Log)
	cli := &mautrix.Client{
		HomeserverURL: client.HTTP.HomeserverURL,
		UserID:        params.UserID,
		DeviceID:      params.DeviceID,
		AccessToken:   params.AccessToken,
		UserAgent:     client.HTTP.UserAgent,
		Client:        client.HTTP.Client,
		Log:           log,
	}
	stateStore := mautrix.NewMemoryStateStore().(*mautrix.MemoryStateStore)
	cli.StateStore = stateStore
	cryptoStore := crypto.NewSQLCryptoStore(db, cryptoDBLogger(log), params.AccountID, params.DeviceID, []byte(params.PickleKey))
	storedDeviceID, err := cryptoStore.FindDeviceID(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to find existing device ID: %w", err)
	} else if storedDeviceID != "" && storedDeviceID != params.DeviceID {
		return nil, fmt.Errorf("mismatching device ID in client and crypto store (%q != %q)", params.DeviceID, storedDeviceID)
	}

	mach := crypto.NewOlmMachine(cli, &log, cryptoStore, stateStore)
	if err = mach.Load(ctx); err != nil {
		return nil, fmt.Errorf("failed to load olm account: %w", err)
	} else if !mach.GetAccount().Shared {
		if err = mach.ShareKeys(ctx, -1); err != nil {
			return nil, fmt.Errorf("failed to share keys: %w", err)
		}
	}

	syncer := mautrix.NewDefaultSyncer()
	syncer.OnSync(mach.ProcessSyncResponse)
	syncer.OnEventType(event.StateMember, mach.HandleMemberEvent)
	syncer.OnEventType(event.StateHistoryVisibility, mach.HandleHistoryVisibility)
	syncer.OnEvent(cli.StateStoreSyncHandler)

	prev := client.Crypto.Swap(&Crypto{
		Client:     cli,
		Machine:    mach,
		StateStore: stateStore,
		Syncer:     syncer,
	})
	if prev != nil {
		prev.Machine.Destroy()
	}
	return &InitCryptoResult{Fingerprint: mach.Fingerprint()}, nil
}

func (client *Client) closeCrypto() {
	if prev := client.Crypto.Swap(nil); prev != nil {
		prev.Machine.Destroy()
	}
}

func getCrypto(clientID uint64) (*Crypto, error) {
	client, err := getClient(clientID)
	if err != nil {
		return nil, err
	}
	c := client.Crypto.Load()
	if c == nil {
		return nil, fmt.Errorf("encryption is not enabled for client %d", clientID)
	}
	return c, nil
}

func closeCrypto(_ context.Context, params *ClientParams) (*struct{}, error) {
	client, err := getClient(params.ClientID)
	if err != nil {
		return nil, err
	}
	client.closeCrypto()
	return nil, nil
}

type EncryptParams struct {
	ClientID  uint64         `json:"client_id"`
	RoomID    id.RoomID      `json:"room_id"`
	EventType string         `json:"event_type"`
	Content   jsontext.Value `json:"content"`
}

func encrypt(ctx context.Context, params *EncryptParams) (*event.EncryptedEventContent, error) {
	c, err := getCrypto(params.ClientID)
	if err != nil {
		return nil, err
	}
	evtType := event.Type{Type: params.EventType, Class: event.MessageEventType}
	encrypted, err := c.Machine.EncryptMegolmEvent(ctx, params.RoomID, evtType, params.Content)
	if crypto.IsShareError(err) {
		if err = c.shareGroupSession(ctx, params.RoomID); err != nil {
			return nil, withType(ErrorTypeEncryption, fmt.Errorf("failed to share group session: %w", err))
		}
		encrypted, err = c.Machine.EncryptMegolmEvent(ctx, params.RoomID, evtType, params.Content)
	}
	return encrypted, withType(ErrorTypeEncryption, err)
}

func (c *Crypto) shareGroupSession(ctx context.Context, roomID id.RoomID) error {
	fetched, err := c.StateStore.HasFetchedMembers(ctx, roomID)
	if err != nil {
		return err
	} else if !fetched {
		if _, err = c.Client.Members(ctx, roomID); err != nil {
			return fmt.Errorf("failed to fetch member list: %w", err)
		}
	}
	members, err := c.StateStore.GetRoomJoinedOrInvitedMembers(ctx, roomID)
	if err != nil {
		return fmt.Errorf("failed to get member list: %w", err)
	}
	return c.Machine.ShareGroupSession(ctx, roomID, members)
}

type DecryptParams struct {
	ClientID       uint64       `json:"client_id"`
	Event          *event.Event `json:"event"`
	WaitForSession bool         `json:"wait_for_session"`
}

type DecryptResult struct {
	Event         *event.Event `json:"event"`
	TrustState    int          `json:"trust_state"`
	ForwardedKeys bool         `json:"forwarded_keys"`
}

func decrypt(ctx context.Context, params *DecryptParams) (*DecryptResult, error) {
	c, err := getCrypto(params.ClientID)
	if err != nil {
		return nil, err
	}
	evt := params.Event
	evt.Type.Class = event.MessageEventType
	if err = evt.Content.ParseRaw(evt.Type); err != nil {
		return nil, withType(ErrorTypeDecryption, err)
	}
	decrypted, err := c.Machine.DecryptMegolmEvent(ctx, evt)
	if params.WaitForSession && errors.Is(err, crypto.ErrNoSessionFound) && c.waitForSession(ctx, evt) {
		decrypted, err = c.Machine.DecryptMegolmEvent(ctx, evt)
	}
	if err != nil {
		return nil, withType(ErrorTypeDecryption, err)
	}
	result := &DecryptResult{
		Event:         decrypted,
		TrustState:    int(decrypted.Mautrix.TrustState),
		ForwardedKeys: decrypted.Mautrix.ForwardedKeys,
	}
	// The raw content includes fields that the parsed content struct doesn't know about.
	decrypted.Content = event.Content{VeryRaw: decrypted.Content.VeryRaw}
	return result, nil
}

func (c *Crypto) waitForSession(ctx context.Context, evt *event.Event) bool {
	content := evt.Content.AsEncrypted()
	if c.Machine.WaitForSession(ctx, evt.RoomID, content.SenderKey, content.SessionID, initialSessionWaitTimeout) {
		return true
	}
	go c.requestSession(context.WithoutCancel(ctx), evt)
	return c.Machine.WaitForSession(ctx, evt.RoomID, content.SenderKey, content.SessionID, extendedSessionWaitTimeout)
}

func (c *Crypto) requestSession(ctx context.Context, evt *event.Event) {
	content := evt.Content.AsEncrypted()
	deviceID := content.DeviceID
	if deviceID == "" {
		deviceID = "*"
	}
	err := c.Machine.SendRoomKeyRequest(ctx, evt.RoomID, content.SenderKey, content.SessionID, "", map[id.UserID][]id.DeviceID{
		evt.Sender:      {deviceID},
		c.Client.UserID: {"*"},
	})
	if err != nil {
		c.Client.Log.Warn().Err(err).Stringer("session_id", content.SessionID).Msg("Failed to send key request")
	}
}

type RecoveryKeyParams struct {
	ClientID    uint64 `json:"client_id"`
	RecoveryKey string `json:"recovery_key"`
}

func verifyWithRecoveryKey(ctx context.Context, params *RecoveryKeyParams) (*struct{}, error) {
	c, err := getCrypto(params.ClientID)
	if err != nil {
		return nil, err
	}
	return nil, c.Machine.VerifyWithRecoveryKey(ctx, params.RecoveryKey)
}

type RecoveryKeyResult struct {
	RecoveryKey string `json:"recovery_key"`
}

func generateRecoveryKey(ctx context.Context, params *ClientParams) (*RecoveryKeyResult, error) {
	c, err := getCrypto(params.ClientID)
	if err != nil {
		return nil, err
	}
	recoveryKey, err := c.Machine.GenerateAndVerifyWithRecoveryKey(ctx)
	if err != nil {
		return nil, err
	}
	return &RecoveryKeyResult{RecoveryKey: recoveryKey}, nil
}

type CrossSigningPublicKeys struct {
	MasterKey      id.Ed25519 `json:"master_key"`
	SelfSigningKey id.Ed25519 `json:"self_signing_key"`
	UserSigningKey id.Ed25519 `json:"user_signing_key"`
}

func getOwnCrossSigningPublicKeys(ctx context.Context, params *ClientParams) (*CrossSigningPublicKeys, error) {
	c, err := getCrypto(params.ClientID)
	if err != nil {
		return nil, err
	}
	keys, err := c.Machine.GetOwnCrossSigningPublicKeys(ctx)
	if err != nil || keys == nil {
		return nil, err
	}
	return &CrossSigningPublicKeys{
		MasterKey:      keys.MasterKey,
		SelfSigningKey: keys.SelfSigningKey,
		UserSigningKey: keys.UserSigningKey,
	}, nil
}

type TrustStateResult struct {
	TrustState int `json:"trust_state"`
}

func getOwnTrustState(ctx context.Context, params *ClientParams) (*TrustStateResult, error) {
	c, err := getCrypto(params.ClientID)
	if err != nil {
		return nil, err
	}
	trustState, err := c.Machine.ResolveTrustContext(ctx, c.Machine.OwnIdentity())
	if err != nil {
		return nil, err
	}
	return &TrustStateResult{TrustState: int(trustState)}, nil
}
