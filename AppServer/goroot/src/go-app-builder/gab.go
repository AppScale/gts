// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

/*
go-app-builder is a program that builds Go App Engine apps.

It takes a list of source file names, loads and parses them,
deduces their package structure, creates a synthetic main package,
and finally compiles and links all these pieces.

Usage:
	go-app-builder [options] [file.go ...]
*/
package main

import (
	"exec"
	"flag"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path"
	"strings"
)

var (
	appBase      = flag.String("app_base", ".", "Path to app root. Command-line filenames are relative to this.")
	arch         = flag.String("arch", defaultArch(), `The Go architecture specifier (e.g. "5", "6", "8").`)
	binaryName   = flag.String("binary_name", "_go_app.bin", "Name of final binary, relative to --work_dir.")
	dynamic      = flag.Bool("dynamic", false, "Create a binary with a dynamic linking header.")
	extraImports = flag.String("extra_imports", "", "A comma-separated list of extra packages to import.")
	goRoot       = flag.String("goroot", os.Getenv("GOROOT"), "Root of the Go installation.")
	unsafe       = flag.Bool("unsafe", false, "Permit unsafe packages.")
	verbose      = flag.Bool("v", false, "Noisy output.")
	workDir      = flag.String("work_dir", "/tmp", "Directory to use for intermediate and output files.")
)

func defaultArch() string {
	switch os.Getenv("GOARCH") {
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

func main() {
	flag.Usage = usage
	flag.Parse()
	if flag.NArg() == 0 {
		flag.Usage()
		os.Exit(1)
	}

	app, err := ParseFiles(*appBase, flag.Args())
	if err != nil {
		log.Fatalf("go-app-builder: Failed parsing input: %v", err)
	}

	if err := build(app); err != nil {
		log.Fatalf("go-app-builder: Failed building app: %v", err)
	}
}

func build(app *App) os.Error {
	var extra []string
	if *extraImports != "" {
		extra = strings.Split(*extraImports, ",", -1)
	}
	mainStr, err := MakeMain(app, extra)
	if err != nil {
		return fmt.Errorf("failed creating main: %v", err)
	}
	const mainName = "_go_main.go"
	mainFile := path.Join(*workDir, mainName)
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
	})

	// Common environment for compiler and linker.
	env := []string{
		"GOROOT=" + *goRoot,
	}

	// Compile phase.
	compiler := path.Join(*goRoot, "bin", *arch+"g")
	gopack := path.Join(*goRoot, "bin", "gopack")
	for i, pkg := range app.Packages {
		objectFile := path.Join(*workDir, pkg.ImportPath) + "." + *arch
		objectDir, _ := path.Split(objectFile)
		if err := os.MkdirAll(objectDir, 0750); err != nil {
			return fmt.Errorf("failed creating directory %v: %v", objectDir, err)
		}
		args := []string{
			compiler,
			"-I", *workDir,
			"-o", objectFile,
		}
		if !*unsafe {
			// reject unsafe code
			args = append(args, "-u")
		}
		if i < len(app.Packages)-1 {
			// regular package
			for _, f := range pkg.Files {
				args = append(args, path.Join(*appBase, f.Name))
			}
		} else {
			// synthetic main package
			args = append(args, mainFile)
		}
		defer os.Remove(objectFile)
		if err := run(args, env); err != nil {
			return err
		}

		// Turn the object file into an archive file, stripped of file path information.
		// The path we strip depends on whether this object file is based on user code
		// or the synthetic main code.
		archiveFile := path.Join(*workDir, pkg.ImportPath) + ".a"
		srcDir := *appBase
		if i == len(app.Packages)-1 {
			srcDir = *workDir
		}
		args = []string{
			gopack,
			"grcP", srcDir,
			archiveFile,
			objectFile,
		}
		defer os.Remove(archiveFile)
		if err := run(args, env); err != nil {
			return err
		}
	}

	// Link phase.
	linker := path.Join(*goRoot, "bin", *arch+"l")
	archiveFile := path.Join(*workDir, app.Packages[len(app.Packages)-1].ImportPath) + ".a"
	binaryFile := path.Join(*workDir, *binaryName)
	args := []string{
		linker,
		"-L", *workDir,
		"-o", binaryFile,
	}
	if !*dynamic {
		// force the binary to be statically linked
		args = append(args, "-d")
	}
	if !*unsafe {
		// reject unsafe code
		args = append(args, "-u")
	}
	args = append(args, archiveFile)
	if err := run(args, env); err != nil {
		return err
	}

	// Check the final binary. A zero-length file indicates an unexpected linker failure.
	fi, err := os.Stat(binaryFile)
	if err != nil {
		return err
	}
	if fi.Size == 0 {
		return os.NewError("created binary has zero size")
	}

	return nil
}

func usage() {
	fmt.Fprintf(os.Stderr, "Usage:  %s [options] <foo.go> ...\n", os.Args[0])
	flag.PrintDefaults()
}

func run(args []string, env []string) os.Error {
	if *verbose {
		log.Printf("run %v", args)
	}
	tool := path.Base(args[0])
	cmd, err := exec.Run(args[0], args, env, "", exec.DevNull, exec.PassThrough, exec.PassThrough)
	if err != nil {
		return fmt.Errorf("failed running %v: %v", tool, err)
	}
	w, err := cmd.Wait(0)
	if err != nil {
		return fmt.Errorf("failed while waiting for %v to finish: %v", tool, err)
	}
	if rc := w.ExitStatus(); rc != 0 {
		return fmt.Errorf("%v exited with status %d", tool, rc)
	}
	return nil
}
