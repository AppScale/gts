// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package guestbook

import (
	"http"
	"io"
	"os"
	"template"
	"time"

	"appengine"
	"appengine/datastore"
	"appengine/user"
)

type Greeting struct {
	Author  string
	Content string
	Date    datastore.Time
}

func serve404(w http.ResponseWriter) {
	w.WriteHeader(http.StatusNotFound)
	w.Header().Set("Content-Type", "text/plain")
	io.WriteString(w, "Not Found")
}

func serveError(c appengine.Context, w http.ResponseWriter, err os.Error) {
	w.WriteHeader(http.StatusInternalServerError)
	w.Header().Set("Content-Type", "text/plain")
	io.WriteString(w, "Internal Server Error")
	c.Logf("%v", err)
}

var mainPage = template.MustParse(`<html><body>
{.repeated section @}
{.section Author}<b>{@|html}</b>{.or}An anonymous person{.end}
wrote <blockquote>{Content|html}</blockquote>
{.end}
<form action="/sign" method="post">
<div><textarea name="content" rows="3" cols="60"></textarea></div>
<div><input type="submit" value="Sign Guestbook"></div>
</form></body></html>`,
	nil)

func handleMainPage(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" || r.URL.Path != "/" {
		serve404(w)
		return
	}
	c := appengine.NewContext(r)
	q := datastore.NewQuery("Greeting").Order("-Date").Limit(10)
	var gg []*Greeting
	_, err := q.GetAll(c, &gg)
	if err != nil {
		serveError(c, w, err)
		return
	}
	w.Header().Set("Content-Type", "text/html")
	if err := mainPage.Execute(w, gg); err != nil {
		c.Logf("%v", err)
	}
}

func handleSign(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		serve404(w)
		return
	}
	c := appengine.NewContext(r)
	if err := r.ParseForm(); err != nil {
		serveError(c, w, err)
		return
	}
	g := &Greeting{
		Content: r.FormValue("content"),
		Date:    datastore.SecondsToTime(time.Seconds()),
	}
	if u := user.Current(c); u != nil {
		g.Author = u.String()
	}
	if _, err := datastore.Put(c, datastore.NewIncompleteKey("Greeting"), g); err != nil {
		serveError(c, w, err)
		return
	}
	http.Redirect(w, r, "/", http.StatusFound)
}

func init() {
	http.HandleFunc("/", handleMainPage)
	http.HandleFunc("/sign", handleSign)
}
