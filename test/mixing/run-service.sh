#!/bin/bash

set -x
WORKSPACE='/tmp/panoramix_mixing_test'

export PANORAMIX_DATABASE=${WORKSPACE}/panoramix_db.sqlite3

panoramix-manage migrate

panoramix-manage runserver --nothreading 127.0.0.1:8000
