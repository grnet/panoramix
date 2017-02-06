from panoramix.wizard_common import abort, client, ui, cfg
from panoramix import wizard_common as common
import canonical


TYPE = "SPHINXMIX"


def split_mixnet_url(mixnet_url):
    url = mixnet_url.rstrip('/')
    segments = url.rsplit('/', 3)
    if len(segments) != 4:
        abort()
    [catalog_url, prefix, resources, peer_id] = segments
    return catalog_url, peer_id


def mixnet_url_process(mixnet_url):
    catalog_url, peer_id = split_mixnet_url(mixnet_url)
    cfg.set_value("CATALOG_URL", catalog_url)
    client.register_catalog_url(catalog_url)
    cfg.set_value("PEER_ID", peer_id)
    peer = client.peer_info(peer_id)
    assert peer["crypto_backend"] == TYPE
    backend = common.BACKENDS[TYPE]
    client.register_backend(backend)
    cfg.set_value("CRYPTO_BACKEND", backend)
    owner_ids = get_owners_sorted(peer)
    cfg.set_value("OWNER_IDS", owner_ids)
    crypto_params = canonical.from_unicode_canonical(peer["crypto_params"])
    cfg.set_value("CRYPTO_PARAMS", crypto_params)
    endpoint = client.get_open_endpoint_of_peer(peer_id)
    if endpoint is None:
        abort("No open endpoint.")
    cfg.set_value("ENDPOINT_ID", endpoint["endpoint_id"])


def get_owners_sorted(peer):
    owner_ids = []
    for owner in peer["owners"]:
        owner_id = owner["owner_key_id"]
        owner_ids.append(owner_id)
    owner_ids.sort()
    return owner_ids


def register_peer_and_owners():
    peer_id = cfg.get("PEER_ID")
    client.peer_import(peer_id)
    owner_ids = cfg.get("OWNER_IDS")
    for owner_id in owner_ids:
        client.peer_import(owner_id)


def send_message(text=None, recipient=None):
    endpoint_id = cfg.get("ENDPOINT_ID")
    ui.inform("Ready to send message through the endpoint '%s'." % endpoint_id)
    if recipient is None:
        recipient = ui.ask_value("recipient", "Message recipient")
    if text is None:
        text = ui.ask_value("text", "Message text")
    owner_ids = cfg.get("OWNER_IDS")
    recipients = owner_ids + [recipient]
    m = client.message_send(endpoint_id, text, recipients)
    ui.inform("Sent message with id %s" % m["data"]["id"])


def main(text=None, recipient=None):
    import os
    ui.inform("Welcome to Panoramix sphinxmix client!")
    ui.inform("Configuration file is: %s" % common.config_file)
    ui.inform("Set PANORAMIX_CONFIG environment variable to override")
    on("MIXNET_URL",
       lambda: ui.ask_value("MIXNET_URL", "Give sphinxmix mixnet URL"),
       mixnet_url_process)
    on("KEY",
       common.set_key_wizard, lambda _: client.register_crypto_client(cfg))
    register_peer_and_owners()
    send_message(text=text, recipient=recipient)


on = common.on_meta({})

if __name__ == "__main__":
    main()
