// Copyright (c) 2026 Tulir Asokan
//
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/.

package main

/*
#include <stdint.h>
#include <stdlib.h>

typedef struct {
	uint64_t id;
	void *data;
	size_t data_len;
	void *body;
	size_t body_len;
} gothon_result;
*/
import "C"

import (
	"unsafe"
)

func main() {}

//export gothon_init
func gothon_init() C.int {
	if results.err != nil {
		return -1
	}
	return C.int(results.readFD)
}

//export gothon_call
func gothon_call(callID C.uint64_t, method *C.char, params unsafe.Pointer, paramsLen C.size_t, body unsafe.Pointer, bodyLen C.size_t) {
	call := &Call{
		ID:     uint64(callID),
		Method: C.GoString(method),
		Params: C.GoBytes(params, C.int(paramsLen)),
		Body:   C.GoBytes(body, C.int(bodyLen)),
	}
	go func() {
		results.push(call.Run())
	}()
}

//export gothon_call_sync
func gothon_call_sync(method *C.char, params unsafe.Pointer, paramsLen C.size_t, out *C.gothon_result) {
	call := &Call{
		Method: C.GoString(method),
		Params: C.GoBytes(params, C.int(paramsLen)),
	}
	call.Run().writeTo(out)
}

//export gothon_cancel
func gothon_cancel(callID C.uint64_t) {
	cancel, ok := activeCalls.Pop(uint64(callID))
	if ok {
		cancel()
	}
}

//export gothon_poll
func gothon_poll(out *C.gothon_result) C.int {
	res, ok := results.pop()
	if !ok {
		return 0
	}
	res.writeTo(out)
	return 1
}

//export gothon_free
func gothon_free(ptr unsafe.Pointer) {
	C.free(ptr)
}

func (res *Result) writeTo(out *C.gothon_result) {
	out.id = C.uint64_t(res.ID)
	out.data, out.data_len = toCBytes(res.Data)
	out.body, out.body_len = toCBytes(res.Body)
}

func toCBytes(data []byte) (unsafe.Pointer, C.size_t) {
	if len(data) == 0 {
		return nil, 0
	}
	return C.CBytes(data), C.size_t(len(data))
}
