// Programmer: Chris Bunch
// The neptune package provides and interface to the Neptune programming
// language, a domain specific language that simplifies the configuration
// and deployment of high performance computing applications to cloud
// platforms.
// Learn more about Neptune at http://neptune-lang.org

package neptune

import (
	"bytes"
	"crypto/rand"
	"encoding/binary"
	"exec"
	"fmt"
	"io"
	"os"
	"strings"

	"appengine"
	"appengine/user"
)

const (
	NEPTUNE_API     = "neptune_api"
	NOT_ENABLED_MSG = "this user cannot call the neptune api"
)

// right now the neptune executable is located on all machines, so
// it is always available. this function is here just because in the
// future this assumption may not necessarily be valid
func CanRunJobs() bool {
	return true
}

func RunJob(c appengine.Context, fileLocation string) map[string]string {
	result := map[string]string{
		"out": "",
		"err": ""}

	if !user.IsCurrentUserCapable(c, NEPTUNE_API) {
		result["err"] = NOT_ENABLED_MSG
		return result
	}

	if _, err := os.Stat(fileLocation); err != nil {
		fmt.Printf("user requested to run a job on file %v, which doesn't exist\n", fileLocation)
		result["err"] = "file not found"
		return result
	}

	// 'which neptune' returns with a newline on the end, so chop it off
	neptuneCommand := strings.TrimSpace(runShellCommand([]string{"/usr/bin/which", "neptune"})["out"])
	return runShellCommand([]string{neptuneCommand, fileLocation})
}

func runShellCommand(argv []string) map[string]string {
	result := map[string]string{
		"out": "",
		"err": ""}

	app := argv[0]
	home := fmt.Sprintf("HOME=%v", os.Getenv("HOME"))
	path := fmt.Sprintf("PATH=%v", os.Getenv("PATH"))
	env := []string{home, path}

	cmd, err := exec.Run(app, argv, env, "", exec.DevNull, exec.Pipe, exec.Pipe)

	if err != nil {
		fmt.Fprintln(os.Stderr, err.String())
		result["err"] = err.String()
		return result
	}

	var b1 bytes.Buffer
	io.Copy(&b1, cmd.Stdout)
	fmt.Println(b1.String())
	result["out"] = b1.String()

	var b2 bytes.Buffer
	io.Copy(&b2, cmd.Stderr)
	fmt.Println(b2.String())
	result["err"] = b2.String()

	cmd.Close()

	return result
}

func WriteJobParams(c appengine.Context, params map[string]string) (string, string, string) {
	if !user.IsCurrentUserCapable(c, NEPTUNE_API) {
		return "", "", NOT_ENABLED_MSG
	}

	neptuneCode := fmt.Sprintf("puts neptune(:boo => 2,\n")

	for key, val := range params {
		neptuneCode += fmt.Sprintf("  %v => %v,\n", key, val)
	}

	neptuneCode += fmt.Sprintf("  :baz => 2).inspect\n\n")
	return WriteJobCode(c, neptuneCode)
}

func WriteJobCode(c appengine.Context, code string) (string, string, string) {
	return WriteTempFile(c, code, "job.rb")
}

func WriteTempFile(c appengine.Context, code string, fileName string) (string, string, string) {
	if !user.IsCurrentUserCapable(c, NEPTUNE_API) {
		return "", "", NOT_ENABLED_MSG
	}

	var randNum int32
	binary.Read(rand.Reader, binary.LittleEndian, &randNum)
	neptuneDir := fmt.Sprintf("/tmp/neptune-%v", randNum)

	if err := os.MkdirAll(neptuneDir, 0777); err != nil {
		fmt.Printf("error seen creating directory %v: %v", neptuneDir, err)
		return "", "", fmt.Sprintf("%v", err)
	}

	fileLocation := fmt.Sprintf("%v/%v", neptuneDir, fileName)
	file, err := os.Create(fileLocation)

	if err != nil {
		fmt.Printf("error seen creating file %v: %v", fileLocation, err)
		return "", "", fmt.Sprintf("%v", err)
	}

	if _, err2 := file.WriteString(code); err2 != nil {
		fmt.Printf("error seen writing to file %v: %v", fileLocation, err2)
		return "", "", fmt.Sprintf("%v", err2)
	}

	if err3 := file.Close(); err3 != nil {
		fmt.Printf("error seen closing file %v: %v", fileLocation, err3)
		return "", "", fmt.Sprintf("%v", err3)
	}

	fmt.Printf("Wrote Neptune code to %v\n", fileLocation)
	return neptuneDir, fileName, ""
}

func init() {
	// nothing to do here for now
}
