#!/bin/bash
set -x
cd "$(dirname "$0")"

WORKSPACE='/tmp/consensus_client_test'
rm -rf ${WORKSPACE}
mkdir -p ${WORKSPACE}

export CONSENSUS_DATABASE=${WORKSPACE}/consensus_db.sqlite3

python ../../consensus-service/manage.py migrate
python ../../consensus-service/manage.py runserver 127.0.0.1:8000 --nothreading &
sleep 3

python test.py

echo Killing daemons...
pkill -f 'runserver 127.0.0.1:8000'
