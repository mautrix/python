// Copyright (c) 2026 Tulir Asokan
//
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/.

package main

import (
	"bytes"

	"github.com/rs/zerolog"
)

type LogParams struct {
	Name  string `json:"name"`
	Level int    `json:"level"`
}

type logWriter struct{}

func (logWriter) Write(p []byte) (int, error) {
	results.push(&Result{Data: bytes.Clone(p)})
	return len(p), nil
}

// newLogger creates a logger whose lines are passed to the Python logger with the given name.
func newLogger(params LogParams) zerolog.Logger {
	return zerolog.New(logWriter{}).
		Level(pythonToZerologLevel(params.Level)).
		With().
		Str("logger", params.Name).
		Logger()
}

func pythonToZerologLevel(level int) zerolog.Level {
	switch {
	case level < 10:
		return zerolog.TraceLevel
	case level < 20:
		return zerolog.DebugLevel
	case level < 30:
		return zerolog.InfoLevel
	case level < 40:
		return zerolog.WarnLevel
	default:
		return zerolog.ErrorLevel
	}
}
