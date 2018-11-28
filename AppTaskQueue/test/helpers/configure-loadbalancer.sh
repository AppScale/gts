#!/usr/bin/env bash
#
# Ensures that HAProxy is running on the machine.
# Configures haproxy to listen on specific port and distribute load
# across number of taskqueue locations.


set -e
set -u


usage() {
    echo "Usage: ${0} --tq-locations-file <FILE> --listen-tcp <HOST:PORT>"
    echo
    echo "Options:"
    echo "   --tq-locations-file <FILE>   File containing taskqueue locations"
    echo "   --listen-tcp <HOST:PORT>     Host and port to listen on"
    exit 1
}

LOCATIONS_FILE=
LISTEN_TCP=

# Let's get the command line arguments.
while [ $# -gt 0 ]; do
    if [ "${1}" = "--tq-locations-file" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        LOCATIONS_FILE="${1}"
        shift
        continue
    fi
    if [ "${1}" = "--listen-tcp" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        LISTEN_TCP="${1}"
        shift
        continue
    fi
    usage
done

if [ -z "${LOCATIONS_FILE}" ] || [ -z "${LISTEN_TCP}" ]; then
    usage
fi


log() {
    local LEVEL=${2:-INFO}
    echo "$(date +'%Y-%m-%d %T'): $LEVEL $1"
}


mv /etc/haproxy/haproxy.cfg /etc/haproxy/haproxy.cfg.orig

cat > /etc/haproxy/haproxy.cfg << CONFIG
global
  maxconn 64000
  ulimit-n 200000

  # log incoming requests - may need to tell syslog to accept these requests
  # http://kevin.vanzonneveld.net/techblog/article/haproxy_logging/
  log             127.0.0.1       local1 warning

  # Distribute the health checks with a bit of randomness
  spread-checks 5

  # Bind socket for haproxy stats
  stats socket /etc/haproxy/stats level admin

# Settings in the defaults section apply to all services (unless overridden in a specific config)
defaults

  # apply log settings from the global section above to services
  log global

  # Proxy incoming traffic as HTTP requests
  mode http

  # Use round robin load balancing, however since we will use maxconn that will take precedence
  balance roundrobin

  maxconn 64000

  # Log details about HTTP requests
  #option httplog

  # If sending a request fails, try to send it to another, 3 times
  # before aborting the request
  retries 3

  # Do not enforce session affinity (i.e., an HTTP session can be served by
  # any Mongrel, not just the one that started the session
  option redispatch

  # Time to wait for a connection attempt to a server.
  timeout connect 120000ms

  # The maximum inactivity time allowed for a client.
  timeout client 50000ms

  # The maximum inactivity time allowed for a server.
  timeout server 600000ms

  # Enable the statistics page
  stats enable
  stats uri     /haproxy?stats
  stats realm   Haproxy\ Statistics
  stats auth    haproxy:stats

  # Create a monitorable URI which returns a 200 if haproxy is up
  # monitor-uri /haproxy?monitor

  # Amount of time after which a health check is considered to have timed out
  timeout check 5000

listen TaskQueue
  bind ${LISTEN_TCP}
CONFIG

awk '{ print "  server TaskQueue-" $1 " " $1 " maxconn 1 check" }' \
    "${LOCATIONS_FILE}" \
    >> /etc/haproxy/haproxy.cfg


log "Restarting haproxy"
service haproxy restart
