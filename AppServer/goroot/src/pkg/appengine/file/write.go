// Copyright 2012 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package file

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"strings"

	"appengine"
	pb "appengine_internal/files"
	"code.google.com/p/goprotobuf/proto"
)

const writeBufferSize = 512 * 1024

// CreateOptions are the file creation options.
// A nil *CreateOptions means the same as using all the default values.
type CreateOptions struct {
	// MIMEType is the MIME type to use.
	// The empty string means to use "application/octet-stream".
	MIMEType string

	// The Google Cloud Storage bucket name to use.
	// The empty string means to use the default bucket.
	BucketName string
}

func (o *CreateOptions) mime() string {
	if o == nil || o.MIMEType == "" {
		return "application/octet-stream"
	}
	return o.MIMEType
}

func (o *CreateOptions) gsBucketName(c appengine.Context) (string, error) {
	if o == nil || o.BucketName == "" {
		return DefaultBucketName(c)
	}
	return o.BucketName, nil
}

func (o *CreateOptions) requestFilename(c appengine.Context, filename string) (string, error) {
	if strings.HasPrefix(filename, "/gs/") {
		return filename, nil
	}
	if strings.HasPrefix(filename, "/") {
		return "", errors.New("file: unknown absolute filename pattern")
	}
	bucketName, err := o.gsBucketName(c)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("/gs/%s/%s", bucketName, filename), nil
}

// Create creates a new file, opened for append.
//
// The file must be closed when done writing.
//
// The provided filename may be absolute ("/gs/bucketname/objectname")
// or may be just the filename, in which case the bucket is determined
// from opts.  The absolute filename is returned.
func Create(c appengine.Context, filename string, opts *CreateOptions) (wc io.WriteCloser, absFilename string, err error) {
	reqFilename, err := opts.requestFilename(c, filename)
	if err != nil {
		return nil, "", err
	}
	req := &pb.CreateRequest{
		Filename:    &reqFilename,
		Filesystem:  proto.String("gs"),
		ContentType: pb.FileContentType_RAW.Enum(),
		Parameters: []*pb.CreateRequest_Parameter{
			{
				Name:  proto.String("content_type"),
				Value: proto.String(opts.mime()),
			},
		},
	}
	res := &pb.CreateResponse{}
	if err := c.Call("file", "Create", req, res, nil); err != nil {
		return nil, "", err
	}

	w := &writer{
		c:        c,
		filename: *res.Filename,
	}
	w.bw = bufio.NewWriterSize(appendWriter{w}, writeBufferSize)

	oreq := &pb.OpenRequest{
		Filename:      res.Filename,
		ContentType:   pb.FileContentType_RAW.Enum(),
		OpenMode:      pb.OpenRequest_APPEND.Enum(),
		ExclusiveLock: proto.Bool(true),
	}
	ores := &pb.OpenResponse{}
	if err := c.Call("file", "Open", oreq, ores, nil); err != nil {
		return nil, "", err
	}

	return w, reqFilename, nil
}

// writer is used for writing blobs. Blobs aren't fully written until
// Close is called, at which point the key can be retrieved by calling
// the Key method.
type writer struct {
	c        appengine.Context
	filename string
	closed   bool

	bw *bufio.Writer
}

func (w *writer) Write(p []byte) (n int, err error) {
	if w.closed {
		return 0, errors.New("file: Writer is closed")
	}
	return w.bw.Write(p)
}

// appendWriter is the unbuffered writer that actually makes the RPC
// calls. It is buffered by the bufio.Writer in *writer.
type appendWriter struct {
	w *writer
}

func (aw appendWriter) Write(p []byte) (n int, err error) {
	req := &pb.AppendRequest{
		Filename: &aw.w.filename,
		Data:     p,
	}
	res := &pb.AppendResponse{}
	if err := aw.w.c.Call("file", "Append", req, res, nil); err != nil {
		return 0, err
	}
	// No fields in AppendResponse to check.
	return len(p), nil
}

func (w *writer) Close() error {
	if w.closed {
		return fmt.Errorf("file: Writer is closed")
	}
	w.closed = true
	if err := w.bw.Flush(); err != nil {
		return err
	}
	req := &pb.CloseRequest{
		Filename: &w.filename,
		Finalize: proto.Bool(true),
	}
	res := &pb.CloseResponse{}
	return w.c.Call("file", "Close", req, res, nil)
}
