# Remove logs, keys and tar balls
rm -f ./AppDB/hadoop-0.20.0/logs/*
rm -f ./AppDB/hbase/hbase-0.20.0-alpha/logs/*
rm -f ./AppDB/hypertable/0.9.2.5/log/*
rm -f ./AppDB/logs/*
rm -f /var/cassandra/*/*
rm -f ./.appscale/secret.key
rm -f ./.appscale/ssh.key.private
rm -f ./AppLoadBalancer/log/*
rm -f /tmp/*.log
rm -f ./.appscale/*log
rm -f ./.appscale/certs/*
rm -rf ./downloads
