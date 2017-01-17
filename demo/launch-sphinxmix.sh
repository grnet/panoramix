cd "$(dirname "$0")"

export PANORAMIX_CONFIG=$(pwd)/conf/sphinxmix_server.conf
panoramix-manage runserver $1
