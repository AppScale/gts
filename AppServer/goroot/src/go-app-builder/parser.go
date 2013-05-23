// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package main

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path"
	"regexp"
	"strconv"
)

// App represents an entire Go App Engine app.
type App struct {
	Files        []*File    // the complete set of source files for this app
	Packages     []*Package // the packages
	RootPackages []*Package // the subset of packages with init functions
}

// Package represents a Go package.
type Package struct {
	ImportPath   string     // the path under which this package may be imported
	Files        []*File    // the set of source files that form this package
	Dependencies []*Package // the packages that this directly depends upon, in no particular order
	HasInit      bool       // whether the package has any init functions
}

func (p *Package) String() string {
	return fmt.Sprintf("%+v", *p)
}

type File struct {
	Name        string   // the file name
	PackageName string   // the package this file declares itself to be
	ImportPaths []string // import paths
	HasInit     bool     // whether the file has an init function
}

func (f *File) String() string {
	return fmt.Sprintf("%+v", *f)
}

// ParseFiles parses the named files, deduces their package structure,
// and returns the dependency DAG as an App.
// Elements of filenames are considered relative to baseDir.
func ParseFiles(baseDir string, filenames []string) (*App, os.Error) {
	app := &App{
		Files: make([]*File, len(filenames)),
	}

	// As we parse the files, group the files by directory,
	// and check that there is only one package per directory.
	pkgFiles := make(map[string][]*File)
	for i, filename := range filenames {
		file, err := parseFile(baseDir, filename)
		if err != nil {
			return nil, err
		}
		app.Files[i] = file
		dirname, _ := path.Split(filename)
		if dirname == "" || dirname == "/" {
			return nil, os.NewError("go files must be in a subdirectory of the app root")
		}
		dirname = dirname[:len(dirname)-1] // strip trailing slash
		if fs := pkgFiles[dirname]; len(fs) > 0 && fs[0].PackageName != file.PackageName {
			return nil, os.NewError("multiple packages found in " + dirname)
		}
		pkgFiles[dirname] = append(pkgFiles[dirname], file)
	}

	// Create Package objects.
	impPathPackages := make(map[string]*Package) // map import path to *Package
	for dirname, files := range pkgFiles {
		p := &Package{
			ImportPath: dirname,
			Files:      files,
		}
		if p.ImportPath == "main" {
			return nil, os.NewError("top-level main package is forbidden")
		}
		for _, f := range files {
			if f.HasInit {
				p.HasInit = true
				break
			}
		}
		app.Packages = append(app.Packages, p)
		if p.HasInit {
			app.RootPackages = append(app.RootPackages, p)
		}
		impPathPackages[p.ImportPath] = p
	}

	// Populate dependency lists.
	for _, p := range app.Packages {
		imports := make(map[string]int) // ImportPath => 1
		for _, f := range p.Files {
			for _, path := range f.ImportPaths {
				imports[path] = 1
			}
		}
		p.Dependencies = make([]*Package, 0, len(imports))
		for path := range imports {
			pkg, ok := impPathPackages[path]
			if !ok {
				// A file declared an import we don't know.
				// It could be a package from the standard library.
				continue
			}
			p.Dependencies = append(p.Dependencies, pkg)
		}
	}

	// Sort topologically.
	if err := topologicalSort(app.Packages); err != nil {
		return nil, err
	}

	return app, nil
}

// isInit returns whether the given function declaration is a true init function.
// Such a function must be called "init", not have a receiver, and have no arguments or return types.
func isInit(f *ast.FuncDecl) bool {
	ft := f.Type
	return f.Name.Name == "init" && f.Recv == nil && ft.Params.NumFields() == 0 && ft.Results.NumFields() == 0
}

// parseFile parses a single Go source file into a *File.
func parseFile(baseDir, filename string) (*File, os.Error) {
	file, err := parser.ParseFile(token.NewFileSet(), path.Join(baseDir, filename), nil, 0)
	if err != nil {
		return nil, err
	}

	// Walk the file's declarations looking for all the imports.
	// Determine whether the file has an init function at the same time.
	var imports []string
	hasInit := false
	for _, decl := range file.Decls {
		if genDecl, ok := decl.(*ast.GenDecl); ok && genDecl.Tok == token.IMPORT {
			for _, spec := range genDecl.Specs {
				importSpec := spec.(*ast.ImportSpec)
				val := string(importSpec.Path.Value)
				path, err := strconv.Unquote(val)
				if err != nil {
					return nil, fmt.Errorf("parser: bad ImportSpec %q: %v", val, err)
				}
				if !checkImport(path) {
					return nil, fmt.Errorf("parser: bad import %q", path)
				}
				imports = append(imports, path)
			}
		}
		if funcDecl, ok := decl.(*ast.FuncDecl); ok {
			if isInit(funcDecl) {
				hasInit = true
			}
		}
	}

	return &File{
		Name:        filename,
		PackageName: file.Name.Name,
		ImportPaths: imports,
		HasInit:     hasInit,
	},
		nil
}

var legalImportPath = regexp.MustCompile(`^[a-zA-Z0-9_\-./]+$`)
var doubleDot = regexp.MustCompile(`[.][.]`)

// checkImport will return whether the provided import path is good.
func checkImport(path string) bool {
	if path == "" {
		return false
	}
	if len(path) > 1024 {
		return false
	}
	if path[0] == '/' || doubleDot.MatchString(path) {
		return false
	}
	if !legalImportPath.MatchString(path) {
		return false
	}
	if path == "syscall" {
		return false
	}
	return true
}

// topologicalSort sorts the given slice of *Package in topological order.
// The ordering is such that X comes before Y if X is a dependency of Y.
// A cyclic dependency graph is signalled by an error being returned.
func topologicalSort(p []*Package) os.Error {
	selected := make(map[*Package]bool, len(p))
	for len(p) > 0 {
		// Sweep the working list and move the packages with no
		// selected dependencies to the front.
		//
		// n acts as both a count of the dependency-free packages,
		// and as the marker for the position of the first package
		// with a dependency that can be swapped to a later position.
		n := 0
	packageLoop:
		for i, pkg := range p {
			for _, dep := range pkg.Dependencies {
				if _, ok := selected[dep]; !ok {
					continue packageLoop
				}
			}
			selected[pkg] = true
			p[i], p[n] = p[n], pkg
			n++
		}
		if n == 0 {
			// No leaves, so there must be a cycle.
			// TODO: Return a summary of the cycle?
			return os.NewError("parser: cyclic dependency graph")
		}
		p = p[n:]
	}
	return nil
}
