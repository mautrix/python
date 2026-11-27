// Copyright (c) 2026 Tulir Asokan
//
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/.

package main

import (
	"sync"
	"syscall"
)

// Result is a finished call or, when ID is zero, a log line.
type Result struct {
	ID   uint64
	Data []byte
	Body []byte
}

// resultQueue holds results until Python polls them. A byte is written to the pipe whenever the
// queue becomes non-empty, which lets the asyncio event loop watch the read end with add_reader.
type resultQueue struct {
	lock    sync.Mutex
	items   []*Result
	readFD  int
	writeFD int
	err     error
}

var results = newResultQueue()

func newResultQueue() *resultQueue {
	var fds [2]int
	if err := syscall.Pipe(fds[:]); err != nil {
		return &resultQueue{err: err}
	}
	syscall.CloseOnExec(fds[0])
	syscall.CloseOnExec(fds[1])
	if err := syscall.SetNonblock(fds[1], true); err != nil {
		return &resultQueue{err: err}
	}
	return &resultQueue{readFD: fds[0], writeFD: fds[1]}
}

func (q *resultQueue) push(res *Result) {
	q.lock.Lock()
	wasEmpty := len(q.items) == 0
	q.items = append(q.items, res)
	q.lock.Unlock()
	if wasEmpty && q.err == nil {
		_, _ = syscall.Write(q.writeFD, []byte{1})
	}
}

func (q *resultQueue) pop() (*Result, bool) {
	q.lock.Lock()
	defer q.lock.Unlock()
	if len(q.items) == 0 {
		return nil, false
	}
	res := q.items[0]
	q.items[0] = nil
	q.items = q.items[1:]
	if len(q.items) == 0 {
		q.items = nil
	}
	return res, true
}
