from panoramix.wizard_common import abort, client, ui, cfg, on
from panoramix import wizard_common as common
from panoramix import canonical
from panoramix.agent import agent

TYPE = "SPHINXMIX"


def split_mixnet_url(mixnet_url):
    url = mixnet_url.rstrip('/')
    segments = url.rsplit('/', 3)
    if len(segments) != 4:
        abort()
    [catalog_url, prefix, resources, endpoint_id] = segments
    return catalog_url, endpoint_id


def mixnet_url_process(mixnet_url):
    catalog_url, endpoint_id = split_mixnet_url(mixnet_url)
    cfg.set_value("CATALOG_URL", catalog_url)
    client.register_catalog_url(catalog_url)
    print endpoint_id
    endpoint = client.endpoint_info(endpoint_id)
    if endpoint["status"] != "OPEN":
        abort("Endpoint is not open.")
    if endpoint["endpoint_type"] != "SPHINXMIX_GATEWAY":
        abort("Not a SPHINXMIX_GATEWAY.")

    peer_id = endpoint["peer_id"]
    cfg.set_value("PEER_ID", peer_id)
    peer = client.peer_info(peer_id)

    assert peer["crypto_backend"] == TYPE
    backend = common.BACKENDS[TYPE]
    client.register_backend(backend)
    cfg.set_value("CRYPTO_BACKEND", backend)
    crypto_params = canonical.from_unicode_canonical(peer["crypto_params"])
    cfg.set_value("CRYPTO_PARAMS", crypto_params)

    description = {"gateway": endpoint,
                   "mixnet_peer": peer}
    cfg.set_value("MIXNET_DESCRIPTION", description)


def main(text=None, recipient=None):
    import os
    ui.inform("Welcome to Panoramix sphinxmix agent!")
    ui.inform("Configuration file is: %s" % common.config_file)
    ui.inform("Set PANORAMIX_CONFIG environment variable to override")
    url = on("MIXNET_URL",
             lambda: ui.ask_value("MIXNET_URL", "Give sphinxmix mixnet URL"))
    mixnet_url_process(url)
    on("KEY", common.set_key_wizard)
    agent.main()

if __name__ == "__main__":
    main()
