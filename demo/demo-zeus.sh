#!/bin/bash

source cli_functions.bash
source mixnet_functions.bash

NAME="$1"
shift
ARGS=${*}
CONF="${NAME}.data"

if [ -z "${TMPDIR}" ]; then
    TMPDIR=/tmp
fi

if [ -z "${NAME}" ]; then
    echo "Usage: ${0} PEERNAME"
    exit 1
fi

#           varname         defval      prompt_text     pre_prompt
cli_setenv  SHARE_CHANNEL    "${TMPDIR}/demo_share_channel"
cli_setenv  PANORAMIX_CONFIG "${CONF}/zeus"
cli_setenv  KEYID            "$(cat "${CONF}/zeus_keyid")"
cli_setenv  REGISTRY_FILE    "${TMPDIR}/registry_${KEYID}"

cli_setenv  NR_PEERS        "2" \
    "Enter number of mixnet servers to wait for"

cli_setenv  PEER_KEYID      "292918e814abd7ab9e476d99bf861f016cc4ffec765dabc010fc33aab0721dfd" \
    "Enter key_id of a peer to import (or leave empty to review peer list): "

cli_setenv  MIX_CREATE_NEG        "" \
    "Enter negotiation id for mix peer creation"

prompt_mix_peer () {
    ${CMD} peer list
}
cli_setenv  MIX_PEER "" \
    "Enter keyid of mixnet peer to import (or leave empty to review peer list)" \
    prompt_mix_peer

cli_setenv  INBOX_NEG "" \
    "Enter negotiation id for booth creation"

cli_setenv  INBOX_EP "" \
    "Enter id of created endpoint"

cli_setenv  INBOX_CYCLE_NEG "" \
    "Enter negotiation id for cycle creation"

cli_setenv  INBOX_CYCLE "" \
    "Enter id of created cycle"

cli_setenv  MIX_NEG "" \
    "Enter negotiation id to start mixing"

cli_setenv  MIX_PEER2 "" \
    "Enter peer_id"

cli_setenv  MIX_EP "" \
    "Enter endpoint_id"

cli_setenv  MIX_CYCLE "" \
    "Enter cycle_id"

cli_input_missing SHARE_CHANNEL NAME KEYID PEER_KEYID

rm -f -- "$REGISTRY_FILE"
for name in "${SHARE_CHANNEL}" "${SHARE_CHANNEL}/peers" "${SHARE_CHANNEL}/negotiations" "${SHARE_CHANNEL}/consensus" "${SHARE_CHANNEL}/mixes" "${SHARE_CHANNEL}/uploads"; do
    mkdir -p "${name}" || error cannot create directory "${name}"
done

with_self_consensus "peer create"

touch "${SHARE_CHANNEL}/peers/${KEYID}"

cli_input_missing NR_PEERS
while true; do
    nr_peers=0
    export OWNERS=
    for f in "${SHARE_CHANNEL}"/peers/*; do
        peerid="$(basename "${f}")"
        echo PEER "${peerid}"
        exe ${CMD} peer import --peer-id "${peerid}"
        nr_peers=$[nr_peers+1]
        if [ -z "${OWNERS}" ]; then
            export OWNERS="${peerid}"
        else
            export OWNERS="${OWNERS},${peerid}"
        fi
    done
    if ((nr_peers < NR_PEERS)); then
        echo -n "Only ${nr_peers}/${NR_PEERS} found. Press <enter> to try again."
        read c
    else
        break
    fi
done

echo
read -p "Next: negotiate to create joined peer; press <enter>. " y

run_with_neg MIX_CREATE_NEG "peer create --name joint --owners ${OWNERS}"
MIX_PEER="${consensus_result}"

exe ${CMD} peer import --peer-id "${MIX_PEER}"

ELECTION_PUBLIC="$(exe ${CMD} peer info --peer-id ${MIX_PEER} -f value -c key_data)"

echo
read -p "Next: negotiate to create and open booth endpoint; press <enter>. " y

FINAL_DECRYPT_EP="FINAL_DECR1"

run_with_neg INBOX_NEG "endpoint create --endpoint-id BOOTH1 --peer-id ${MIX_PEER} --size-min 2 --size-max 10 --endpoint-type ZEUS_BOOTH --link ${FINAL_DECRYPT_EP} OUTBOX PROCESSBOX"
INBOX_EP="${consensus_result}"
BOOTH_CREATE_CONSENSUS="${consensus}"

while true; do
    echo "Type message to send (or leave empty to end):"
    read -p '> ' message
    if [ -z "${message}" ]; then
        break
    else
        exe ${CMD} message send --recipient "${MIX_PEER}" --endpoint-id "${INBOX_EP}" --data "${message}"
    fi
done

exe ${CMD} inbox list --endpoint-id "${INBOX_EP}"

echo
read -p "Next: negotiate to close the inbox; press <enter>. " y

ACCEPTED_LOG=/tmp/INBOX_ACCEPTED_LOG_${NAME}

write_hashes_log ${INBOX_EP} ${ACCEPTED_LOG}
run_with_neg CLOSE_INBOX_NEG "inbox close --endpoint-id ${INBOX_EP} --on-last-consensus-id ${BOOTH_CREATE_CONSENSUS}  --from-log ${ACCEPTED_LOG}"
BOOTH_CLOSE_CONSENSUS="${consensus}"

echo
read -p "Next: peers will mix the messages consecutively; press <enter>. " y

PREVIOUS="$(ls -1 ${SHARE_CHANNEL}/peers | sort | grep -B 1 ${KEYID} | head -n 1)"

if [ "${PREVIOUS}" = "${KEYID}" ]; then
    INBOX_MIX_EP="${INBOX_EP}"
    FROM_BOX="ACCEPTED"
else
    INBOX_MIX_EP="SK_MIX1_${PREVIOUS:0:7}"
    FROM_BOX="OUTBOX"
fi

echo
read -p "Will make a ZEUS_SK_MIX endpoint in ${NAME}, get messages from ${INBOX_MIX_EP} and mix them; press <enter>. " y

MIX_EP="SK_MIX1_${KEYID:0:7}"
with_self_consensus "endpoint create --endpoint-id ${MIX_EP} --peer-id ${KEYID} --size-min 2 --size-max 10 --endpoint-type ZEUS_SK_MIX --param election_public ${ELECTION_PUBLIC} --link ${INBOX_MIX_EP} ${FROM_BOX} INBOX"
MIX_CREATE_CONSENSUS="${consensus}"


INBOX_LOG=/tmp/INBOX_LOG_${NAME}
rm $INBOX_LOG
run_if_not_file "inbox get --endpoint-id ${MIX_EP} --hashes-log-file ${INBOX_LOG}" "${INBOX_LOG}"

with_self_consensus "inbox close --endpoint-id ${MIX_EP} --on-last-consensus-id ${MIX_CREATE_CONSENSUS} --from-log ${INBOX_LOG}"
MIX_CLOSE_CONSENSUS="${consensus}"

PROCESS_LOG=/tmp/MIX_PROCESS_LOG_${NAME}
exe ${CMD} inbox process --peer-id ${KEYID} --endpoint-id ${MIX_EP} --process-log-file ${PROCESS_LOG} --upload

with_self_consensus "processed ack --endpoint-id ${MIX_EP} --on-last-consensus-id ${MIX_CLOSE_CONSENSUS} --from-log ${PROCESS_LOG}"

echo $MIX_EP > "${SHARE_CHANNEL}/mixes/INBOX_MIX_EP_${KEYID}"

echo "Waiting until all peers have mixed..."

LAST_MIX_PEER="$(ls -1 ${SHARE_CHANNEL}/peers | sort | tail -n 1)"
LAST_MIX_EP="$(cat_ready_file ${SHARE_CHANNEL}/mixes/INBOX_MIX_EP_${LAST_MIX_PEER})"

echo
read -p "Will make a ZEUS_SK_PARTIAL_DECRYPT endpoint in ${NAME}, get messages from the last mix outbox and partially decrypt them; press <enter>. " y

PARTIAL_DECRYPT_EP="PART_DECR1_${KEYID:0:7}"
with_self_consensus "endpoint create --endpoint-id ${PARTIAL_DECRYPT_EP} --peer-id ${KEYID} --size-min 2 --size-max 10 --endpoint-type ZEUS_SK_PARTIAL_DECRYPT --link ${LAST_MIX_EP} OUTBOX INBOX"
PARTIAL_DECRYPT_CREATE_CONSENSUS="${consensus}"

rm ${INBOX_LOG}
run_if_not_file "inbox get --endpoint-id ${PARTIAL_DECRYPT_EP} --hashes-log-file ${INBOX_LOG}" "${INBOX_LOG}"

with_self_consensus "inbox close --endpoint-id ${PARTIAL_DECRYPT_EP} --on-last-consensus-id ${PARTIAL_DECRYPT_CREATE_CONSENSUS} --from-log ${INBOX_LOG}"
PARTIAL_DECRYPT_CLOSE_CONSENSUS="${consensus}"

PROCESS_LOG=/tmp/PART_DECRYPT_PROCESS_LOG_${NAME}
exe ${CMD} inbox process --peer-id "${KEYID}" --endpoint-id "${PARTIAL_DECRYPT_EP}" --process-log-file ${PROCESS_LOG} --upload

with_self_consensus "processed ack --endpoint-id ${PARTIAL_DECRYPT_EP} --on-last-consensus-id ${PARTIAL_DECRYPT_CLOSE_CONSENSUS} --from-log ${PROCESS_LOG}"

echo
read -p "Next: Negotiate a final decryption endpoint; all peers will upload their partial decryptions there; press <enter>. " y

SORTED_PEERS="$(ls -1 ${SHARE_CHANNEL}/peers | sort)"
LINKS=""
for peer in ${SORTED_PEERS}; do
    LINKS+=" --link PART_DECR1_${peer:0:7} OUTBOX INBOX"
done

run_with_neg FINAL_DECRYPT_CREATE_NEG "endpoint create --endpoint-id ${FINAL_DECRYPT_EP} --peer-id ${MIX_PEER} --size-min 2 --size-max 10 --endpoint-type ZEUS_SK_COMBINE $LINKS"
FINAL_DECRYPT_CREATE_CONSENSUS="${consensus}"

DRY_RUN=""
if [ "${PREVIOUS}" != "${KEYID}" ]; then
    DRY_RUN="--dry-run"
fi

rm ${INBOX_LOG}
run_if_not_file "inbox get --endpoint-id ${FINAL_DECRYPT_EP} --hashes-log-file ${INBOX_LOG} ${DRY_RUN}" "${INBOX_LOG}"

echo
read -p "Next: negotiate closing the final decryption inbox; press <enter>. " y

run_with_neg FINAL_DECRYPT_CLOSE_NEG "inbox close --endpoint-id ${FINAL_DECRYPT_EP} --on-last-consensus-id ${FINAL_DECRYPT_CREATE_CONSENSUS} --from-log ${INBOX_LOG}"
FINAL_DECRYPT_CLOSE_CONSENSUS="${consensus}"

echo
read -p "Next: process inbox and negotiate results; press <enter>. " y

if [ "${PREVIOUS}" = "${KEYID}" ]; then
    UPLOAD="--upload"
else
    UPLOAD=
fi

PROCESS_LOG=/tmp/INBOX_PROCESS_LOG_${NAME}
exe ${CMD} inbox process --peer-id "${MIX_PEER}" --endpoint-id "${FINAL_DECRYPT_EP}" --process-log-file "${PROCESS_LOG}" ${UPLOAD}

run_with_neg FINAL_DECRYPT_PROCESSED_ACK_NEG "processed ack --endpoint-id ${FINAL_DECRYPT_EP} --on-last-consensus-id ${FINAL_DECRYPT_CLOSE_CONSENSUS} --from-log ${PROCESS_LOG}"

exe ${CMD} outbox list --endpoint-id "${FINAL_DECRYPT_EP}"

echo
read -p "Next: upload results to booth endpoint and publish; press <enter>. " y

PROCESS_LOG=/tmp/INBOX_PROCESS_LOG_${NAME}
rm ${PROCESS_LOG}
run_if_not_file "processed get --endpoint-id ${INBOX_EP} --hashes-log-file ${PROCESS_LOG} --serialized ${DRY_RUN}" "${PROCESS_LOG}"

run_with_neg INBOX_PROCESSED_ACK_NEG "processed ack --endpoint-id ${INBOX_EP} --on-last-consensus-id ${BOOTH_CLOSE_CONSENSUS} --from-log ${PROCESS_LOG}"

exe ${CMD} outbox list --endpoint-id "${INBOX_EP}"
