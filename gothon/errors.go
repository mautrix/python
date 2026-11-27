// Copyright (c) 2026 Tulir Asokan
//
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/.

package main

import (
	"context"
	"errors"

	"maunium.net/go/mautrix"
	"maunium.net/go/mautrix/crypto"
)

type ErrorType string

const (
	ErrorTypeHTTP            ErrorType = "http"
	ErrorTypeConnection      ErrorType = "connection"
	ErrorTypeCancelled       ErrorType = "cancelled"
	ErrorTypeEncryption      ErrorType = "encryption"
	ErrorTypeDecryption      ErrorType = "decryption"
	ErrorTypeSessionNotFound ErrorType = "session_not_found"
	ErrorTypeInternal        ErrorType = "internal"
)

type ErrorInfo struct {
	Type    ErrorType `json:"type"`
	Message string    `json:"message"`

	Status          int    `json:"status,omitzero"`
	ErrCode         string `json:"errcode,omitzero"`
	UnstableErrCode string `json:"unstable_errcode,omitzero"`
	Text            string `json:"text,omitzero"`
}

type typedError struct {
	Type ErrorType
	Err  error
}

func (te *typedError) Error() string {
	return te.Err.Error()
}

func (te *typedError) Unwrap() error {
	return te.Err
}

func withType(errType ErrorType, err error) error {
	if err == nil {
		return nil
	}
	return &typedError{Type: errType, Err: err}
}

// httpErrorWithBody carries the error response body, which mautrix-go returns separately from the error.
type httpErrorWithBody struct {
	mautrix.HTTPError
	Body []byte
}

func (he *httpErrorWithBody) Unwrap() error {
	return he.HTTPError
}

func makeErrorInfo(err error) *ErrorInfo {
	info := &ErrorInfo{Type: ErrorTypeInternal, Message: err.Error()}
	var typed *typedError
	var httpErr mautrix.HTTPError
	switch {
	case errors.Is(err, context.Canceled):
		info.Type = ErrorTypeCancelled
	case errors.Is(err, crypto.ErrNoSessionFound):
		info.Type = ErrorTypeSessionNotFound
	case errors.As(err, &typed):
		info.Type = typed.Type
	case errors.As(err, &httpErr) && httpErr.Response != nil && httpErr.WrappedError == nil:
		info.Type = ErrorTypeHTTP
		info.Status = httpErr.Response.StatusCode
		if httpErr.RespError != nil {
			info.ErrCode = httpErr.RespError.ErrCode
			info.Message = httpErr.RespError.Err
			info.UnstableErrCode, _ = httpErr.RespError.ExtraData["org.matrix.msc3848.unstable.errcode"].(string)
		}
		var withBody *httpErrorWithBody
		if errors.As(err, &withBody) {
			info.Text = string(withBody.Body)
		}
	case errors.As(err, &httpErr):
		info.Type = ErrorTypeConnection
	}
	return info
}
