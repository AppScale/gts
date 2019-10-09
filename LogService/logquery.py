#!/usr/bin/python
import argparse
import capnp  # pylint: disable=unused-import
import logging
import logging_capnp
import socket
import struct
import sys
import time


from urlparse import urlparse


_I_SIZE = struct.calcsize('I')
MAX_LOG_LINE_LENGTH = 120

def get_connection(args):
  url = urlparse(args.con)
  if url.scheme not in ('tcp', 'unix'):
    raise ValueError("Unsupported connection: %s" % args.con)
  if url.scheme == 'unix':
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(url.path)
  else:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(url.netloc.split(':', 2))
  sock.send('a%s%s' % (struct.pack('I', len(args.app_id)), args.app_id))
  return sock

def get_query(args, offset=None):
  query = logging_capnp.Query.new_message()
  if args.start:
    query.startTime = int(args.start)
  if args.end:
    query.endTime = int(args.end)
  if args.ids:
    query.requestIds = args.ids
  query.versionIds = [args.version]
  query.count = args.count
  query.reverse = args.reverse
  if offset:
    query.offset = offset
  return query.to_bytes()

def output_http(record):
  time_seconds = (record.endTime or record.startTime) / 10**6
  date_string = time.strftime('%d/%b/%Y:%H:%M:%S %z',
                              time.localtime(time_seconds))
  print '%s: %s - %s [%s] "%s %s %s" %d %d - "%s"' % (
        record.requestId, record.ip, record.nickname, date_string, record.method, record.resource,
        record.httpVersion, record.status or 0, record.responseSize or 0, record.userAgent)

def output_appengine(record):
  output_http(record)
  for appLog in record.appLogs:
    time_seconds = float(appLog.time) / 10**6
    date_string = time.strftime('%M:%S', time.localtime(time_seconds))
    line = ' + %s.%s %s %s' % (date_string, str(round(time_seconds % 1, 3))[2:],
                               logging.getLevelName(appLog.level), appLog.message)
    n = MAX_LOG_LINE_LENGTH
    line_no = 0
    for line in (line[i * n:i * n+n] for i, _ in enumerate(line[::n])):
      if line_no == 0:
        print line
      else:
        print '   %s' % line

def output_plain(record):
  for appLog in record.appLogs:
    time_seconds = float(appLog.time) / 10**6
    date_string = time.strftime('%d/%b/%Y:%H:%M:%S', time.localtime(time_seconds))
    print '%s.%s %s' % (date_string, str(round(time_seconds % 1, 3))[2:], appLog.message)

OUT_REGISTER = dict(http=output_http, appengine=output_appengine, plain=output_plain)

def main(args):
  if args.mode == 'log':
    log(args)
  else:
    query_or_follow(args)

def log(args):
  sock = get_connection(args)
  try:
    for line in sys.stdin:
      time_usec = int(time.time() * 10**6)
      m = logging_capnp.RequestLog.new_message()
      m.appId = args.app_id
      m.versionId = args.version
      m.startTime = time_usec
      m.endTime = time_usec
      m.init('appLogs', 1)
      m.appLogs[0].level = logging.INFO
      m.appLogs[0].time = time_usec
      m.appLogs[0].message = line.strip()
      buf = m.to_bytes()
      sock.send('l%s%s' % (struct.pack('I', len(buf)), buf))
  finally:
    sock.close()

def query_or_follow(args):
  start = time.time()
  record_count = 0
  offset = None
  sock = get_connection(args)
  outputter = OUT_REGISTER[args.format]
  try:
    fh = sock.makefile()
    try:
      # send query
      while True:
        if args.mode == 'query' or offset is None:
          buf = get_query(args, offset)
          mode = 'q' if args.mode == 'query' else 'f'
          fh.write('%s%s%s' % (mode, struct.pack('I', len(buf)), buf))
          fh.flush()
        # receive results
        result_count, = struct.unpack('I', fh.read(_I_SIZE))
        if result_count == 0:
          break
        for _ in xrange(result_count):
          buflen, = struct.unpack('I', fh.read(_I_SIZE))
          record = logging_capnp.RequestLog.from_bytes(fh.read(buflen))
          outputter(record)
          record_count += 1
          if record_count == args.count:
            break
        offset = record.offset
        if args.mode == 'query':
          break
    finally:
      fh.close()
  finally:
    sock.close()
  print "Returned %s records in %s seconds" % (record_count, time.time() - start)

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Query AppScale logserver.')
  parser.add_argument('--app_id', type=str, required=True, help='app_id')
  parser.add_argument('--version', type=str, required=True, help='app version')
  parser.add_argument('--con', type=str, nargs='?', default='unix:///run/appscale/logserver.sock',
                      help='Connection eg tcp://10.10.10.10:1010. (Default local log server)')
  parser.add_argument('--start', type=int, nargs='?', help='start epoch timestamp')
  parser.add_argument('--end', type=int, nargs='?', help='end epoch timestamp')
  parser.add_argument('--ids', type=str, nargs='+', help='requestIds')
  parser.add_argument('--count', type=int, nargs='?', help='count', default=10)
  parser.add_argument('--format', type=str, choices=['http', 'appengine', 'plain'], nargs='?',
                      help='output format', default='appengine')
  parser.add_argument('--mode', type=str, choices=['query', 'follow', 'log'], nargs='?',
                      help='mode', default='query')
  parser.add_argument('--reverse', action='store_true', help='reverse log order', default=False)
  args = parser.parse_args()
  #import pdb; pdb.set_trace()
  main(args)

