import os
import json
import requests
import time
from panoramix.config import cfg, config_file, ENV_CONFIG
from panoramix.backends import sphinxmix_backend
from panoramix.common import *
from panoramix import utils


client = SphinxmixClient()


def set_catalog_url_wizard():
    default = "http://127.0.0.1:8000/panoramix/"
    response = ui.ask_value("CATALOG_URL",
                            "Set CATALOG_URL (default: '%s')" % default)
    if not response:
        response = default
    return response


def key_and_peer_wizard():
    key = on("KEY", set_key_wizard)
    client.register_crypto_client(cfg)
    name = on("PEER_NAME", lambda: utils.locale_to_unicode(
        ui.ask_value("PEER_NAME", "Specify name to register as peer")))
    params = cfg.get("CRYPTO_PARAMS")
    key_data = key["PUBLIC"]
    peer_id = on("PEER_ID",
                 lambda: client.peer_create(name, params, key_data)['peer_id'])
    ui.inform("PEER_ID = %s" % peer_id)


def create_mixnet_peer(mixers):
    params = cfg.get("CRYPTO_PARAMS")
    peer = client.peer_create_combined('mixnet peer', params, mixers)
    return peer['peer_id']


def get_min_size():
    return int(ui.ask_value("MIN_SIZE", "Specify minimum size"))


def purge_acked_cycles(endpoint_id):
    acked_cycles = client.cycle_list(endpoint_id, 'ACK')
    for cycle_info in acked_cycles:
        cycle = cycle_info['cycle']
        print "PURGING cycle", cycle
        client.cycle_purge(endpoint_id, cycle)
        client.cycle_set_state(endpoint_id, cycle, 'PURGED')


def run_input_endpoint(endpoint_spec, size_min):
    endpoint_id = endpoint_spec['endpoint_id']
    purge_acked_cycles(endpoint_id)
    current_cycle = client.endpoint_get(endpoint_id)['current_cycle']
    print "Running", endpoint_id, 'cycle', current_cycle
    if current_cycle == 0:
        client.cycle_create(endpoint_id)
        current_cycle = client.endpoint_get(endpoint_id)['current_cycle']

    cycle_info = client.cycle_get(endpoint_id, current_cycle)
    message_count = cycle_info['message_count']
    print "Count:", message_count
    if message_count < size_min:
        return

    print 'New cycle'
    client.cycle_create(endpoint_id)
    client.cycle_set_all_message_state(endpoint_id, current_cycle, 'ACCEPTED')
    client.cycle_set_state(endpoint_id, current_cycle, 'READY')


def format_accepted_messages(messages):
    peer_id = cfg.get('PEER_ID')
    formatted = []
    for recipient, text in messages:
        formatted.append({
            'sender': peer_id,
            'recipient': recipient,
            'text': text,
            'state': 'ACCEPTED',
        })
    return formatted


def run_mix_endpoint(endpoint_spec):
    endpoint_id = endpoint_spec['endpoint_id']
    purge_acked_cycles(endpoint_id)
#    size_min = endpoint_spec['size_min']
    current_cycle = client.endpoint_get(endpoint_id)['current_cycle']
    print "Running", endpoint_id, 'cycle', current_cycle
    if current_cycle == 0:
        client.cycle_create(endpoint_id)
        current_cycle = client.endpoint_get(endpoint_id)['current_cycle']

    link = endpoint_spec['link']
    from_endpoint_id = link['from_endpoint_id']
    from_state = link['from_state']
    input_cycle = client.cycle_get(from_endpoint_id, current_cycle)
    print 'Input', input_cycle
    if not input_cycle or input_cycle['state'] != 'READY':
        return

    messages = client.messages_list(
        from_endpoint_id, state=from_state, cycle=current_cycle)
    print "GOT MESSAGES", len(messages)
    endpoint_type = endpoint_spec['endpoint_type']
    if endpoint_type == "SPHINXMIX":
        messages, proof = client.crypto_client.process(endpoint_spec, messages)
        messages = format_accepted_messages(messages)

    print 'New cycle'
    client.cycle_bulk_upload(endpoint_id, current_cycle, messages)
    client.cycle_set_state(from_endpoint_id, current_cycle, 'ACK')
    client.cycle_create(endpoint_id)
    client.cycle_set_state(endpoint_id, current_cycle, 'READY')


def run_mixnet():
    spec = cfg.get('MIXNET_SPEC')
    peer_id = cfg.get("PEER_ID")
    in_endpoint = spec['input']
    if in_endpoint['admin'] == peer_id:
        run_input_endpoint(in_endpoint, spec['size_min'])
    out_endpoint = spec['output']
    if out_endpoint['admin'] == peer_id:
        run_mix_endpoint(out_endpoint)
    mix_endpoint = spec['mix_endpoints'].get(peer_id)
    if mix_endpoint:
        run_mix_endpoint(mix_endpoint)
    time.sleep(3)


def create_endpoint(endpoint_spec):
    client.endpoint_create(endpoint_spec)
    return True


def create_endpoints(spec):
    endpoints = list(spec['mix_endpoints'].values())
    endpoints.append(spec['input'])
    endpoints.append(spec['output'])
    for endpoint in endpoints:
        setting = 'ENDPOINT_%s' % endpoint['endpoint_id']
        on(setting, lambda: create_endpoint(endpoint))


def get_endpoint_url(endpoint_spec):
    return join_urls(cfg.get("CATALOG_URL"),
                     'endpoints',
                     endpoint_spec['endpoint_id'],
                     '/')


def create_mixnet_wizard():
    mixers = on("MIXERS_LIST",
                lambda: ui.ask_value(
                    "MIXERS", "Set mixer ids (comma-separated)").split(','))
    mixnet_id = on("MIXNET_PEER", lambda: create_mixnet_peer(mixers))
    ui.inform('MIXNET_PEER = %s' % mixnet_id)
    mixnet_name = on("MIXNET_NAME", lambda: ui.ask_value(
        "NAME", "Set mixnet name"))
    admin_id = cfg.get("PEER_ID")
    min_size = on("MIN_SIZE", get_min_size)
    spec = on("MIXNET_SPEC",
              lambda: sphinxmix_backend.make_description(
                  mixnet_name, mixnet_id, mixers, admin_id, min_size))
    create_endpoints(spec)


def get_mixnet_peer(endpoint_id):
    return client.endpoint_get(endpoint_id)['peer_id']


def join_mixnet_wizard():
    mixnet_name = on("MIXNET_NAME",
                     lambda: ui.ask_value(
                         "NAME", "Set mixnet name"))
    mixnet_id = on("MIXNET_PEER",
                   lambda: get_mixnet_peer(mixnet_name))
    min_size = on("MIN_SIZE", get_min_size)
    mix_peer = client.peer_get(mixnet_id)
    mixers = mix_peer['owners']
    on("MIXNET_SPEC",
       lambda: sphinxmix_backend.make_description(
           mixnet_name, mixnet_id, mixers, 'admin', min_size))


def crypto_params_wizard():
    default_crypto_params = sphinxmix_backend.get_default_crypto_params()
    crypto_params = {}
    for key, default_value in default_crypto_params.iteritems():
        typ = type(default_value)
        response = ui.ask_value(key,
                                ("Set %s (default: '%s')" %
                                 (key, default_value)))
        crypto_params[key] = typ(response) if response else default_value
    return crypto_params


def main():
    ui.inform("Welcome to Panoramix wizard!")
    ui.inform("Configuration file is: %s" % config_file)
    ui.inform("Set PANORAMIX_CONFIG environment variable to override")
    catalog_url = on("CATALOG_URL", set_catalog_url_wizard)
    client.register_catalog_url(catalog_url)
    crypto_params = on("CREATE_CRYPTO_PARAMS", crypto_params_wizard)
    on("CRYPTO_PARAMS", lambda: crypto_params)
    key_and_peer_wizard()

    role = on("SETUP_ROLE",
              lambda: ui.ask_value("role", "Choose 'admin' or 'contrib' mixnet"))
    if role == 'admin':
        create_mixnet_wizard()
    elif role == 'contrib':
        join_mixnet_wizard()

    spec = cfg.get('MIXNET_SPEC')
    input_endpoint = spec['input']
    ui.inform("Mixnet input endpoint: %s" % get_endpoint_url(input_endpoint))
    output_endpoint = spec['output']
    ui.inform("Mixnet output endpoint: %s" % get_endpoint_url(output_endpoint))

    while True:
        run_mixnet()


if __name__ == "__main__":
    main()
