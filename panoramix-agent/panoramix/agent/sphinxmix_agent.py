import json
from panoramix.common import ui, on, abort, SphinxmixClient, set_key_wizard
from panoramix.config import cfg, config_file, ENV_CONFIG
from panoramix.agent import agent

TYPE = "SPHINXMIX"

client = SphinxmixClient()


def split_mixnet_url(mixnet_url):
    url = mixnet_url.rstrip('/')
    segments = url.rsplit('/', 2)
    if len(segments) != 3:
        abort()
    [catalog_url, resources, endpoint_id] = segments
    return catalog_url, endpoint_id


def mixnet_url_process(mixnet_url):
    catalog_url, endpoint_id = split_mixnet_url(mixnet_url)
    cfg.set_value("CATALOG_URL", catalog_url)
    client.register_catalog_url(catalog_url)
    cfg.set_value("ENDPOINT_ID", endpoint_id)
    print endpoint_id
    endpoint = client.endpoint_get(endpoint_id)
    if endpoint["endpoint_type"] != "SPHINXMIX_GATEWAY":
        abort("Not a SPHINXMIX_GATEWAY.")

    peer_id = endpoint["peer_id"]
    cfg.set_value("MIXNET_ID", peer_id)
    peer = client.peer_get(peer_id)

    assert peer["crypto_backend"] == TYPE
    print peer['crypto_params']
    crypto_params = json.loads(peer["crypto_params"])
    cfg.set_value("CRYPTO_PARAMS", crypto_params)
    cfg.set_value("MIXERS", client.get_owners(peer))


def send_message(text=None, recipient=None):
    if recipient is None:
        recipient = ui.ask_value("recipient", "Message recipient")
    if text is None:
        text = ui.ask_value("text", "Message text")

    message = client.message_send(cfg.get('ENDPOINT_ID'),
                                  cfg.get('MIXNET_ID'),
                                  cfg.get('MIXERS'),
                                  text,
                                  recipient)
    ui.inform("Sent message with id %s" % message['id'])


def main(text=None, recipient=None):
    ui.inform("Welcome to Panoramix sphinxmix agent!")
    ui.inform("Configuration file is: %s" % config_file)
    ui.inform("Set PANORAMIX_CONFIG environment variable to override")
    url = on("MIXNET_URL",
             lambda: ui.ask_value("MIXNET_URL", "Give sphinxmix mixnet URL"))
    mixnet_url_process(url)
    on("KEY", set_key_wizard)
    agent.main()


if __name__ == "__main__":
    main()
