// Copyright 2012 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

// Package file provides a client for Google Cloud Storage.
package file

import (
	"fmt"
	"os"
	"path"
	"time"

	"appengine"
	"appengine_internal"
	blobpb "appengine_internal/blobstore"
	filepb "appengine_internal/files"
	"code.google.com/p/goprotobuf/proto"
)

// gsFilePrefix is the prefix for all Google Cloud Storage files.
const gsFilePrefix = "/gs/"

// Stat stats a file.
func Stat(c appengine.Context, filename string) (os.FileInfo, error) {
	// The file has to be open for stat to succeed, for now.
	// TODO: remove this after the restriction is lifted.
	oreq := &filepb.OpenRequest{
		Filename:    &filename,
		ContentType: filepb.FileContentType_RAW.Enum(),
		OpenMode:    filepb.OpenRequest_READ.Enum(),
	}
	ores := &filepb.OpenResponse{}
	if err := c.Call("file", "Open", oreq, ores, nil); err != nil {
		return nil, err
	}
	defer func() {
		creq := &filepb.CloseRequest{
			Filename: oreq.Filename,
		}
		c.Call("file", "Close", creq, new(filepb.CloseResponse), nil)
	}()

	sreq := &filepb.StatRequest{
		Filename: proto.String(filename),
	}
	sres := &filepb.StatResponse{}
	if err := c.Call("file", "Stat", sreq, sres, nil); err != nil {
		return nil, err
	}
	for _, st := range sres.Stat {
		if *st.Filename == filename {
			return fileInfo{st}, nil
		}
	}
	return nil, os.ErrNotExist
}

type fileInfo struct {
	s *filepb.FileStat
}

func (fi fileInfo) Name() string      { return path.Base(*fi.s.Filename) }
func (fi fileInfo) IsDir() bool       { return false } // TODO: verify this is correct. can we have directories?
func (fi fileInfo) Mode() os.FileMode { return 0600 }
func (fi fileInfo) Sys() interface{}  { return fi.s }

func (fi fileInfo) ModTime() time.Time {
	if fi.s.Mtime == nil {
		return time.Time{}
	}
	return time.Unix(*fi.s.Mtime, 0)
}

func (fi fileInfo) Size() int64 {
	return fi.s.GetLength()
}

// DefaultBucketName returns the name of this application's
// default Google Cloud Storage bucket.
func DefaultBucketName(c appengine.Context) (string, error) {
	req := new(filepb.GetDefaultGsBucketNameRequest)
	res := new(filepb.GetDefaultGsBucketNameResponse)
	if err := c.Call("file", "GetDefaultGsBucketName", req, res, nil); err != nil {
		return "", err
	}
	if res.DefaultGsBucketName == nil {
		return "", fmt.Errorf("file: no default bucket name returned in RPC response: %v", res)
	}
	return *res.DefaultGsBucketName, nil
}

// Delete deletes a file.
func Delete(c appengine.Context, filename string) error {
	req := &filepb.DeleteRequest{
		Filename: &filename,
	}
	res := new(filepb.DeleteResponse)
	// No fields in response to check.
	return c.Call("file", "Delete", req, res, nil)
}

func init() {
	appengine_internal.RegisterErrorCodeMap("blobstore", blobpb.BlobstoreServiceError_ErrorCode_name)
	appengine_internal.RegisterErrorCodeMap("file", filepb.FileServiceErrors_ErrorCode_name)
}
