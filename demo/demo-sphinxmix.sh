#!/bin/bash

# run with --debug for traceback

cd "$(dirname "$0")"
CURDIR=$(pwd)
CONF=$CURDIR/conf

ARGS=${*}

source cli_functions.bash
source mixnet_functions.bash

exe export PANORAMIX_CONFIG=$CONF/ec1_settings


echo
exe $CMD peer list

echo
exe $CMD key show

echo
read -p "Create peer: " Y

with_self_consensus "peer create --name peer1"
PEER1_ID="${consensus_result}"

exe $CMD peer info --peer-id ${PEER1_ID}

ENDPOINT1="SPHINX_PEER1"

echo
read -p "Create endpoint $ENDPOINT1: " Y

with_self_consensus "endpoint create --endpoint-id ${ENDPOINT1} --peer-id ${PEER1_ID} --endpoint-type SPHINXMIX --size-min 3 --size-max 10"
EP_CREATE_CONSENSUS="${consensus}"

echo
read -p "List endpoints: " Y

echo
exe $CMD endpoint list --peer-id ${PEER1_ID}

echo
exe export PANORAMIX_CONFIG=$CONF/ec2_settings

echo
read -p "Create second peer: " Y

with_self_consensus "peer create --name peer2"
PEER2_ID="${consensus_result}"

echo
read -p "Import peer data: " Y

echo
exe $CMD peer import --peer-id ${PEER1_ID}

echo
read -p "Send first message: " Y

echo
exe $CMD message send --recipients ${PEER1_ID},${PEER2_ID},${PEER2_ID} --endpoint-id ${ENDPOINT1} --data "first text"

echo
exe $CMD inbox list --endpoint-id ${ENDPOINT1}

echo
read -p "Send two more messages: " Y

echo
exe $CMD message send --recipients ${PEER1_ID},${PEER2_ID} --endpoint-id ${ENDPOINT1} --data "second text"

echo
exe $CMD message send --recipients ${PEER1_ID},${PEER2_ID} --endpoint-id ${ENDPOINT1} --data "third text"

echo
read -p "List inbox again: " Y

echo
exe $CMD inbox list --endpoint-id ${ENDPOINT1}

echo
exe export PANORAMIX_CONFIG=$CONF/ec1_settings

echo
read -p "Endpoint owner closes the inbox: " Y

ACCEPTED_LOG=/tmp/INBOX_ACCEPTED_LOG_GPG_PEER1
write_hashes_log ${ENDPOINT1} ${ACCEPTED_LOG}
with_self_consensus "inbox close --endpoint-id ${ENDPOINT1} --on-last-consensus-id ${EP_CREATE_CONSENSUS} --from-log ${ACCEPTED_LOG}"
EP_CLOSE_CONSENSUS="${consensus}"

echo
exe $CMD endpoint info --endpoint-id "${ENDPOINT1}"

echo
read -p "Endpoint owner processes the inbox: " Y

echo
PROCESS_LOG=/tmp/INBOX_PROCESS_LOG_GPG_PEER1
exe $CMD inbox process --peer-id ${PEER1_ID} --endpoint-id ${ENDPOINT1} --process-log-file "${PROCESS_LOG}" --upload

echo
read -p "Endpoint owner acknowledges the outbox: " Y

with_self_consensus "processed ack --endpoint-id ${ENDPOINT1} --on-last-consensus-id ${EP_CLOSE_CONSENSUS} --from-log ${PROCESS_LOG}"

echo
read -p "Check endpoint status: " Y

echo
exe $CMD endpoint info --endpoint-id "${ENDPOINT1}"

echo
read -p "List outbox: " Y

echo
exe $CMD outbox list --endpoint-id "${ENDPOINT1}"
