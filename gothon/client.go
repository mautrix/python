// Copyright (c) 2026 Tulir Asokan
//
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/.

package main

import (
	"context"
	"encoding/json/v2"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"sync/atomic"
	"time"

	"github.com/rs/zerolog"
	"go.mau.fi/util/exsync"
	"maunium.net/go/mautrix"
)

// Client is the Go side of a Python HTTPAPI instance. Requests from Python go through HTTP, which
// doesn't have an access token, because Python sets the Authorization header itself.
type Client struct {
	HTTP   *mautrix.Client
	Crypto atomic.Pointer[Crypto]
}

var clients = exsync.NewMap[uint64, *Client]()
var nextClientID atomic.Uint64
var noopLogger = zerolog.Nop()

func getClient(clientID uint64) (*Client, error) {
	client, ok := clients.Get(clientID)
	if !ok {
		return nil, fmt.Errorf("unknown client %d", clientID)
	}
	return client, nil
}

type NewClientParams struct {
	BaseURL   string    `json:"base_url"`
	UserAgent string    `json:"user_agent"`
	Log       LogParams `json:"log"`
}

type NewClientResult struct {
	ClientID uint64 `json:"client_id"`
}

func newClient(_ context.Context, params *NewClientParams) (*NewClientResult, error) {
	baseURL, err := url.Parse(params.BaseURL)
	if err != nil {
		return nil, fmt.Errorf("failed to parse base URL: %w", err)
	}
	clientID := nextClientID.Add(1)
	clients.Set(clientID, &Client{
		HTTP: &mautrix.Client{
			HomeserverURL: baseURL,
			UserAgent:     params.UserAgent,
			Client:        &http.Client{Timeout: 5 * time.Minute},
			Log:           newLogger(params.Log),
		},
	})
	return &NewClientResult{ClientID: clientID}, nil
}

type ClientParams struct {
	ClientID uint64 `json:"client_id"`
}

func freeClient(_ context.Context, params *ClientParams) (*struct{}, error) {
	client, ok := clients.Pop(params.ClientID)
	if ok {
		client.closeCrypto()
	}
	return nil, nil
}

type RequestParams struct {
	ClientID   uint64            `json:"client_id"`
	Method     string            `json:"method"`
	URL        string            `json:"url"`
	Headers    map[string]string `json:"headers"`
	RetryCount int               `json:"retry_count"`
	IsSync     bool              `json:"is_sync"`
}

type RequestResult struct {
	Status int `json:"status"`
}

func request(ctx context.Context, params *RequestParams, body []byte) (*RequestResult, []byte, error) {
	client, err := getClient(params.ClientID)
	if err != nil {
		return nil, nil, err
	}
	headers := make(http.Header, len(params.Headers))
	for key, value := range params.Headers {
		headers.Set(key, value)
	}
	req := mautrix.FullRequest{
		Method:      params.Method,
		URL:         params.URL,
		Headers:     headers,
		MaxAttempts: params.RetryCount + 1,
		Logger:      &noopLogger,
	}
	if params.Method != http.MethodGet && params.Method != http.MethodHead {
		req.RequestBytes = body
	}
	data, resp, err := client.HTTP.MakeFullRequestWithResp(ctx, req)
	var httpErr mautrix.HTTPError
	if errors.As(err, &httpErr) && len(data) > 0 {
		return nil, nil, &httpErrorWithBody{HTTPError: httpErr, Body: data}
	} else if err != nil {
		return nil, nil, err
	}
	if params.IsSync {
		client.processSync(ctx, params.URL, data)
	}
	return &RequestResult{Status: resp.StatusCode}, data, nil
}

func (client *Client) processSync(ctx context.Context, syncURL string, data []byte) {
	c := client.Crypto.Load()
	if c == nil {
		return
	}
	log := c.Client.Log
	parsedURL, err := url.Parse(syncURL)
	if err != nil {
		log.Err(err).Msg("Failed to parse sync URL")
		return
	}
	var resp mautrix.RespSync
	if err = json.Unmarshal(data, &resp); err != nil {
		log.Err(err).Msg("Failed to parse sync response")
		return
	}
	if err = c.Syncer.ProcessResponse(ctx, &resp, parsedURL.Query().Get("since")); err != nil {
		log.Err(err).Msg("Failed to process sync response")
	}
}
