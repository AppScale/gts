// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package main

import (
	"bytes"
	"text/template"
)

// MakeMain creates the synthetic main package for a Go App Engine app.
func MakeMain(app *App) (string, error) {
	buf := new(bytes.Buffer)
	if err := mainTemplate.Execute(buf, app); err != nil {
		return "", err
	}
	return buf.String(), nil
}

// MakeExtraImports creates the synthetic extra-imports file for a single package.
func MakeExtraImports(packageName string, extraImports []string) (string, error) {
	buf := new(bytes.Buffer)
	err := extraImportsTemplate.Execute(buf, struct {
		PackageName  string
		ExtraImports []string
	}{
		packageName,
		extraImports,
	})
	if err != nil {
		return "", err
	}
	return buf.String(), nil
}

var mainTemplate = template.Must(template.New("main").Parse(
	`package main

import (
	{{with .InternalPkg}}
	internal {{printf "%q" .}}
	{{else}}
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	{{end}}

	// Top-level app packages
	{{range .RootPackages}}
	_ "{{.ImportPath}}"
	{{end}}
)

func main() {
	{{if .InternalPkg}}
	internal.Main()
	{{else}}
	installHealthChecker()
	port := "8080"
	if s := os.Getenv("PORT"); s != "" {
		port = s
	}
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("http.ListenAndServe: %v", err)
	}
	{{end}}
}

{{if not .InternalPkg}}
func installHealthChecker() {
	const healthPath = "/_ah/health"
	hreq := &http.Request{
		Method: "GET",
		URL: &url.URL{
			Path: healthPath,
		},
	}
	if _, pat := http.DefaultServeMux.Handler(hreq); pat != healthPath {
		http.HandleFunc(healthPath, func(w http.ResponseWriter, r *http.Request) {
			io.WriteString(w, "ok")
		})
	}
}
{{end}}
`))

var extraImportsTemplate = template.Must(template.New("extraImports").Parse(
	`package {{.PackageName}}

import (
	{{range .ExtraImports}}
	_ "{{.}}"
	{{end}}
)
`))
