if [ -z "${TMPDIR}" ]; then
    TMPDIR=/tmp
fi

SHARE_CHANNEL="${TMPDIR}/demo_share_channel"
rm -rf "${SHARE_CHANNEL}"

rm -f /tmp/panoramix.db.sqlite3; panoramix-manage migrate; rm -rf /tmp/mixnet_gnupg
