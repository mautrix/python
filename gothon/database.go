// Copyright (c) 2026 Tulir Asokan
//
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/.

package main

import (
	"context"
	"fmt"
	"sync"

	_ "github.com/lib/pq"
	"github.com/rs/zerolog"
	"go.mau.fi/util/dbutil"
	_ "go.mau.fi/util/dbutil/litestream"
	"maunium.net/go/mautrix/crypto"
)

type DatabaseParams struct {
	Type string `json:"type"`
	URI  string `json:"uri"`
}

// Clients that use the same database share a connection pool, like they do on the Python side.
var databases = map[DatabaseParams]*dbutil.Database{}
var databasesLock sync.Mutex

func openDatabase(ctx context.Context, params DatabaseParams) (*dbutil.Database, error) {
	databasesLock.Lock()
	defer databasesLock.Unlock()
	if db, ok := databases[params]; ok {
		return db, nil
	}
	db, err := dbutil.NewWithDialect(params.URI, params.Type)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}
	err = crypto.NewSQLCryptoStore(db, cryptoDBLogger(zerolog.Nop()), "", "", nil).DB.Upgrade(ctx)
	if err != nil {
		_ = db.Close()
		return nil, fmt.Errorf("failed to upgrade crypto database: %w", err)
	}
	databases[params] = db
	return db, nil
}

func cryptoDBLogger(log zerolog.Logger) dbutil.DatabaseLogger {
	return dbutil.ZeroLogger(log.With().Str("db_section", "crypto").Logger())
}
