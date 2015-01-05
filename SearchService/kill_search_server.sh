# Monit watches the Search Server, so it will restart after being killed.
ps aux | grep search_server | grep -v grep | awk '{print $2}' | xargs kill -9
