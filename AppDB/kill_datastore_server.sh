ps aux | grep datastore_server | grep -v grep | awk '{print $2}' | xargs kill -9
