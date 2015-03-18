#!/bin/bash
# Kills all running djinnServers.

is_djinn_alive()
{
    return `pgrep -f djinnServer | wc -l`
}

kill_djinn()
{
    SIGNAL=$1
    pkill $SIGNAL -f djinnServer
}

# send INT to terminate safely
is_djinn_alive
if [ $? -eq 0 ]; then
    exit 0
fi
kill_djinn -INT

# wait for djinn 10 seconds
count=0
while [ $count -le 5 ]; do
    is_djinn_alive
    if [ $? -eq 0 ]; then
	break
    fi
    count=$(expr $count + 1)
    sleep 2
done

# if it is still alive, kill -9
is_djinn_alive
if [ $? -ne 0 ]; then
    kill_djinn -9
fi
