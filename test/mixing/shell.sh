#!/bin/bash

set -x
WORKSPACE='/tmp/panoramix_mixing_test'

export PANORAMIX_DATABASE=${WORKSPACE}/panoramix_db.sqlite3

PANORAMIX_CONFIG=${WORKSPACE}/server panoramix-manage shell
