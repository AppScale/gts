#!/usr/bin/env bash
#
# The script ensures that appscale_search_api_configs set is defined
# in SolrCloud (uploaded to zookeeper).
# The config set is used by SearchService2
# when new collections (indexes) are created.

set -e
set -u

# This name is used in appscale.search.solr_api when new collection is created.
CONFIG_SET_NAME=appscale_search_api_config

# Directory where Solr is installed.
SOLR_INSTALL_DIR=${SOLR_INSTALL_DIR:-/opt/solr}

# Root path for all SolrCloud nodes in Zookeeper.
SOLR_ZK_ROOT=/solr

# Zookeeper location
ZK_LOCATION=${ZK_LOCATION:-$(head -1 /etc/appscale/zookeeper_locations)}

SOLR_BIN="${SOLR_INSTALL_DIR}/bin/solr"
CONFIG_PATH=${SOLR_ZK_ROOT}/configs/${CONFIG_SET_NAME}
if ${SOLR_BIN} zk ls ${CONFIG_PATH} -z ${ZK_LOCATION} | grep managed-schema
then
    if [[ ${FORCE_UPLOAD:-no} == "yes" ]]
    then
        echo "Upgrading configs set."
    else
        echo "Config set ${CONFIG_SET_NAME} already exists."
        echo "Use FORCE_UPLOAD=yes to force upgrade of configs set."
        exit 0
    fi
fi

# Create temp directory to hold all config files.
CONFIGS_TMP_DIR=/tmp/appscale-solr-config-set
SOLR_MANAGEMENT_DIR="$( realpath --strip "$( dirname "${BASH_SOURCE[0]}" )" )"
mkdir -p "${CONFIGS_TMP_DIR}"

# Copy all default configurations from solr install directory
cp -r ${SOLR_INSTALL_DIR}/server/solr/configsets/_default/conf/* "${CONFIGS_TMP_DIR}"

# Copy the only customized file with managed-schema
cp "${SOLR_MANAGEMENT_DIR}"/managed-schema.appscale "${CONFIGS_TMP_DIR}"/managed-schema

echo "Uploading configs directory as appscale_search_api_config"
bash ${SOLR_INSTALL_DIR}/server/scripts/cloud-scripts/zkcli.sh \
  -zkhost "${ZK_LOCATION}${SOLR_ZK_ROOT}" -cmd upconfig \
  -confname "${CONFIG_SET_NAME}" -confdir "${CONFIGS_TMP_DIR}"
