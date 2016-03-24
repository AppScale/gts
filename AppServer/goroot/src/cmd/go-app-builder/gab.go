// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

/*
go-app-builder is a program that builds Go App Engine apps.

It takes a list of source file names, loads and parses them,
deduces their package structure, creates a synthetic main package,
and finally compiles and links all these pieces.

Files named *_test.go will be ignored.

Usage:
	go-app-builder [options] [file.go ...]
*/
package main

import (
	"crypto/sha1"
	"errors"
	"flag"
	"fmt"
	"go/scanner"
	"io"
	"io/ioutil"
	"log"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	// go15 indicates that we're building using the 1.5 (or later) toolchain, which has
	// different compiler/linker binary names uses different output file
	// extensions.
	// It may be set to true by the toolchain build.sh script.
	// TODO: delete this flag once 1.4 is no longer used.
	go15 = false
	// Root packages are those packages that are part of the app and have init functions.
	// To avoid importing huge numbers of these packages from main directly, a tree of
	// packages is constructed, with the main package as its root, and the root packages
	// as its leaves, so that the main package transitively imports all the root packages.
	// maxRootPackageTreeImportsPerFile is the maximum number of imports that are part of
	// this tree in any single file.
	maxRootPackageTreeImportsPerFile = 20
)

var (
	apiVersion      = flag.String("api_version", "go1", "API version to build for.")
	appBase         = flag.String("app_base", ".", "Path to app root. Command-line filenames are relative to this.")
	arch            = flag.String("arch", defaultArch(), `The Go architecture specifier (e.g. "5", "6", "8").`)
	binaryName      = flag.String("binary_name", "_go_app.bin", "Name of final binary, relative to --work_dir.")
	dynamic         = flag.Bool("dynamic", false, "Create a binary with a dynamic linking header.")
	extraImports    = flag.String("extra_imports", "", "A comma-separated list of extra packages to import.")
	gcFlags         = flag.String("gcflags", "", "Comma-separated list of extra compiler flags.")
	goPath          = flag.String("gopath", os.Getenv("GOPATH"), "Location of extra packages.")
	goRoot          = flag.String("goroot", os.Getenv("GOROOT"), "Root of the Go installation.")
	ldFlags         = flag.String("ldflags", "", "Comma-separated list of extra linker flags.")
	logFile         = flag.String("log_file", "", "If set, a file to write messages to.")
	noBuildFiles    = flag.String("nobuild_files", "", "Regular expression matching files to not build.")
	parallelism     = flag.Int("parallelism", 1, "Maximum number of compiles to run in parallel.")
	pkgDupes        = flag.String("pkg_dupe_whitelist", "", "Comma-separated list of packages that are okay to duplicate.")
	printExtras     = flag.Bool("print_extras", false, "Whether to skip building and just print extra-app files.")
	printExtrasHash = flag.Bool("print_extras_hash", false, "Whether to skip building and just print a hash of the extra-app files.")
	printExtraPkgs  = flag.Bool("print_extra_packages", false, "Whether to skip building and just print extra-app packages.")
	trampoline      = flag.String("trampoline", "", "If set, a binary to invoke tools with.")
	trampolineFlags = flag.String("trampoline_flags", "", "Comma-separated flags to pass to trampoline.")
	unsafe          = flag.Bool("unsafe", false, "Permit unsafe packages.")
	verbose         = flag.Bool("v", false, "Noisy output.")
	vm              = flag.Bool("vm", false, "Whether to build for Managed VMs (implies -unsafe).")
	workDir         = flag.String("work_dir", "/tmp", "Directory to use for intermediate and output files.")
)

func defaultArch() string {
	switch runtime.GOARCH {
	case "386":
		return "8"
	case "amd64":
		return "6"
	case "arm":
		return "5"
	}
	// Default to amd64.
	return "6"
}

func fullArch(c string) string {
	switch c {
	case "5":
		return "arm"
	case "6":
		return "amd64"
	case "8":
		return "386"
	}
	return "amd64"
}

var apiVersionBeta = regexp.MustCompile(`go1.(\d+)beta`)

// Extracts the minor version (x) from an API version string if it is of the form "go1.xbeta"
func betaVersion(apiVersion string) (v int, ok bool) {
	if m := apiVersionBeta.FindStringSubmatch(apiVersion); m != nil {
		v, err := strconv.Atoi(m[1])
		return v, err == nil
	}
	return 0, false
}

func releaseTags(apiVersion string) []string {
	v, ok := betaVersion(apiVersion)
	if !ok {
		v = 4 // we support up to go1.4
	}

	var tags []string
	for i := 1; i <= v; i++ {
		tags = append(tags, "go1."+strconv.Itoa(i))
	}
	return tags
}

func main() {
	flag.Usage = usage
	flag.Parse()
	if flag.NArg() == 0 {
		flag.Usage()
		os.Exit(1)
	}

	if *logFile != "" {
		f, err := os.OpenFile(*logFile, os.O_WRONLY|os.O_APPEND|os.O_CREATE|os.O_SYNC, 0644)
		if err != nil {
			log.Fatalf("go-app-builder: Failed opening log file: %v", err)
		}
		defer f.Close()
		log.SetOutput(f)
	}

	app, err := ParseFiles(*appBase, flag.Args())
	if err != nil {
		if errl, ok := err.(scanner.ErrorList); ok {
			log.Printf("go-app-builder: Failed parsing input (%d error%s)", len(errl), plural(len(errl), "s"))
			for _, err := range errl {
				log.Println(err)
			}
			os.Exit(1)
		}
		log.Fatalf("go-app-builder: Failed parsing input: %v", err)
	}

	if *printExtras {
		printExtraFiles(os.Stdout, app)
		return
	}
	if *printExtrasHash {
		printExtraFilesHash(os.Stdout, app)
		return
	}
	if *printExtraPkgs {
		printExtraPackages(os.Stdout, app)
		return
	}

	gTimer.name = *arch + "g"
	lTimer.name = *arch + "l"

	if go15 {
		gTimer.name = "compile"
		lTimer.name = "link"
	}

	err = buildApp(app)
	log.Printf("go-app-builder: build timing: %v, %v", &gTimer, &lTimer)
	if err != nil {
		log.Fatalf("go-app-builder: %v", err)
	}
}

// Timers that are manipulated in buildApp.
var gTimer, lTimer timer // manipulated in buildApp

func plural(n int, suffix string) string {
	if n == 1 {
		return ""
	}
	return suffix
}

func buildApp(app *App) error {
	newPackages, newRootPackages, err := constructRootPackageTree(app.RootPackages, maxRootPackageTreeImportsPerFile)
	if err != nil {
		return fmt.Errorf("failed creating import tree: %v", err)
	}
	app.Packages = append(app.Packages, newPackages...)
	app.RootPackages = newRootPackages

	defer func() {
		for _, p := range newPackages {
			for _, f := range p.Files {
				os.Remove(f.Name)
			}
		}
	}()
	mainStr, err := MakeMain(app)
	if err != nil {
		return fmt.Errorf("failed creating main: %v", err)
	}
	mainFile := filepath.Join(*workDir, "_go_main.go")
	defer os.Remove(mainFile)
	if err := ioutil.WriteFile(mainFile, []byte(mainStr), 0640); err != nil {
		return fmt.Errorf("failed writing main: %v", err)
	}
	app.Packages = append(app.Packages, &Package{
		ImportPath: "main",
		Files: []*File{
			&File{
				Name:        mainFile,
				PackageName: "main",
				// don't care about ImportPaths
			},
		},
		Dependencies: app.RootPackages,
		Synthetic:    true,
	})

	// Prepare dependency channels.
	for _, pkg := range app.Packages {
		pkg.compiled = make(chan struct{})
	}

	// Common environment for compiler and linker.
	env := []string{
		"GOROOT=" + *goRoot,
		// Use a less efficient, but stricter malloc/free.
		"MALLOC_CHECK_=3",
	}
	// Since we pass -I *workDir and -L *workDir to the compiler and linker respectively,
	// we must also pass -I/-L $GOROOT/pkg/$GOOS_$GOARCH to them before that
	// to ensure that the $GOROOT versions of dupe packages take precedence.
	goRootSearchPath := filepath.Join(*goRoot, "pkg", runtime.GOOS+"_"+runtime.GOARCH)

	// Compile phase.
	compPath := toolPath(*arch + "g")
	if go15 {
		compPath = toolPath("compile")
	}
	c := &compiler{
		app:              app,
		mainFile:         mainFile,
		goRootSearchPath: goRootSearchPath,
		compiler:         compPath,
		gopack:           toolPath("pack"),
		env:              env,
	}
	if *extraImports != "" {
		c.extra = strings.Split(*extraImports, ",")
	}
	defer c.removeFiles()

	// Each package gets its own goroutine that blocks on the completion
	// of its dependencies' compilations.
	errc := make(chan error, 1)
	abortc := make(chan struct{}) // closed if we need to abort the build
	sem := make(chan int, *parallelism)
	var wg sync.WaitGroup
	for i, pkg := range app.Packages {
		wg.Add(1)
		go func(i int, pkg *Package) {
			defer wg.Done()

			// Wait for this package's dependencies to have been compiled.
			for _, dep := range pkg.Dependencies {
				select {
				case <-dep.compiled:
				case <-abortc:
					return
				}
			}
			// Acquire semaphore, and release it when we're done.
			select {
			case sem <- 1:
				defer func() { <-sem }()
			case <-abortc:
				return
			}

			if err := c.compile(i, pkg); err != nil {
				// We only care about the first compile to fail.
				// If this error is the first, tell the others to abort.
				select {
				case errc <- err:
					close(abortc)
				default:
				}
				return
			}

			// Mark this package as being compiled; unblocks dependent packages.
			close(pkg.compiled)
		}(i, pkg)
	}

	// Wait for either a compile error, or for the main package to be compiled.
	wg.Wait()
	select {
	case err := <-errc:
		return err
	default:
	}

	// Link phase.
	linker := toolPath(*arch + "l")
	ext := "." + *arch
	if go15 {
		linker = toolPath("link")
		ext = ".a"
	}
	archiveFile := filepath.Join(*workDir, app.Packages[len(app.Packages)-1].ImportPath) + ext
	binaryFile := filepath.Join(*workDir, *binaryName)
	args := []string{
		linker,
		"-L", goRootSearchPath,
		"-L", *workDir,
		"-o", binaryFile,
	}
	if !*dynamic {
		// force the binary to be statically linked, disable dwarf generation, and strip binary
		args = append(args, "-d", "-w", "-s")
	}
	if !*unsafe && !*vm {
		// reject unsafe code
		args = append(args, "-u")
	}
	if *ldFlags != "" {
		args = append(args, parseToolFlags(*ldFlags)...)
	}
	args = append(args, archiveFile)
	if err := lTimer.run(args, env); err != nil {
		return err
	}

	// Check the final binary. A zero-length file indicates an unexpected linker failure.
	fi, err := os.Stat(binaryFile)
	if err != nil {
		return err
	}
	if fi.Size() == 0 {
		return errors.New("created binary has zero size")
	}

	return nil
}

type compiler struct {
	app              *App
	mainFile         string
	goRootSearchPath string
	compiler         string
	gopack           string
	env              []string
	extra            []string

	mu            sync.Mutex
	filesToRemove []string
}

func (c *compiler) removeLater(filename string) {
	c.mu.Lock()
	c.filesToRemove = append(c.filesToRemove, filename)
	c.mu.Unlock()
}

func (c *compiler) removeFiles() {
	c.mu.Lock()
	for _, filename := range c.filesToRemove {
		os.Remove(filename)
	}
	c.mu.Unlock()
}

func (c *compiler) compile(i int, pkg *Package) error {
	ext := "." + *arch
	if go15 {
		ext = ".a"
	}
	objectFile := filepath.Join(*workDir, pkg.ImportPath) + ext
	objectDir, _ := filepath.Split(objectFile)
	if err := os.MkdirAll(objectDir, 0750); err != nil {
		return fmt.Errorf("failed creating directory %v: %v", objectDir, err)
	}
	args := []string{
		c.compiler,
		"-I", c.goRootSearchPath,
		"-I", *workDir,
		"-o", objectFile,
	}
	if go15 {
		args = append(args, "-pack")
	}
	if !*unsafe && !*vm {
		// reject unsafe code
		args = append(args, "-u")
	}
	if *gcFlags != "" {
		args = append(args, parseToolFlags(*gcFlags)...)
	}
	stripDir := *appBase
	var files []string
	if !pkg.Synthetic {
		// regular package
		base := *appBase
		if pkg.BaseDir != "" {
			base = pkg.BaseDir
		} else {
			// gc at go1.4.1 only accepts one -trimpath flag unfortunately,
			// so copy the source files into workDir for compilation.
			pkgDir := filepath.Join(*workDir, pkg.ImportPath)
			if err := os.MkdirAll(pkgDir, 0750); err != nil {
				return fmt.Errorf("failed creating directory %v: %v", pkgDir, err)
			}
			for _, f := range pkg.Files {
				src := filepath.Join(*appBase, f.Name)
				dst := filepath.Join(*workDir, f.Name)
				if src == dst {
					// The usual cases can have -app_base and -work_dir the same.
					continue
				}
				c.removeLater(dst)
				if err := cp(src, dst); err != nil {
					return err
				}
			}
			base = *workDir
			stripDir = *workDir
		}
		for _, f := range pkg.Files {
			files = append(files, filepath.Join(base, f.Name))
		}
		// Don't generate synthetic extra imports for dupe packages.
		// They won't be linked into the binary anyway,
		// and this avoids triggering a circular import.
		if len(pkg.Files) > 0 && len(c.extra) > 0 && !pkg.Dupe {
			// synthetic extra imports
			extraImportsStr, err := MakeExtraImports(pkg.Files[0].PackageName, c.extra)
			if err != nil {
				return fmt.Errorf("failed creating extra-imports file: %v", err)
			}
			extraImportsFile := filepath.Join(*workDir, fmt.Sprintf("_extra_imports_%d.go", i))
			c.removeLater(extraImportsFile)
			if err := ioutil.WriteFile(extraImportsFile, []byte(extraImportsStr), 0640); err != nil {
				return fmt.Errorf("failed writing extra-imports file: %v", err)
			}
			files = append(files, extraImportsFile)
		}
	} else {
		// synthetic package
		for _, f := range pkg.Files {
			files = append(files, f.Name)
		}
		stripDir = *workDir
	}

	// Add the right -trimpath flag.
	stripDir, _ = filepath.Abs(stripDir) // assume os.Getwd doesn't fail
	args = append(args, "-trimpath", stripDir)

	args = append(args, files...)
	c.removeLater(objectFile)
	if err := gTimer.run(args, c.env); err != nil {
		return err
	}

	return nil
}

func cp(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return fmt.Errorf("os.Open: %v", err)
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return fmt.Errorf("os.Create: %v", err)
	}
	if _, err := io.Copy(out, in); err != nil {
		out.Close()
		return fmt.Errorf("io.Copy: %v", err)
	}
	return out.Close()
}

type timer struct {
	name string

	mu    sync.Mutex
	n     int
	total time.Duration
}

func (t *timer) run(args, env []string) error {
	start := time.Now()
	err := run(args, env)

	t.mu.Lock()
	t.n++
	t.total += time.Since(start)
	t.mu.Unlock()

	return err
}

func (t *timer) String() string {
	t.mu.Lock()
	defer t.mu.Unlock()

	// Display total only to millisecond resolution.
	tot := t.total - (t.total % time.Millisecond)
	return fmt.Sprintf("%d×%s (%v total)", t.n, t.name, tot)
}

func printExtraFiles(w io.Writer, app *App) {
	for _, pkg := range app.Packages {
		if pkg.BaseDir == "" {
			continue // app package
		}
		for _, f := range pkg.Files {
			// The app-relative path should always use forward slash.
			// The code in dev_appserver only deals with those paths.
			rel := path.Join(pkg.ImportPath, f.Name)
			dst := filepath.Join(pkg.BaseDir, f.Name)
			fmt.Fprintf(w, "%s|%s\n", rel, dst)
		}
	}
}

func printExtraFilesHash(w io.Writer, app *App) {
	// Compute a hash of the extra files information, namely the name and mtime
	// of all the extra files. This is sufficient information for the dev_appserver
	// to be able to decide whether a rebuild is necessary based on GOPATH changes.
	h := sha1.New()
	sort.Sort(byImportPath(app.Packages)) // be deterministic
	for _, pkg := range app.Packages {
		if pkg.BaseDir == "" {
			continue // app package
		}
		sort.Sort(byFileName(pkg.Files)) // be deterministic
		for _, f := range pkg.Files {
			dst := filepath.Join(pkg.BaseDir, f.Name)
			fi, err := os.Stat(dst)
			if err != nil {
				log.Fatalf("go-app-builder: os.Stat(%q): %v", dst, err)
			}
			fmt.Fprintf(h, "%s: %v\n", dst, fi.ModTime())
		}
	}
	fmt.Fprintf(w, "%x", h.Sum(nil))
}

func printExtraPackages(w io.Writer, app *App) {
	// Print all the packages that aren't in the app that look like they aren't in the standard library.
	// This is a heuristic approach, but should be good enough for its intended use,
	// namely finding the packages we need to fetch.
	appPkgs, extPkgs := make(map[string]bool), make(map[string]bool)
	for _, pkg := range app.Packages {
		appPkgs[pkg.ImportPath] = true
	}
	for _, pkg := range app.Packages {
		// Look at all the imports for all packages (even ones we get from GOPATH).
		for _, f := range pkg.Files {
			for _, imp := range f.ImportPaths {
				if appPkgs[imp] {
					// The imported path is in the app, or in GOPATH.
					continue
				}
				// Heuristic: If an import path has no dot, assume it is in the standard library.
				if !strings.Contains(imp, ".") {
					continue
				}
				extPkgs[imp] = true
			}
		}
	}

	imps := make([]string, 0, len(extPkgs))
	for imp := range extPkgs {
		imps = append(imps, imp)
	}
	sort.Strings(imps)
	for _, imp := range imps {
		fmt.Fprintln(w, imp)
	}
}

func toolPath(x string) string {
	ext := ""
	if runtime.GOOS == "windows" {
		ext = ".exe"
	}
	return filepath.Join(*goRoot, "pkg", "tool", runtime.GOOS+"_"+fullArch(*arch), x+ext)
}

func usage() {
	fmt.Fprintf(os.Stderr, "Usage:  %s [options] <foo.go> ...\n", os.Args[0])
	flag.PrintDefaults()
}

func run(args []string, env []string) error {
	if *verbose {
		log.Printf("run %v", args)
	}
	tool := filepath.Base(args[0])
	if *trampoline != "" {
		// Add trampoline binary, its flags, and -- to the start.
		newArgs := []string{*trampoline}
		if *trampolineFlags != "" {
			newArgs = append(newArgs, strings.Split(*trampolineFlags, ",")...)
		}
		newArgs = append(newArgs, "--")
		args = append(newArgs, args...)
	}
	cmd := &exec.Cmd{
		Path:   args[0],
		Args:   args,
		Env:    env,
		Stdout: os.Stdout,
		Stderr: os.Stderr,
	}
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed running %v: %v", tool, err)
	}
	return nil
}
