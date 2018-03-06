#!/bin/bash

set -x
WORKSPACE='/tmp/panoramix_mixing_test'

cd "$(dirname "$0")"
rm -rf ${WORKSPACE}
cp -r config ${WORKSPACE}

./run-service.sh &
sleep 10

./run-admin.sh &
./run-contrib.sh &
./run-client-daemon.sh &
sleep 3

PANORAMIX_CONFIG=${WORKSPACE}/client python mixing.py

echo Killing daemons...
pkill -f panoramix-wizard
pkill -f sphinxmix-agent
pkill -f 'panoramix-manage runserver'
