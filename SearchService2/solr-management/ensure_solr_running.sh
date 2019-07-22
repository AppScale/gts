#!/usr/bin/env bash

set -e
set -u

SOLR_EXTRACT_DIR=/opt/
SOLR_MANAGEMENT_DIR="$( realpath --strip "$( dirname "${BASH_SOURCE[0]}" )" )"

# Check if Solr is installed
VERSION=7.6.0
if ! ${SOLR_EXTRACT_DIR}/solr/bin/solr -version | grep "${VERSION}"
then
    echo "Can not start Solr ${VERSION} as it's not installed."
    exit 1
fi

# Root path for all SolrCloud nodes in Zookeeper.
SOLR_ZK_ROOT=/solr

# Determine zookeeper hosts
FIRST_ZK=$(head -1 /etc/appscale/zookeeper_locations)
ZK_HOST="${FIRST_ZK}"
for host in $(tail -n +2 /etc/appscale/zookeeper_locations)
do
    ZK_HOST="${ZK_HOST},${host}"
done
ZK_HOST="${ZK_HOST}${SOLR_ZK_ROOT}"
PRIVATE_IP=$(cat /etc/appscale/my_private_ip)
solr_zk="${SOLR_EXTRACT_DIR}/solr/bin/solr zk"

if ${solr_zk} ls ${SOLR_ZK_ROOT} -z "${FIRST_ZK}"
then
    echo "Zookeeper root is already created."
else
    echo "Creating zookeeper root."
    ${solr_zk} mkroot ${SOLR_ZK_ROOT} -z "${FIRST_ZK}" \
      || ${solr_zk} ls ${SOLR_ZK_ROOT} -z "${FIRST_ZK}"
    # We shouldn't fail if root was created after we entered to else clause.
fi

# Generating proper solr.in.sh with needed SolrCloud configurations.
HEAP_REDUCTION="${HEAP_REDUCTION:-0.0}"
TOTAL_MEM_KB=$(awk '/MemTotal/ { print $2 }' /proc/meminfo)
# Give Solr at most half of total memory minus heap reduction (kill if greater).
SOLR_MEM_MAX=$(echo "$TOTAL_MEM_KB $HEAP_REDUCTION" \
               | awk '{ printf "%d", $1 * (1 - $2) / 1024 / 2 }')
# Always try to give at least 70% of max memory.
SOLR_MEM_LOW=$(echo "$SOLR_MEM_MAX" | awk '{ printf "%d", $1 * 0.70 }')
# Slow process down when usage is higher.
SOLR_MEM_HIGH=$(echo "$SOLR_MEM_MAX" | awk '{ printf "%d", $1 * 0.90 }')

mkdir /var/solr7
sudo chown solr:solr /var/solr7
mkdir -p /var/log/appscale/solr
sudo chown -R solr:solr /var/log/appscale/solr

export SOLR_HEAP="${SOLR_MEM_HIGH}m"
export MEMORY_LOW="${SOLR_MEM_LOW}M"
export MEMORY_HIGH="${SOLR_MEM_HIGH}M"
export MEMORY_MAX="${SOLR_MEM_MAX}M"
export ZK_HOST
export PRIVATE_IP
envsubst '$SOLR_HEAP $ZK_HOST $PRIVATE_IP' \
 < "${SOLR_MANAGEMENT_DIR}/solr.in.sh" > "/tmp/solr.in.sh"
envsubst '$MEMORY_LOW $MEMORY_HIGH $MEMORY_MAX'\
 < "${SOLR_MANAGEMENT_DIR}/solr.service" > "/tmp/solr.service"
if cmp -s "/tmp/solr.in.sh" "/etc/default/solr.in.sh" \
&& cmp -s "/tmp/solr.service" "/etc/systemd/system/solr.service"
then
    echo "/etc/default/solr.in.sh has no changes."
    echo "/etc/systemd/system/solr.service has no changes."
    echo "Making sure Solr is running."
    sudo systemctl enable solr
    sudo systemctl start solr
else
    echo "Copying new solr.in.sh to /etc/default/solr.in.sh"
    sudo cp "/tmp/solr.in.sh" "/etc/default/solr.in.sh"
    echo "Copying new solr.service to /etc/systemd/system/solr.service"
    sudo cp "/tmp/solr.service" "/etc/systemd/system/solr.service"
    echo "Making sure Solr is restarted."
    sudo systemctl daemon-reload
    sudo systemctl enable solr
    sudo systemctl restart solr
fi

echo "Making sure appscale-specific config set is uploaded to zookeeper."
"${SOLR_MANAGEMENT_DIR}"/ensure_config_set.sh

echo "Solr is installed, configured and started."
