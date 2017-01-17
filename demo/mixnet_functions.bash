source cli_functions.bash

CMD="panoramix $ARGS"

prepare_neg () {
    local varname="$1"
    local filename="${SHARE_CHANNEL}/negotiations/${varname}"
    if [ ! -f "${filename}" ]; then
        local tmp_negid=$(exe $CMD negotiation create)
        echo creating ${tmp_negid}
        echo "${tmp_negid}" >> "${filename}"
    fi
    export ${varname}="$(head -n 1 "${filename}")"
}

contrib_loop () {
    local negid="$1"
    local contrib=
    while true; do
        export consensus="$(exe ${CMD} negotiation info --negotiation-id=${negid} -f value -c consensus)"
        echo consensus "$consensus"
        if [ "${consensus}" != "None" ]; then
            break
        fi
        echo
        exe ${CMD} contribution list --negotiation-id="${negid}"
        read -p "Enter contribution id to accept (or 'contrib' to make own contribution, or <enter> to review list): " contrib
        if [ "${contrib}" = "contrib" ]; then
            read -p "Command: " COMMAND; echo; exe $CMD $COMMAND;
        elif [ -n "${contrib}" ]; then
            echo; exe $CMD contribution accept --negotiation-id=${negid} --contribution-id=${contrib}
        fi
    done
}

with_self_consensus () {
    COMMAND="$1"
    SELF_NEG="$(exe $CMD negotiation create)"
    exe ${CMD} ${COMMAND} --negotiation-id="${SELF_NEG}" --accept
    contrib_loop "${SELF_NEG}"
    OUTPUT="$(exe ${CMD} ${COMMAND} --consensus-id ${consensus})"
    echo $OUTPUT
    export consensus_result="${OUTPUT}"
}

run_with_neg () {
    NEG_NAME="$1"
    COMMAND="$2"
    prepare_neg "${NEG_NAME}"
    eval negid="\$${NEG_NAME}"
    exe ${CMD} ${COMMAND} --negotiation-id="${negid}"
    contrib_loop "${negid}"
    if [ -f "${SHARE_CHANNEL}/consensus/${consensus}" ]; then
        COMMAND_OUT="$(cat ${SHARE_CHANNEL}/consensus/${consensus})"
    else
        COMMAND_OUT="$(exe ${CMD} ${COMMAND} --consensus-id="${consensus}")"
        echo "${COMMAND_OUT}" | tee "${SHARE_CHANNEL}/consensus/${consensus}"
    fi
    export consensus_result="${COMMAND_OUT}"
}

write_hashes_log () {
    EP="$1"
    FILE="$2"
    exe ${CMD} inbox list --endpoint-id ${EP} -c message_hash -f value | ${CMD} hashes wrap > ${FILE}
}
