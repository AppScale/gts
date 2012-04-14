// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package main

import (
	"bytes"
	"os"
	"template"
)

// MakeMain creates the synthetic main package for a Go App Engine app.
func MakeMain(app *App, extraImports []string) (string, os.Error) {
	buf := new(bytes.Buffer)
	data := &templateData{
		App:          app,
		ExtraImports: extraImports,
	}
	if err := mainTemplate.Execute(buf, data); err != nil {
		return "", err
	}
	return buf.String(), nil
}

var mainTemplate *template.Template

func init() {
	mainTemplate = template.New(template.FormatterMap{})
	mainTemplate.SetDelims("{{", "}}")
	if err := mainTemplate.Parse(rawTemplate); err != nil {
		panic("synthesizer: bad template: " + err.String())
	}
}

type templateData struct {
	App          *App
	ExtraImports []string
}

const rawTemplate = `package main

import (
	"appengine_internal"
	{{.repeated section ExtraImports}}
	_ "{{@}}"
	{{.end}}

	// Top-level app packages
	{{.repeated section App.RootPackages}}
	_ "{{ImportPath}}"
	{{.end}}
)

func main() {
	appengine_internal.Main()
}
`
