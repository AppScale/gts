// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

/*
Package runtime exposes information about the resource usage of the application.
It also provides a way to run code in a new background context of a backend.
*/
package runtime

import (
	"net/http"

	"appengine"
	"appengine_internal"

	pb "appengine_internal/system"
)

// Statistics represents the system's statistics.
type Statistics struct {
	// CPU records the CPU consumed by this instance, in megacycles.
	CPU struct {
		Total   float64
		Rate1M  float64 // consumption rate over one minute
		Rate10M float64 // consumption rate over ten minutes
	}
	// RAM records the memory used by the instance, in megabytes.
	RAM struct {
		Current    float64
		Average1M  float64 // average usage over one minute
		Average10M float64 // average usage over ten minutes
	}
}

func Stats(c appengine.Context) (*Statistics, error) {
	req := &pb.GetSystemStatsRequest{}
	res := &pb.GetSystemStatsResponse{}
	if err := c.Call("system", "GetSystemStats", req, res, nil); err != nil {
		return nil, err
	}
	s := &Statistics{}
	if res.Cpu != nil {
		s.CPU.Total = res.Cpu.GetTotal()
		s.CPU.Rate1M = res.Cpu.GetRate1M()
		s.CPU.Rate10M = res.Cpu.GetRate10M()
	}
	if res.Memory != nil {
		s.RAM.Current = res.Memory.GetCurrent()
		s.RAM.Average1M = res.Memory.GetAverage1M()
		s.RAM.Average10M = res.Memory.GetAverage10M()
	}
	return s, nil
}

/*
RunInBackground makes an API call that triggers an /_ah/background request.

There are two independent code paths that need to make contact:
the RunInBackground code, and the /_ah/background handler. The matchmaker
loop arranges for the two paths to meet. The RunInBackground code passes
a send to the matchmaker, the /_ah/background passes a recv to the matchmaker,
and the matchmaker hooks them up.
*/

func init() {
	http.HandleFunc("/_ah/background", handleBackground)

	sc := make(chan send)
	rc := make(chan recv)
	sendc, recvc = sc, rc
	go matchmaker(sc, rc)
}

var (
	sendc chan<- send // RunInBackground sends to this
	recvc chan<- recv // handleBackground sends to this
)

type send struct {
	id string
	f  func(appengine.Context)
}

type recv struct {
	id string
	ch chan<- func(appengine.Context)
}

func matchmaker(sendc <-chan send, recvc <-chan recv) {
	// When one side of the match arrives before the other
	// it is inserted in the corresponding map.
	waitSend := make(map[string]send)
	waitRecv := make(map[string]recv)

	for {
		select {
		case s := <-sendc:
			if r, ok := waitRecv[s.id]; ok {
				// meet!
				delete(waitRecv, s.id)
				r.ch <- s.f
			} else {
				// waiting for r
				waitSend[s.id] = s
			}
		case r := <-recvc:
			if s, ok := waitSend[r.id]; ok {
				// meet!
				delete(waitSend, r.id)
				r.ch <- s.f
			} else {
				// waiting for s
				waitRecv[r.id] = r
			}
		}
	}
}

var newContext = appengine.NewContext // for testing

func handleBackground(w http.ResponseWriter, req *http.Request) {
	id := req.Header.Get("X-AppEngine-BackgroundRequest")

	ch := make(chan func(appengine.Context))
	recvc <- recv{id, ch}
	(<-ch)(newContext(req))
}

// RunInBackground runs f in a background goroutine in this process.
// This is only valid to invoke from a backend.
func RunInBackground(c appengine.Context, f func(c appengine.Context)) error {
	req := &pb.StartBackgroundRequestRequest{}
	res := &pb.StartBackgroundRequestResponse{}
	if err := c.Call("system", "StartBackgroundRequest", req, res, nil); err != nil {
		return err
	}
	sendc <- send{res.GetRequestId(), f}
	return nil
}

func init() {
	appengine_internal.RegisterErrorCodeMap("system", pb.SystemServiceError_ErrorCode_name)
}
