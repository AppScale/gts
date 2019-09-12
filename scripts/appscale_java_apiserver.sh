#!/bin/bash
# Launches the AppScale Java Runtime API server

API_ARGS=""
while test -n "${1}"; do
  case "${1}" in
    --application_prefix)
      shift
      ;;
    --clear_datastore)
      ;;
    --datastore_consistency_policy)
      shift
      ;;
    --datastore_path)
      shift
      ;;
    *)
      API_ARGS="${API_ARGS} ${1}"
      ;;
  esac
  shift
done

exec python2 /root/appscale/AppServer/api_server.py ${API_ARGS}
