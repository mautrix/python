// Copyright (c) 2026 Tulir Asokan
//
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/.

package main

import (
	"context"
	"encoding/json/v2"
	"fmt"
	"runtime/debug"

	"go.mau.fi/util/exsync"
)

type Handler func(ctx context.Context, params []byte, body []byte) (result any, resultBody []byte, err error)

var handlers = map[string]Handler{
	"client.new":  handle(newClient),
	"client.free": handle(freeClient),
	"request":     handleWithBody(request),

	"crypto.init":                              handle(initCrypto),
	"crypto.close":                             handle(closeCrypto),
	"crypto.encrypt":                           handle(encrypt),
	"crypto.decrypt":                           handle(decrypt),
	"crypto.verify_with_recovery_key":          handle(verifyWithRecoveryKey),
	"crypto.generate_recovery_key":             handle(generateRecoveryKey),
	"crypto.get_own_cross_signing_public_keys": handle(getOwnCrossSigningPublicKeys),
	"crypto.get_own_trust_state":               handle(getOwnTrustState),
}

func handle[Params, Result any](fn func(context.Context, *Params) (Result, error)) Handler {
	return handleWithBody(func(ctx context.Context, params *Params, _ []byte) (Result, []byte, error) {
		result, err := fn(ctx, params)
		return result, nil, err
	})
}

func handleWithBody[Params, Result any](fn func(context.Context, *Params, []byte) (Result, []byte, error)) Handler {
	return func(ctx context.Context, rawParams []byte, body []byte) (any, []byte, error) {
		var params Params
		if err := json.Unmarshal(rawParams, &params); err != nil {
			return nil, nil, fmt.Errorf("failed to parse params: %w", err)
		}
		return fn(ctx, &params, body)
	}
}

var activeCalls = exsync.NewMap[uint64, context.CancelFunc]()

type Call struct {
	ID     uint64
	Method string
	Params []byte
	Body   []byte
}

type response struct {
	Result any        `json:"result,omitzero"`
	Error  *ErrorInfo `json:"error,omitzero"`
}

func (call *Call) Run() *Result {
	ctx, cancel := context.WithCancel(context.Background())
	if call.ID != 0 {
		activeCalls.Set(call.ID, cancel)
		defer activeCalls.Delete(call.ID)
	}
	defer cancel()

	result, body, err := call.execute(ctx)
	var resp response
	if err != nil {
		resp.Error = makeErrorInfo(err)
	} else {
		resp.Result = result
	}
	data, err := json.Marshal(&resp)
	if err != nil {
		data, _ = json.Marshal(&response{Error: makeErrorInfo(fmt.Errorf("failed to marshal response: %w", err))})
		body = nil
	}
	return &Result{ID: call.ID, Data: data, Body: body}
}

func (call *Call) execute(ctx context.Context) (result any, body []byte, err error) {
	defer func() {
		if p := recover(); p != nil {
			err = fmt.Errorf("%s panicked: %v\n%s", call.Method, p, debug.Stack())
		}
	}()
	handler, ok := handlers[call.Method]
	if !ok {
		return nil, nil, fmt.Errorf("unknown method %q", call.Method)
	}
	return handler(ctx, call.Params, call.Body)
}
