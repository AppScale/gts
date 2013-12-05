// Copyright 2012 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

/*
Package socket provides outbound network sockets.
*/
package socket

import (
	"fmt"
	"io"
	"net"
	"strconv"
	"time"

	"appengine"
	"appengine_internal"
	pb "appengine_internal/socket"
	"code.google.com/p/goprotobuf/proto"
)

// Dial connects to the address addr on the network protocol.
// The address format is host:port, where host may be a hostname or an IP address.
// Known protocols are "tcp" and "udp".
// The returned connection satisfies net.Conn, and is valid while c is valid;
// if the connection is to be used after c becomes invalid, invoke SetContext
// with the new context.
func Dial(c appengine.Context, protocol, addr string) (*Conn, error) {
	return DialTimeout(c, protocol, addr, 0)
}

var ipFamilies = []pb.CreateSocketRequest_SocketFamily{
	pb.CreateSocketRequest_IPv4,
	pb.CreateSocketRequest_IPv6,
}

// DialTimeout is like Dial but takes a timeout.
// The timeout includes name resolution, if required.
func DialTimeout(c appengine.Context, protocol, addr string, timeout time.Duration) (*Conn, error) {
	var deadline time.Time
	if timeout > 0 {
		deadline = time.Now().Add(timeout)
	}

	host, portStr, err := net.SplitHostPort(addr)
	if err != nil {
		return nil, err
	}
	port, err := strconv.Atoi(portStr)
	if err != nil {
		return nil, fmt.Errorf("socket: bad port %q: %v", portStr, err)
	}

	var prot pb.CreateSocketRequest_SocketProtocol
	switch protocol {
	case "tcp":
		prot = pb.CreateSocketRequest_TCP
	case "udp":
		prot = pb.CreateSocketRequest_UDP
	default:
		return nil, fmt.Errorf("socket: unknown protocol %q", protocol)
	}

	packedAddrs, resolved, err := resolve(c, ipFamilies, host, deadline)
	if err != nil {
		return nil, fmt.Errorf("socket: failed resolving %q: %v", host, err)
	}
	if len(packedAddrs) == 0 {
		return nil, fmt.Errorf("no addresses for %q", host)
	}

	packedAddr := packedAddrs[0] // use first address
	fam := pb.CreateSocketRequest_IPv4
	if len(packedAddr) == net.IPv6len {
		fam = pb.CreateSocketRequest_IPv6
	}

	req := &pb.CreateSocketRequest{
		Family:   fam.Enum(),
		Protocol: prot.Enum(),
		RemoteIp: &pb.AddressPort{
			Port:          proto.Int32(int32(port)),
			PackedAddress: packedAddr,
		},
	}
	if resolved {
		req.RemoteIp.HostnameHint = &host
	}
	res := &pb.CreateSocketReply{}
	if err := c.Call("remote_socket", "CreateSocket", req, res, opts(deadline)); err != nil {
		return nil, err
	}

	return &Conn{
		c:      c,
		desc:   res.GetSocketDescriptor(),
		prot:   prot,
		local:  res.ProxyExternalIp,
		remote: req.RemoteIp,
	}, nil
}

// LookupIP returns the given host's IP addresses.
func LookupIP(c appengine.Context, host string) (addrs []net.IP, err error) {
	packedAddrs, _, err := resolve(c, ipFamilies, host, time.Time{})
	if err != nil {
		return nil, fmt.Errorf("socket: failed resolving %q: %v", host, err)
	}
	addrs = make([]net.IP, len(packedAddrs))
	for i, pa := range packedAddrs {
		addrs[i] = net.IP(pa)
	}
	return addrs, nil
}

func resolve(c appengine.Context, fams []pb.CreateSocketRequest_SocketFamily, host string, deadline time.Time) ([][]byte, bool, error) {
	// Check if it's an IP address.
	if ip := net.ParseIP(host); ip != nil {
		if ip := ip.To4(); ip != nil {
			return [][]byte{ip}, false, nil
		}
		return [][]byte{ip}, false, nil
	}

	req := &pb.ResolveRequest{
		Name:            &host,
		AddressFamilies: fams,
	}
	res := &pb.ResolveReply{}
	if err := c.Call("remote_socket", "Resolve", req, res, opts(deadline)); err != nil {
		// XXX: need to map to pb.ResolveReply_ErrorCode?
		return nil, false, err
	}
	return res.PackedAddress, true, nil
}

func opts(deadline time.Time) *appengine_internal.CallOptions {
	if deadline.IsZero() {
		return nil
	}
	return &appengine_internal.CallOptions{
		Timeout: deadline.Sub(time.Now()),
	}
}

// Conn represents a socket connection.
// It implements net.Conn.
type Conn struct {
	c      appengine.Context
	desc   string
	offset int64

	prot          pb.CreateSocketRequest_SocketProtocol
	local, remote *pb.AddressPort

	readDeadline, writeDeadline time.Time // optional
}

// SetContext sets the context that is used by this Conn.
// It is usually used only when using a Conn that was created in a different context,
// such as when a connection is created during a warmup request but used while
// servicing a user request.
func (cn *Conn) SetContext(c appengine.Context) {
	cn.c = c
}

func (cn *Conn) Read(b []byte) (n int, err error) {
	const maxRead = 1 << 20
	if len(b) > maxRead {
		b = b[:maxRead]
	}

	req := &pb.ReceiveRequest{
		SocketDescriptor: &cn.desc,
		DataSize:         proto.Int32(int32(len(b))),
	}
	res := &pb.ReceiveReply{}
	if !cn.readDeadline.IsZero() {
		req.TimeoutSeconds = proto.Float64(cn.readDeadline.Sub(time.Now()).Seconds())
	}
	if err := cn.c.Call("remote_socket", "Receive", req, res, nil); err != nil {
		return 0, err
	}
	if len(res.Data) == 0 {
		return 0, io.EOF
	}
	if len(res.Data) > len(b) {
		return 0, fmt.Errorf("socket: internal error: read too much data: %d > %d", len(res.Data), len(b))
	}
	return copy(b, res.Data), nil
}

func (cn *Conn) Write(b []byte) (n int, err error) {
	const lim = 1 << 20 // max per chunk

	for n < len(b) {
		chunk := b[n:]
		if len(chunk) > lim {
			chunk = chunk[:lim]
		}

		req := &pb.SendRequest{
			SocketDescriptor: &cn.desc,
			Data:             chunk,
			StreamOffset:     &cn.offset,
		}
		res := &pb.SendReply{}
		if !cn.writeDeadline.IsZero() {
			req.TimeoutSeconds = proto.Float64(cn.writeDeadline.Sub(time.Now()).Seconds())
		}
		if err = cn.c.Call("remote_socket", "Send", req, res, nil); err != nil {
			// assume zero bytes were sent in this RPC
			break
		}
		n += int(res.GetDataSent())
	}

	cn.offset += int64(n)
	return
}

func (cn *Conn) Close() error {
	req := &pb.CloseRequest{
		SocketDescriptor: &cn.desc,
	}
	res := &pb.CloseReply{}
	if err := cn.c.Call("remote_socket", "Close", req, res, nil); err != nil {
		return err
	}
	cn.desc = "CLOSED"
	return nil
}

func addr(prot pb.CreateSocketRequest_SocketProtocol, ap *pb.AddressPort) net.Addr {
	if ap == nil {
		return nil
	}
	switch prot {
	case pb.CreateSocketRequest_TCP:
		return &net.TCPAddr{
			IP:   net.IP(ap.PackedAddress),
			Port: int(*ap.Port),
		}
	case pb.CreateSocketRequest_UDP:
		return &net.UDPAddr{
			IP:   net.IP(ap.PackedAddress),
			Port: int(*ap.Port),
		}
	}
	panic("unknown protocol " + prot.String())
}

func (cn *Conn) LocalAddr() net.Addr  { return addr(cn.prot, cn.local) }
func (cn *Conn) RemoteAddr() net.Addr { return addr(cn.prot, cn.remote) }

func (cn *Conn) SetDeadline(t time.Time) error {
	cn.readDeadline = t
	cn.writeDeadline = t
	return nil
}

func (cn *Conn) SetReadDeadline(t time.Time) error {
	cn.readDeadline = t
	return nil
}

func (cn *Conn) SetWriteDeadline(t time.Time) error {
	cn.writeDeadline = t
	return nil
}

func init() {
	appengine_internal.RegisterErrorCodeMap("remote_socket", pb.RemoteSocketServiceError_ErrorCode_name)
}
