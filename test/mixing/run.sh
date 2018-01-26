#!/bin/bash

set -x
WORKSPACE='/tmp/panoramix_mixing_test'

cd "$(dirname "$0")"
rm -rf ${WORKSPACE}
cp -r config ${WORKSPACE}

export PANORAMIX_DATABASE=${WORKSPACE}/panoramix_db.sqlite3

PANORAMIX_CONFIG=${WORKSPACE}/server panoramix-manage runserver 127.0.0.1:8000 &
sleep 3

PANORAMIX_CONFIG=${WORKSPACE}/coordinator panoramix-wizard &
PANORAMIX_CONFIG=${WORKSPACE}/contributor panoramix-wizard &

PANORAMIX_CONFIG=${WORKSPACE}/client sphinxmix-agent &
sleep 3

PANORAMIX_CONFIG=${WORKSPACE}/client python mixing.py

echo Killing daemons...
pkill -f panoramix-wizard
pkill -f sphinxmix-agent
pkill -f 'panoramix-manage runserver'
