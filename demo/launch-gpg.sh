cd "$(dirname "$0")"

export PANORAMIX_CONFIG=$(pwd)/conf/gpg_server.conf
panoramix-manage runserver $1
