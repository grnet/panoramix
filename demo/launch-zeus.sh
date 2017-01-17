cd "$(dirname "$0")"

export PANORAMIX_CONFIG=$(pwd)/conf/zeus_server.conf
panoramix-manage runserver $1
