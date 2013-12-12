// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

// Package blobstore provides a client for App Engine's persistent blob
// storage service.
package blobstore

import (
	"bufio"
	"crypto/sha512"
	"fmt"
	"io"
	"io/ioutil"
	"mime"
	"mime/multipart"
	"net/http"
	"net/textproto"
	"net/url"
	"strconv"
	"strings"
	"time"

	"appengine"
	"appengine/datastore"
	"appengine/file"
	"code.google.com/p/goprotobuf/proto"

	basepb "appengine_internal/base"
	blobpb "appengine_internal/blobstore"
	filepb "appengine_internal/files"
)

const (
	blobInfoKind      = "__BlobInfo__"
	blobFileIndexKind = "__BlobFileIndex__"
	zeroKey           = appengine.BlobKey("")
)

// BlobInfo is the blob metadata that is stored in the datastore.
// Filename may be empty.
type BlobInfo struct {
	BlobKey      appengine.BlobKey
	ContentType  string    `datastore:"content_type"`
	CreationTime time.Time `datastore:"creation"`
	Filename     string    `datastore:"filename"`
	Size         int64     `datastore:"size"`
}

// isErrFieldMismatch returns whether err is a datastore.ErrFieldMismatch.
//
// The blobstore stores blob metadata in the datastore. When loading that
// metadata, it may contain fields that we don't care about. datastore.Get will
// return datastore.ErrFieldMismatch in that case, so we ignore that specific
// error.
func isErrFieldMismatch(err error) bool {
	_, ok := err.(*datastore.ErrFieldMismatch)
	return ok
}

// Stat returns the BlobInfo for a provided blobKey. If no blob was found for
// that key, Stat returns datastore.ErrNoSuchEntity.
func Stat(c appengine.Context, blobKey appengine.BlobKey) (*BlobInfo, error) {
	c, _ = appengine.Namespace(c, "") // Blobstore is always in the empty string namespace
	dskey := datastore.NewKey(c, blobInfoKind, string(blobKey), 0, nil)
	bi := &BlobInfo{
		BlobKey: blobKey,
	}
	if err := datastore.Get(c, dskey, bi); err != nil && !isErrFieldMismatch(err) {
		return nil, err
	}
	return bi, nil
}

// Send sets the headers on response to instruct App Engine to send a blob as
// the response body. This is more efficient than reading and writing it out
// manually and isn't subject to normal response size limits.
func Send(response http.ResponseWriter, blobKey appengine.BlobKey) {
	hdr := response.Header()
	hdr.Set("X-AppEngine-BlobKey", string(blobKey))

	if hdr.Get("Content-Type") == "" {
		// This value is known to dev_appserver to mean automatic.
		// In production this is remapped to the empty value which
		// means automatic.
		hdr.Set("Content-Type", "application/vnd.google.appengine.auto")
	}
}

// UploadURL creates an upload URL for the form that the user will
// fill out, passing the application path to load when the POST of the
// form is completed. These URLs expire and should not be reused. The
// opts parameter may be nil.
func UploadURL(c appengine.Context, successPath string, opts *UploadURLOptions) (*url.URL, error) {
	req := &blobpb.CreateUploadURLRequest{
		SuccessPath: proto.String(successPath),
	}
	if opts != nil {
		if n := opts.MaxUploadBytes; n != 0 {
			req.MaxUploadSizeBytes = &n
		}
		if n := opts.MaxUploadBytesPerBlob; n != 0 {
			req.MaxUploadSizePerBlobBytes = &n
		}
		if s := opts.StorageBucket; s != "" {
			req.GsBucketName = &s
		}
	}
	res := &blobpb.CreateUploadURLResponse{}
	if err := c.Call("blobstore", "CreateUploadURL", req, res, nil); err != nil {
		return nil, err
	}
	return url.Parse(*res.Url)
}

// UploadURLOptions are the options to create an upload URL.
type UploadURLOptions struct {
	MaxUploadBytes        int64 // optional
	MaxUploadBytesPerBlob int64 // optional

	// StorageBucket specifies the Google Cloud Storage bucket in which
	// to store the blob.
	// This is required if you use Cloud Storage instead of Blobstore.
	// Your application must have permission to write to the bucket.
	// You may optionally specify a bucket name and path in the format
	// "bucket_name/path", in which case the included path will be the
	// prefix of the uploaded object's name.
	StorageBucket string
}

// Delete deletes a blob.
func Delete(c appengine.Context, blobKey appengine.BlobKey) error {
	return DeleteMulti(c, []appengine.BlobKey{blobKey})
}

// DeleteMulti deletes multiple blobs.
func DeleteMulti(c appengine.Context, blobKey []appengine.BlobKey) error {
	s := make([]string, len(blobKey))
	for i, b := range blobKey {
		s[i] = string(b)
	}
	req := &blobpb.DeleteBlobRequest{
		BlobKey: s,
	}
	res := &basepb.VoidProto{}
	if err := c.Call("blobstore", "DeleteBlob", req, res, nil); err != nil {
		return err
	}
	return nil
}

func errorf(format string, args ...interface{}) error {
	return fmt.Errorf("blobstore: "+format, args...)
}

// ParseUpload parses the synthetic POST request that your app gets from
// App Engine after a user's successful upload of blobs. Given the request,
// ParseUpload returns a map of the blobs received (keyed by HTML form
// element name) and other non-blob POST parameters.
func ParseUpload(req *http.Request) (blobs map[string][]*BlobInfo, other url.Values, err error) {
	_, params, err := mime.ParseMediaType(req.Header.Get("Content-Type"))
	if err != nil {
		return nil, nil, err
	}
	boundary := params["boundary"]
	if boundary == "" {
		return nil, nil, errorf("did not find MIME multipart boundary")
	}

	blobs = make(map[string][]*BlobInfo)
	other = make(url.Values)

	mreader := multipart.NewReader(io.MultiReader(req.Body, strings.NewReader("\r\n\r\n")), boundary)
	for {
		part, perr := mreader.NextPart()
		if perr == io.EOF {
			break
		}
		if perr != nil {
			return nil, nil, errorf("error reading next mime part with boundary %q (len=%d): %v",
				boundary, len(boundary), perr)
		}

		bi := &BlobInfo{}
		ctype, params, err := mime.ParseMediaType(part.Header.Get("Content-Disposition"))
		if err != nil {
			return nil, nil, err
		}
		bi.Filename = params["filename"]
		formKey := params["name"]

		ctype, params, err = mime.ParseMediaType(part.Header.Get("Content-Type"))
		if err != nil {
			return nil, nil, err
		}
		bi.BlobKey = appengine.BlobKey(params["blob-key"])
		if ctype != "message/external-body" || bi.BlobKey == "" {
			if formKey != "" {
				slurp, serr := ioutil.ReadAll(part)
				if serr != nil {
					return nil, nil, errorf("error reading %q MIME part", formKey)
				}
				other[formKey] = append(other[formKey], string(slurp))
			}
			continue
		}

		// App Engine sends a MIME header as the body of each MIME part.
		tp := textproto.NewReader(bufio.NewReader(part))
		header, mimeerr := tp.ReadMIMEHeader()
		if mimeerr != nil {
			return nil, nil, mimeerr
		}
		bi.Size, err = strconv.ParseInt(header.Get("Content-Length"), 10, 64)
		if err != nil {
			return nil, nil, err
		}
		bi.ContentType = header.Get("Content-Type")

		// Parse the time from the MIME header like:
		// X-AppEngine-Upload-Creation: 2011-03-15 21:38:34.712136
		createDate := header.Get("X-AppEngine-Upload-Creation")
		if createDate == "" {
			return nil, nil, errorf("expected to find an X-AppEngine-Upload-Creation header")
		}
		bi.CreationTime, err = time.Parse("2006-01-02 15:04:05.000000", createDate)
		if err != nil {
			return nil, nil, errorf("error parsing X-AppEngine-Upload-Creation: %s", err)
		}

		blobs[formKey] = append(blobs[formKey], bi)
	}
	return
}

// Reader is a blob reader.
type Reader interface {
	io.Reader
	io.ReaderAt
	io.Seeker
}

// NewReader returns a reader for a blob. It always succeeds; if the blob does
// not exist then an error will be reported upon first read.
func NewReader(c appengine.Context, blobKey appengine.BlobKey) Reader {
	return file.OpenBlob(c, blobKey)
}

const writeBufferSize = 256 * 1024

// Writer is used for writing blobs. Blobs aren't fully written until
// Close is called, at which point the key can be retrieved by calling
// the Key method.
type Writer struct {
	c        appengine.Context
	filename string

	buf      []byte
	writeErr error // set in flush

	// set on Close:
	closed   bool
	closeErr error

	// set on first Key:
	blobKey appengine.BlobKey
}

// Verify that Writer implements the io.WriteCloser interface.
var _ io.WriteCloser = (*Writer)(nil)

// Prefix for all blobstore-based files.
const blobstoreFileDirectory = "/blobstore/"

// Prefix (after blobstoreFileDirectory) on all writable blob filenames.
// The part that follows when this is present is the "creation handle",
// which must then be looked up in datastore to find the blob once it's
// been finalized.
const creationHandlePrefix = "writable:"

// Create begins creating a new blob. The provided mimeType if non-empty
// is stored in the blob's BlobInfo in datastore, else defaults to
// application/octet-stream. The returned Writer should be written to,
// then closed, and then its Key method can be called to retrieve the
// newly-created blob key if there were no errors.
func Create(c appengine.Context, mimeType string) (*Writer, error) {
	c, _ = appengine.Namespace(c, "") // Blobstore is always in the empty string namespace
	if mimeType == "" {
		mimeType = "application/octet-stream"
	}
	req := &filepb.CreateRequest{
		Filesystem:  proto.String("blobstore"),
		ContentType: filepb.FileContentType_RAW.Enum(),
		Parameters: []*filepb.CreateRequest_Parameter{
			{
				Name:  proto.String("content_type"),
				Value: proto.String(mimeType),
			},
		},
	}
	res := &filepb.CreateResponse{}
	if err := c.Call("file", "Create", req, res, nil); err != nil {
		return nil, err
	}

	w := &Writer{
		c:        c,
		filename: *res.Filename,
	}
	if !strings.HasPrefix(w.filename, blobstoreFileDirectory) {
		return nil, errorf("unexpected filename from files service: %q", w.filename)
	}

	oreq := &filepb.OpenRequest{
		Filename:      res.Filename,
		ContentType:   filepb.FileContentType_RAW.Enum(),
		OpenMode:      filepb.OpenRequest_APPEND.Enum(),
		ExclusiveLock: proto.Bool(true),
	}
	ores := &filepb.OpenResponse{}
	if err := c.Call("file", "Open", oreq, ores, nil); err != nil {
		return nil, err
	}
	return w, nil
}

func (w *Writer) Write(p []byte) (n int, err error) {
	if w.closed {
		return 0, errorf("Writer is already closed")
	}
	w.buf = append(w.buf, p...)
	if len(w.buf) >= writeBufferSize {
		w.flush()
	}
	return len(p), w.writeErr
}

// maxWriteChunkSize bounds our write RPC sizes.
const maxWriteChunkSize = 16 << 20

func (w *Writer) flush() {
	for len(w.buf) > 0 {
		chunk := w.buf
		if len(chunk) > maxWriteChunkSize {
			chunk = chunk[:maxWriteChunkSize]
		}
		req := &filepb.AppendRequest{
			Filename: proto.String(w.filename),
			Data:     chunk,
		}
		res := &filepb.AppendResponse{}
		if err := w.c.Call("file", "Append", req, res, nil); err != nil {
			w.writeErr = err
			return
		}
		w.buf = w.buf[len(chunk):]
	}
	w.buf = nil
}

// Close flushes outstanding buffered writes and finalizes the blob. After
// calling Close the key can be retrieved by calling Key.
func (w *Writer) Close() (closeErr error) {
	defer func() {
		// Save the error for Key
		w.closeErr = closeErr
	}()
	if w.closed {
		return errorf("Writer is already closed")
	}
	w.closed = true
	w.flush()
	if w.writeErr != nil {
		return w.writeErr
	}
	req := &filepb.CloseRequest{
		Filename: proto.String(w.filename),
		Finalize: proto.Bool(true),
	}
	res := &filepb.CloseResponse{}
	return w.c.Call("file", "Close", req, res, nil)
}

// Key returns the created blob key. It must be called after Close.
// An error is returned if Close wasn't called or returned an error.
func (w *Writer) Key() (appengine.BlobKey, error) {
	if !w.closed {
		return "", errorf("cannot call Key before Close")
	}

	if w.blobKey != "" {
		return w.blobKey, w.closeErr
	}

	handle := w.filename[len(blobstoreFileDirectory):]
	if !strings.HasPrefix(handle, creationHandlePrefix) {
		w.blobKey = appengine.BlobKey(handle)
		return w.blobKey, w.closeErr
	}

	k, err := w.keyNewWay(handle)
	if err == nil {
		w.blobKey = k
		return k, nil
	}

	k, err = w.keyOldWay(handle)
	if err == nil {
		w.blobKey = k
	}

	return k, err
}

// blobFileIndexKeyName returns the key name for a __BlobFileIndex__ entity.
//
// Per the Python SDK's blobstore.py, we return the creationHandle directly
// if it's under 500 bytes, else we return its hex SHA-512 value.
func blobFileIndexKeyName(creationHandle string) string {
	if len(creationHandle) < 500 {
		return creationHandle
	}
	h := sha512.New()
	io.WriteString(h, creationHandle)
	return fmt.Sprintf("%x", h.Sum(nil))
}

func (w *Writer) keyNewWay(handle string) (appengine.BlobKey, error) {
	key := datastore.NewKey(w.c, blobFileIndexKind, blobFileIndexKeyName(handle), 0, nil)
	var blobKey struct {
		Value string `datastore:"blob_key"`
	}
	err := datastore.Get(w.c, key, &blobKey)
	if err != nil && !isErrFieldMismatch(err) {
		return zeroKey, err
	}
	if blobKey.Value == "" {
		return zeroKey, errorf("no metadata for creation_handle %q", handle)
	}

	// Double-check that the BlobInfo actually exists.
	// (Consistent with Python.)
	key = datastore.NewKey(w.c, blobInfoKind, blobKey.Value, 0, nil)
	var dummy datastore.PropertyList
	err = datastore.Get(w.c, key, &dummy)
	if err != nil {
		return zeroKey, err
	}
	return appengine.BlobKey(blobKey.Value), nil
}

// keyOldWay looks up a blobkey from its creation_handle the old way:
// by doing an query against __BlobInfo__ entities.  This is now
// deprecated (corollary: the other way doesn't work yet), so we try
// this only after the new way fails, like Python does.
func (w *Writer) keyOldWay(handle string) (appengine.BlobKey, error) {
	query := datastore.NewQuery(blobInfoKind).
		Filter("creation_handle =", handle).
		KeysOnly().
		Limit(1)
	key, err := query.Run(w.c).Next(nil)
	if err != nil {
		if err != datastore.Done {
			return "", errorf("error looking up __BlobInfo__ entity for creation_handle %q: %v", handle, err)
		}
		return "", errorf("didn't find __BlobInfo__ entity for creation_handle %q", handle)
	}
	return appengine.BlobKey(key.StringID()), w.closeErr
}

// BlobKeyForFile returns a BlobKey for a Google Storage file.
// The filename should be of the form "/gs/bucket_name/object_name".
func BlobKeyForFile(c appengine.Context, filename string) (appengine.BlobKey, error) {
	req := &blobpb.CreateEncodedGoogleStorageKeyRequest{
		Filename: &filename,
	}
	res := &blobpb.CreateEncodedGoogleStorageKeyResponse{}
	if err := c.Call("blobstore", "CreateEncodedGoogleStorageKey", req, res, nil); err != nil {
		return "", err
	}
	return appengine.BlobKey(*res.BlobKey), nil
}
