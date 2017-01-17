#!/bin/bash

OFF=`echo "\033[39;49;22;23;24;27;2m"`
BOLD=`echo "\033[1m"`
RED=`echo "\033[31m"`
GREEN=`echo "\033[32m"`
YELLOW=`echo "\033[33m"`
CYAN=`echo "\033[36m"`
BLUE=`echo "\033[34;1m"`
GREY=`echo "\033[1;30m"`
PURPLE=`echo "\033[0;35m"`
WHITE=`echo "\033[37m"`
NORMAL=`echo $OFF`

error () {
    echo "$@" >&2
    exit 1
}

declare -A CLI_SETTINGS

CLI_SETTINGS[debug]=on
CLI_SETTINGS[info]=on
CLI_SETTINGS[notice]=on
CLI_SETTINGS[log]=on

declare -A CLI_ENV_DEFAULT
declare -A CLI_ENV_PROMPT
declare -A CLI_ENV_PRE_HOOK

cli_list_settings () {
    for key in "${!CLI_SETTINGS[@]}"; do
        echo ="${key}" '"'"${CLI_SETTINGS[$key]}"'"'
    done | sort
}

cli_list_commands () {
    for key in "${!CLI_COMMANDS[@]}"; do
        echo "${key}": "${CLI_COMMANDS[$key]}"
    done | sort
}

declare -A CLI_COMMANDS

CLI_COMMANDS[settings]=cli_list_settings
CLI_COMMANDS[commands]=cli_list_commands

cli_check_setting () {
    local name="$1"
    local check="$2"
    if [ -z "${check}" ]; then
        check="on"
    fi
    if [[ "${CLI_SETTINGS["${name}"]}" =~ ${check} ]]; then
        return 0
    else
        return 1
    fi
}

cli_command () {
    sign="${1:0:1}"
    name="${1:1}"
    args=("${@:1}")

    case "${sign}" in
        "+")
            CLI_SETTINGS["${name}"]=on
            ;;
        "-")
            CLI_SETTINGS[${name}]=off
            ;;
        "=")
            CLI_SETTINGS[${name}]="${args[*]:1}"
            ;;
        "<")
            unset CLI_SETTINGS["${name}"]
            ;;
        "!")
            invocation="${CLI_COMMANDS[${name}]}"
            if [ -n "${invocation}" ]; then
                ${invocation} "${args[@]}"
            fi
            ;;
    esac
}

cli_setenv () {
    local varname="$1"
    local defval="$2"
    local prompt="$3"
    local pre_hook="$4"

    CLI_ENV_DEFAULT["${varname}"]="${defval}"
    CLI_ENV_PROMPT["${varname}"]="${prompt}"
    CLI_ENV_PRE_HOOK["${varname}"]="${pre_hook}"

    export ${varname}="${defval}"
}

cli_printenv () {
    for key in "${!CLI_ENV_DEFAULT[@]}"; do
        echo "${key}" "${CLI_ENV_DEFAULT["${key}"]}"
    done | sort
}

cli_env_get_keys () {
    varname="$1"
    if [ -z "${varname}" ]; then
        varname=ret
    fi
    export ${varname}="${!CLI_ENV_DEFAULT[*]}"
}

cli_getenv () {
    local varname="$1"
    export ${varname}="${CLI_ENV_DEFAULT[${varname}]}"
}

cli_input () {
    local varname="$1"
    local prompt="$2"
    local user_val="$3"
    local val=
    if [ -z "${prompt}" ]; then
        prompt="${CLI_ENV_PROMPT["${varname}"]}"
    fi
    local defval="${CLI_ENV_DEFAULT["${varname}"]}"

    if cli_check_setting log; then
        for entry in "${CLI_LOG[@]}"; do
            level="${entry[1]}"
            invocation="${entry[*]:1}"
            
            if [ -n "${SHOW[${level}]}" ]; then
                echo "${invocation}" >&2
            fi
        done
    fi

    unset input
    while [ -z "${input}" ]; do
        echo -en "${RED}${varname}${WHITE}: "
        echo -e "${YELLOW}${prompt}${WHITE}"
        read -e -p "> " -i "${val}" input

        if [[ "${input[0]}" =~ ^[+=\<\!-]$ ]]; then
            cli_command ${input}
            unset input
        fi
    done
    CLI_ENV_DEFAULT["${varname}"]="${input}"
    export ${varname}="${input}"
}

cli_input_missing () {
    local varnames=("$@")
    local varindex=
    declare -A varindex
    local line=
    local key=
    local val=
    if [ -z "${varnames[*]}" ]; then
        varnames=("${!CLI_ENV_DEFAULT[@]}")
    fi

    for key in "${varnames[@]}"; do
        varindex["${key}"]=1
    done

    while true; do
        unset missing
        local missing=
        declare -A missing
        echo
        for key in "${!CLI_ENV_DEFAULT[@]}"; do
            val="${!key}"
            if [ -n "${varindex["${key}"]}" ]; then
                if [ -z "$val" ]; then
                    val="${CLI_ENV_DEFAULT["${key}"]}"
                fi
                if [ -z "$val" ]; then
                    echo -e "${RED}${key}${WHITE} ${val}"
                    missing["${key}"]=1
                else
                    echo -e "${GREEN}${key}${WHITE} ${val}"
                fi
            else
                if [ -z "$val" ]; then
                    echo -e "${YELLOW}${key}${WHITE} ${val}"
                else
                    echo -e "${GREEN}${key}${WHITE} ${val}"
                fi
            fi
        done

        if [ -z "${missing[*]}" ]; then
            break
        fi

        echo
        echo "You have to configure all missing values above."
        echo
        for key in "${!missing[@]}"; do
            cli_input "${key}"
        done
    done
}

exe () {
    CLI_LOG+="$*"
    echo >&2 "${@:1}"
    "$@"
}

cat_ready_file () {
    while true; do
        if [ ! -f "$1" ]; then
           sleep 0.5
        else
            break
        fi
    done
    cat "$1"
}
