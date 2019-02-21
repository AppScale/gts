#!/usr/bin/env bash

set -e
set -u

usage()
{
    echo "usage: init-filebeat.sh --logstash IP:PORT"
}


if [[ $# == 2 && $1 == '--logstash' ]]; then
    LOGSTASH_LOCATION=$2
else
    usage
    exit 1
fi

while fuser /var/cache/apt/archives/lock /var/lib/apt/lists/lock /var/lib/dpkg/lock ; do
  echo "Waiting for apt lock"
  sleep 60
done

if ! systemctl | grep -q filebeat; then
    echo "Installing Filebeat..."
    curl -L -O https://artifacts.elastic.co/downloads/beats/filebeat/filebeat-5.6.4-amd64.deb
    sudo dpkg -i filebeat-5.6.4-amd64.deb
else
    echo "Filebeat has been already installed"
fi


echo "Configuring Filebeat..."
cat > /etc/filebeat/filebeat.yml << FILEBEAT_YML

filebeat.prospectors:
- input_type: log
  paths: ["/opt/appscale/logserver/requests-*"]
  json.keys_under_root: true

output.logstash:
  hosts: ["${LOGSTASH_LOCATION}"]

FILEBEAT_YML


# It's just a flag used in AppServer/../logservice_stub
touch /etc/appscale/elk-enabled

echo "Starting Filebeat service..."
systemctl enable filebeat.service
systemctl start filebeat.service
