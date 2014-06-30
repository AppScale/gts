# Remove logs, keys and tar balls
rm -f ./AppDB/logs/*
rm -f /var/cassandra/*/*
rm -f ./.appscale/secret.key
rm -f ./.appscale/ssh.key.private
rm -f /tmp/*.log
rm -f ./.appscale/*log
rm -f ./.appscale/certs/*
rm -rf ./downloads
rm -f /var/log/appscale/celery_workers/*
rm -f /var/log/appscale/*

