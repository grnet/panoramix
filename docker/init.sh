#!/bin/bash

cd /srv/app
./init-consensus.sh

supervisord -c /srv/services.conf -n
