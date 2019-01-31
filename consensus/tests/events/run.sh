#!/bin/bash
set -x
cd "$(dirname "$0")"

export WORKSPACE='/tmp/consensus_events_test'
rm -rf ${WORKSPACE}
mkdir -p ${WORKSPACE}
cp -r config/* ${WORKSPACE}

export CONSENSUS_DATABASE=${WORKSPACE}/consensus_db.sqlite3

python ../../consensus-service/manage.py migrate
python ../../consensus-service/manage.py runserver 127.0.0.1:8000 --nothreading &
sleep 3

python test.py admin &
python test.py trustee &

python test.py check_done

echo Killing daemons...
pkill -f 'runserver 127.0.0.1:8000'
