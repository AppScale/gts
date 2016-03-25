// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package main

import (
	"bytes"
	"errors"
	"fmt"
	"go/ast"
	"go/build"
	"go/parser"
	"go/scanner"
	"go/token"
	"io/ioutil"
	"log"
	"math/rand"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"appengine_internal/golang.org/x/tools/cmd/vet/whitelist"
)

// App represents an entire Go App Engine app.
type App struct {
	Files        []*File    // the complete set of source files for this app
	Packages     []*Package // the packages
	RootPackages []*Package // the subset of packages with init functions

	PackageIndex map[string]*Package // index from import path to package object

	InternalPkg string // the name of the internal package
}

// Package represents a Go package.
type Package struct {
	ImportPath   string     // the path under which this package may be imported
	Files        []*File    // the set of source files that form this package
	BaseDir      string     // what the file names are relative to, if outside app
	Dependencies []*Package // the packages that this directly depends upon, in no particular order
	HasInit      bool       // whether the package has any init functions
	HasMain      bool       // whether the file has internal.Main
	Dupe         bool       // whether the package is a duplicate
	Synthetic    bool       // whether the package is a synthetic main or import tree package

	compiled chan struct{} // closed when the package has finished compiling
}

func (p *Package) String() string {
	return fmt.Sprintf("%+v", *p)
}

// Implement sort.Interface for []*Package.
type byImportPath []*Package

func (s byImportPath) Len() int           { return len(s) }
func (s byImportPath) Less(i, j int) bool { return s[i].ImportPath < s[j].ImportPath }
func (s byImportPath) Swap(i, j int)      { s[i], s[j] = s[j], s[i] }

type File struct {
	Name        string   // the file name
	PackageName string   // the package this file declares itself to be
	ImportPaths []string // import paths
	HasInit     bool     // whether the file has an init function
	HasMain     bool     // whether the file has internal.Main
}

func (f *File) String() string {
	return fmt.Sprintf("%+v", *f)
}

// Implement sort.Interface for []*File.
type byFileName []*File

func (s byFileName) Len() int           { return len(s) }
func (s byFileName) Less(i, j int) bool { return s[i].Name < s[j].Name }
func (s byFileName) Swap(i, j int)      { s[i], s[j] = s[j], s[i] }

// vfs is a tiny VFS overlay that exposes a subset of files in a tree.
type vfs struct {
	baseDir   string
	filenames []string
}

func (v vfs) readDir(dir string) (fis []os.FileInfo, err error) {
	dir = filepath.Clean(dir)
	for _, f := range v.filenames {
		f = filepath.Join(v.baseDir, f)
		if filepath.Dir(f) == dir {
			fi, err := os.Stat(f)
			if err != nil {
				return nil, err
			}
			fis = append(fis, fi)
		}
	}
	return fis, nil
}

func buildContext(goPath string) *build.Context {
	ctxt := &build.Context{
		GOARCH:      build.Default.GOARCH,
		GOOS:        build.Default.GOOS,
		GOROOT:      *goRoot,
		GOPATH:      goPath,
		ReleaseTags: releaseTags(*apiVersion),
		Compiler:    "gc",
	}
	if *vm {
		ctxt.BuildTags = []string{"appenginevm"}
	} else {
		ctxt.BuildTags = []string{"appengine"}
	}
	return ctxt
}

// ParseFiles parses the named files, deduces their package structure,
// and returns the dependency DAG as an App.
// Elements of filenames are considered relative to baseDir.
func ParseFiles(baseDir string, filenames []string) (*App, error) {
	app := &App{
		PackageIndex: make(map[string]*Package),
	}
	if !*vm {
		app.InternalPkg = "appengine_internal"
	}
	pkgFiles := make(map[string][]*File) // app package name => its files

	vfs := vfs{baseDir, filenames}

	ctxt := buildContext(baseDir)
	ctxt.HasSubdir = func(root, dir string) (rel string, ok bool) {
		// Override the default HasSubdir, which evaluates symlinks.
		const sep = string(filepath.Separator)
		root = filepath.Clean(root)
		if !strings.HasSuffix(root, sep) {
			root += sep
		}
		dir = filepath.Clean(dir)
		if !strings.HasPrefix(dir, root) {
			return "", false
		}
		return dir[len(root):], true
	}
	ctxt.ReadDir = func(dir string) ([]os.FileInfo, error) {
		return vfs.readDir(dir)
	}

	dirs := make(map[string]bool)
	for _, f := range filenames {
		dir := filepath.Dir(f) // "." for top-level files
		if dir == "" || dir == string(filepath.Separator) {
			return nil, fmt.Errorf("bad filename %q", f)
		}
		dirs[dir] = true
	}
	for dir := range dirs {
		pkg, err := ctxt.ImportDir(filepath.Join(baseDir, dir), 0)
		if _, ok := err.(*build.NoGoError); ok {
			// There were .go files, but they were all excluded (e.g. by "// +build ignore").
			continue
		}
		if err != nil {
			return nil, fmt.Errorf("failed parsing dir %v: %v", dir, err)
		}

		for _, f := range pkg.GoFiles {
			filename := filepath.Join(dir, f)
			file, err := parseFile(baseDir, filename)
			if err != nil {
				return nil, err
			}
			app.Files = append(app.Files, file)
			pkgFiles[dir] = append(pkgFiles[dir], file)
		}
	}

	allowedDupes := make(map[string]bool)
	if *pkgDupes != "" {
		for _, pkg := range strings.Split(*pkgDupes, ",") {
			allowedDupes[pkg] = true
		}
	}

	// Create Package objects.
	for dirname, files := range pkgFiles {
		imp := filepath.ToSlash(dirname)
		if dirname == "." {
			// top-level package; generate random package name
			rng := rand.New(rand.NewSource(time.Now().Unix()))
			imp = fmt.Sprintf("main%05d", rng.Intn(1e5))
		}

		p := &Package{
			ImportPath: imp,
			Files:      files,
		}
		if p.ImportPath == "main" {
			return nil, errors.New("top-level main package is forbidden")
		}
		if isStandardPackage(p.ImportPath) {
			if !allowedDupes[p.ImportPath] {
				return nil, fmt.Errorf("package %q has the same name as a standard package", p.ImportPath)
			}
			p.Dupe = true
		}
		for _, f := range files {
			if f.HasInit {
				p.HasInit = true
			}
			if f.HasMain {
				p.HasMain = true
			}
		}
		app.Packages = append(app.Packages, p)
		if p.HasInit || *vm {
			app.RootPackages = append(app.RootPackages, p)
		}
		app.PackageIndex[p.ImportPath] = p
	}

	if *goPath != "" {
		var re *regexp.Regexp
		var err error
		if *noBuildFiles != "" {
			re, err = regexp.Compile(*noBuildFiles)
			if err != nil {
				return nil, fmt.Errorf("bad -nobuild_files: %v", err)
			}
		}
		fs := appFilesInGOPATH(baseDir, *goPath, app)
		if err := addFromGOPATH(app, re, fs); err != nil {
			return nil, err
		}
	}

	if app.InternalPkg == "" {
		var mainPkg *Package
		for _, pkg := range app.Packages {
			if !pkg.HasMain {
				continue
			}
			if mainPkg != nil {
				return nil, fmt.Errorf("duplicate internal.Main in %q and %q", mainPkg.ImportPath, pkg.ImportPath)
			}
			mainPkg = pkg
		}
		if mainPkg != nil {
			app.InternalPkg = mainPkg.ImportPath
		}
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
			pkg, ok := app.PackageIndex[path]
			if !ok {
				// A file declared an import we don't know.
				// It could be a package from the standard library.
				if findInternal(path) {
					return nil, fmt.Errorf("package %q cannot import internal package %q", p.ImportPath, path)
				}
				continue
			}
			p.Dependencies = append(p.Dependencies, pkg)
		}
		sort.Sort(byImportPath(p.Dependencies))
	}

	// Sort topologically.
	if err := topologicalSort(app.Packages); err != nil {
		return nil, err
	}

	return app, nil
}

// appFilesInGOPATH returns a set of app files that are in the GOPATH.
// The constructed set of filenames is relative to the GOPATH's 'src' dir.
// If any of these files appear in a package's source files, an error
// is generated and the build fails.
func appFilesInGOPATH(baseDir, goPath string, app *App) map[string]bool {
	var gopathBase string
	for _, p := range filepath.SplitList(goPath) {
		prefix := filepath.Join(p, "src") + string(filepath.Separator)
		if strings.HasPrefix(baseDir, prefix) {
			gopathBase = baseDir[len(prefix):] // GOPATH-relative base of app's files
			break
		}
	}
	if gopathBase == "" {
		return nil // app not in a GOPATH
	}

	r := make(map[string]bool)
	for _, f := range app.Files {
		r[filepath.Join(gopathBase, f.Name)] = true
	}
	return r
}

func validatePkgPaths(pkg *build.Package, appFilesInGOPATH map[string]bool) error {
	for _, f := range pkg.GoFiles {
		n := filepath.Join(pkg.ImportPath, f)
		if _, ok := appFilesInGOPATH[n]; ok {
			return fmt.Errorf("app file %s conflicts with same file imported from GOPATH", f)
		}
	}
	return nil
}

// addFromGOPATH adds packages from GOPATH that are needed by the app.
func addFromGOPATH(app *App, noBuild *regexp.Regexp, appFilesInGOPATH map[string]bool) error {
	warned := make(map[string]bool)
	for i := 0; i < len(app.Packages); i++ { // app.Packages is grown during this loop
		p := app.Packages[i]
		for _, f := range p.Files {
			for _, path := range f.ImportPaths {
				// Check for invalid imports.
				if !checkImport(path) {
					return fmt.Errorf("parser: bad import %q in %s from GOPATH", path, f.Name)
				}
				if isStandardPackage(path) || app.PackageIndex[path] != nil {
					continue
				}
				pkg, err := gopathPackage(path)
				if err != nil {
					if !warned[path] {
						log.Printf("Can't find package %q in $GOPATH: %v", path, err)
						warned[path] = true
					}
					continue
				}
				if err := validatePkgPaths(pkg, appFilesInGOPATH); err != nil {
					return err
				}

				files := make([]*File, 0, len(pkg.GoFiles))
				pkgHasMain := false
				for _, f := range pkg.GoFiles {
					if noBuild != nil && noBuild.MatchString(filepath.Join(path, f)) {
						continue
					}
					hasMain := false
					if *vm && pkg.Name == "internal" {
						// See if this file has internal.Main.
						// This check duplicates conditions in readFile
						// as an optimisation to avoid parsing lots of code
						// that can't have internal.Main.
						var err error
						_, _, hasMain, err = readFile(pkg.Dir, f)
						if err != nil {
							return err
						}
					}
					files = append(files, &File{
						Name:        f,
						PackageName: pkg.Name,
						// NOTE: This is inaccurate, but it is sufficient to
						// record all the package imports for each file.
						ImportPaths: pkg.Imports,
						HasMain:     hasMain,
					})
					if hasMain {
						pkgHasMain = true
					}
				}
				if len(files) == 0 {
					return fmt.Errorf("package %s required, but all its files were excluded by nobuild_files", path)
				}
				p := &Package{
					ImportPath: path,
					Files:      files,
					BaseDir:    pkg.Dir,
					HasMain:    pkgHasMain,
				}
				app.Packages = append(app.Packages, p)
				app.PackageIndex[path] = p
			}
		}
	}
	return nil
}

// isInit returns whether the given function declaration is a true init function.
// Such a function must be called "init", not have a receiver, and have no arguments or return types.
func isInit(f *ast.FuncDecl) bool { return isNiladic(f, "init") }

// isMain returns whether the given function declaration is a Main function.
// Such a function must be called "Main", not have a receiver, and have no arguments or return types.
func isMain(f *ast.FuncDecl) bool { return isNiladic(f, "Main") }

func isNiladic(f *ast.FuncDecl, name string) bool {
	ft := f.Type
	return f.Name.Name == name && f.Recv == nil && ft.Params.NumFields() == 0 && ft.Results.NumFields() == 0
}

// If this magic string occurs in a file with a niladic Main,
// and the file's package is "internal",
// and -internal_pkg is empty,
// then the file's package is used for internal.Main.
const magicInternalMain = `The gophers party all night; the rabbits provide the beats.`

func readFile(baseDir, filename string) (file *ast.File, fset *token.FileSet, hasMain bool, err error) {
	fullName := filepath.Join(baseDir, filename)
	var src []byte
	src, err = ioutil.ReadFile(fullName)
	if err != nil {
		return
	}
	fset = token.NewFileSet()
	file, err = parser.ParseFile(fset, fullName, src, 0)
	if *vm && file.Name.Name == "internal" {
		for _, decl := range file.Decls {
			funcDecl, ok := decl.(*ast.FuncDecl)
			if !ok {
				continue
			}
			if !isMain(funcDecl) {
				continue
			}
			if !bytes.Contains(src, []byte(magicInternalMain)) {
				continue
			}
			hasMain = true
			break
		}
	}
	return
}

// parseFile parses a single Go source file into a *File.
func parseFile(baseDir, filename string) (*File, error) {
	file, fset, hasMain, err := readFile(baseDir, filename)
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
					return nil, fmt.Errorf("parser: bad import %q in %s", path, filename)
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

	// Check for unkeyed struct literals from the standard package library.
	ch := newCompLitChecker(fset)
	ast.Walk(ch, file)
	if len(ch.errors) > 0 {
		return nil, ch.errors
	}

	return &File{
		Name:        filename,
		PackageName: file.Name.Name,
		ImportPaths: imports,
		HasInit:     hasInit,
		HasMain:     hasMain,
	}, nil
}

var legalImportPath = regexp.MustCompile(`^[a-zA-Z0-9_\-./~+]+$`)

// checkImport will return whether the provided import path is good.
func checkImport(path string) bool {
	if path == "" {
		return false
	}
	if len(path) > 1024 {
		return false
	}
	if filepath.IsAbs(path) || strings.Contains(path, "..") {
		return false
	}
	if !legalImportPath.MatchString(path) {
		return false
	}
	if path == "syscall" || path == "unsafe" {
		// VM apps may import "syscall" and "unsafe"
		return *vm
	}
	return true
}

type compLitChecker struct {
	fset    *token.FileSet
	imports map[string]string // Local name => import path; only standard packages.
	errors  scanner.ErrorList // accumulated errors
}

func newCompLitChecker(fset *token.FileSet) *compLitChecker {
	return &compLitChecker{
		fset:    fset,
		imports: make(map[string]string),
	}
}

func (c *compLitChecker) errorf(node ast.Node, format string, a ...interface{}) {
	c.errors = append(c.errors, &scanner.Error{
		Pos: c.fset.Position(node.Pos()),
		Msg: fmt.Sprintf(format, a...),
	})
}

func (c *compLitChecker) Visit(node ast.Node) ast.Visitor {
	if imp, ok := node.(*ast.ImportSpec); ok {
		pth, _ := strconv.Unquote(imp.Path.Value)
		if !isStandardPackage(pth) {
			return c
		}
		if imp.Name != nil {
			id := imp.Name.Name
			if id == "." {
				return c
			}
			c.imports[id] = pth
		} else {
			// All standard packages have their last path component as their package name.
			c.imports[filepath.Base(pth)] = pth
		}
		return c
	}

	lit, ok := node.(*ast.CompositeLit)
	if !ok {
		return c
	}
	sel, ok := lit.Type.(*ast.SelectorExpr)
	if !ok {
		return c
	}
	id, ok := sel.X.(*ast.Ident)
	if !ok {
		return c
	}
	pth, ok := c.imports[id.Name]
	if !ok {
		// This must be pkg.T for a package in the app.
		return c
	}

	// Check exception list.
	if whitelist.UnkeyedLiteral[pth+"."+sel.Sel.Name] {
		return c
	}

	allKeys := true
	for _, elt := range lit.Elts {
		_, ok := elt.(*ast.KeyValueExpr)
		allKeys = allKeys && ok
	}
	if !allKeys {
		c.errorf(lit, "composite struct literal %v.%v with unkeyed fields", pth, sel.Sel)
	}

	return c
}

// Cache of standard package status.
var stdPackageCache = map[string]bool{
	// There's no unsafe.a, but "unsafe" is a standard package.
	// Mention it explicitly here so we avoid a useless warning.
	"unsafe": true,
}

// isStandardPackage reports whether import path s is a standard package.
func isStandardPackage(s string) bool {
	if std, ok := stdPackageCache[s]; ok {
		return std
	}

	// Don't consider any import path containing a dot to be a standard package.
	if strings.Contains(s, ".") {
		stdPackageCache[s] = false
		return false
	}

	ctxt := buildContext("")
	pkg, err := ctxt.Import(s, "/nowhere", build.FindOnly|build.AllowBinary)
	if err != nil {
		stdPackageCache[s] = false
		return false
	}
	std := pkg.ImportPath != ""
	stdPackageCache[s] = std
	return std
}

// gopathPackage imports information about a package in GOPATH.
func gopathPackage(s string) (*build.Package, error) {
	ctxt := buildContext(*goPath)
	// Don't use FindOnly or AllowBinary because we want import information
	// and we require the source files.
	return ctxt.Import(s, "/nowhere", 0)
}

// topologicalSort sorts the given slice of *Package in topological order.
// The ordering is such that X comes before Y if X is a dependency of Y.
// A cyclic dependency graph is signalled by an error being returned.
func topologicalSort(p []*Package) error {
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
				if !selected[dep] {
					continue packageLoop
				}
			}
			selected[pkg] = true
			p[i], p[n] = p[n], pkg
			n++
		}
		if n == 0 {
			// No leaves, so there must be a cycle.
			cycle := findCycle(p)
			paths := make([]string, len(cycle)+1)
			for i, pkg := range cycle {
				paths[i] = pkg.ImportPath
			}
			paths[len(cycle)] = cycle[0].ImportPath // duplicate last package
			return fmt.Errorf("parser: cyclic dependency graph: %s", strings.Join(paths, " -> "))
		}
		p = p[n:]
	}
	return nil
}

// findCycle finds a cycle in pkgs.
// It assumes that a cycle exists.
func findCycle(pkgs []*Package) []*Package {
	pkgMap := make(map[*Package]bool, len(pkgs)) // quick index of packages
	var min *Package
	for _, pkg := range pkgs {
		pkgMap[pkg] = true
		if min == nil || pkg.ImportPath < min.ImportPath {
			min = pkg
		}
	}

	// Every element of pkgs is a member of a cycle,
	// so find a cycle starting with the first one lexically.
	cycle := []*Package{min}
	seen := map[*Package]int{min: 0} // map of package to index in cycle
	for {
		last := cycle[len(cycle)-1]
		for _, dep := range last.Dependencies {
			if i, ok := seen[dep]; ok {
				// Cycle found.
				return cycle[i:]
			}
		}
		// None of the dependencies of last are in cycle, so pick one of
		// its dependencies (that we know is in a cycle) to add to cycle.
		// We are always able to find such a dependency, because
		// otherwise last would not be a member of a cycle.
		var dep *Package
		for _, d := range last.Dependencies {
			if pkgMap[d] {
				dep = d
				break
			}
		}

		seen[dep] = len(cycle)
		cycle = append(cycle, dep)
	}
}

// findInternal returns whether the pkg path contains an "internal" path element.
func findInternal(path string) bool {
	return strings.HasSuffix(path, "/internal") ||
		strings.HasPrefix(path, "internal/") ||
		strings.Contains(path, "/internal/") ||
		path == "internal"
}

// constructRootPackageTree takes an unbounded-size list of root packages that
// need to be imported by the synthetic main package, and constructs a new list
// of root packages of size bounded by the given limit, such that importing
// those packages will transitively import all the input root packages.  This
// reduces the problem of a single compilation having a very large number of
// direct imports.
//
// Constructs a tree of new synthetic packages as necessary, such that none of
// those packages import more than the given limit of packages.  Source files
// are created for them.
//
// For example, with limit=2 and 5 root packages, it changes this:
//
// main->[a, b, c, d, e]
//
// to this:
//
// t1->[a, b], t2->[c, d], t3->[e, t1], main->[t2, t3]
//
// It returns a slice of the additional packages created, and a new slice of the
// root packages that the main package should import (which could include some
// packages from the original list in rootPackages.)
func constructRootPackageTree(rootPackages []*Package, limit int) (newPackages []*Package, newRootPackages []*Package, err error) {
	var (
		files []string
		count int
	)
	defer func() {
		if err != nil {
			for _, f := range files {
				os.Remove(f)
			}
		}
	}()
	newRootPackages = make([]*Package, len(rootPackages))
	copy(newRootPackages, rootPackages)
	for len(newRootPackages) > limit {
		// Modify newPackages and newRootPackages to add an additional tree node package.
		count++
		packageName := fmt.Sprintf("_import_tree%d", count)
		dir := filepath.Join(*workDir, packageName)
		filename := fmt.Sprintf("_go_main_tree%d.go", count)
		filePath := filepath.Join(dir, filename)
		file := &File{
			Name:        filePath,
			PackageName: packageName,
		}
		p := &Package{
			ImportPath: packageName,
			Files:      []*File{file},
			Synthetic:  true,
		}
		newPackages = append(newPackages, p)
		p.Dependencies, newRootPackages = newRootPackages[0:limit], append(newRootPackages[limit:], p)

		// Write the source file for the new package.
		var depPackageNames []string
		for _, d := range p.Dependencies {
			depPackageNames = append(depPackageNames, d.ImportPath)
		}
		nodeStr, err := MakeExtraImports(packageName, depPackageNames)
		if err != nil {
			return nil, nil, err
		}
		if err = os.MkdirAll(dir, 0750); err != nil {
			return nil, nil, err
		}
		files = append(files, filePath)
		if err = ioutil.WriteFile(filePath, []byte(nodeStr), 0640); err != nil {
			return nil, nil, err
		}
	}
	return newPackages, newRootPackages, nil
}

func init() {
	// Add some App Engine-specific entries to the unkeyed literal whitelist.
	whitelist.UnkeyedLiteral["appengine/datastore.PropertyList"] = true
	whitelist.UnkeyedLiteral["appengine.MultiError"] = true
}
