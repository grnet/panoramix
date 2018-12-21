import os
import json
import requests
from panoramix.config import cfg, config_file, ENV_CONFIG
from panoramix import ui_term, ui_web
from panoramix.backends import sphinxmix_backend


ui_mods = {
    'ui_term': ui_term,
    'ui_web': ui_web,
}

ui_choice = os.environ.get('PANORAMIX_UI_MODULE', 'ui_term')
ui = ui_mods.get(ui_choice, 'ui_term')

def on(setting, action):
    print "ON %s" % setting
    value = cfg.get(setting)
    if value is None:
        value = action()
        cfg.set_value(setting, value)
    return value


def abort(text=None):
    if text:
        ui.inform(text)
    ui.inform("Aborted.")
    exit()


def join_urls(*args):
    """
    Join arguments into a url.

    >>> join_urls("http://www.test.org", "path")
    'http://www.test.org/path'
    >>> join_urls("http://www.test.org/", "path")
    'http://www.test.org/path'
    >>> join_urls("http://www.test.org", "/path")
    'http://www.test.org/path'
    >>> join_urls("http://www.test.org/", "/path")
    'http://www.test.org/path'
    >>> join_urls("http://www.test.org/", "/path/")
    'http://www.test.org/path/'
    >>> join_urls("http://www.test.org/a/b", "c/d")
    'http://www.test.org/a/b/c/d'
    >>> join_urls("http://www.test.org/a/b/", "c/d")
    'http://www.test.org/a/b/c/d'
    >>> join_urls("http://www.test.org/a/b", "/c/d")
    'http://www.test.org/a/b/c/d'
    >>> join_urls("http://www.test.org/a/b/", "/c/d")
    'http://www.test.org/a/b/c/d'
    >>> join_urls("http://www.test.org/a/b/", "/c/d/", "/e/f/")
    'http://www.test.org/a/b/c/d/e/f/'
    >>> join_urls("/path1", "/path")
    '/path1/path'
    >>> join_urls("path1", "/path")
    'path1/path'
    >>> join_urls("path1/")
    'path1/'
    >>> join_urls("path1/", "path2", "path3")
    'path1/path2/path3'
    >>> join_urls("", "path2", "path3")
    'path2/path3'
    >>> join_urls("", "", "")
    ''
    """
    args = filter(bool, args)

    if len(args) == 0:
        return ''

    if len(args) == 1:
        return args[0]

    return "/".join([args[0].rstrip("/")] +
                    [a.strip("/") for a in args[1:-1]] +
                    [args[-1].lstrip("/")])


def pick_subdict(keys, spec):
    keys = set(keys)
    return {key:val for key, val in spec.iteritems() if key in keys}


class RestClient(object):
    def __init__(self, api_url, collection):
        self.endpoint = join_urls(api_url, collection, '/')

    def filled_endpoint(self, ref):
        if ref is None:
            return self.endpoint
        return self.endpoint % ref

    def create(self, data, ref=None):
        endpoint = self.filled_endpoint(ref)
        return requests.post(endpoint, json=data)

    def list(self, params, ref=None):
        endpoint = self.filled_endpoint(ref)
        return requests.get(endpoint, params)

    def get(self, resource_id, ref=None):
        endpoint = self.filled_endpoint(ref)
        return requests.get(join_urls(endpoint, resource_id, '/'))

    def partial_update(self, resource_id, data, ref=None):
        endpoint = self.filled_endpoint(ref)
        return requests.patch(join_urls(endpoint, resource_id, '/'), json=data)

    def custom_post(self, suffix, resource_id, data, ref=None):
        endpoint = self.filled_endpoint(ref)
        return requests.post(join_urls(endpoint, resource_id, suffix, '/'),
                             json=data)


class SphinxmixClient(object):
    def register_catalog_url(self, api_url):
        self.api_url = api_url
        self.peers = RestClient(api_url, 'peers')
        self.endpoints = RestClient(api_url, 'endpoints')
        self.cycles = RestClient(api_url, 'endpoints/%s/cycles')
        self.messages = RestClient(api_url, 'endpoints/%s/messages')

    def register_crypto_client(self, cfg):
        self.crypto_client = sphinxmix_backend.get_client(cfg)

    def peer_create(self, name, crypto_params, key_data, owners=None):
        if owners is None:
            owners = []

        owners_data = []
        for i, owner in enumerate(owners):
            owners_data.append(
                {'position': i,
                 'owner_key_id': owner})

        crypto_params = json.dumps(crypto_params)
        data = {
            'name': name,
            'peer_id': key_data,
            'key_data': key_data,
            'key_type': sphinxmix_backend.key_type,
            'crypto_backend': sphinxmix_backend.BACKEND_NAME,
            'crypto_params': crypto_params,
            'owners': owners_data,
        }
        r = self.peers.create(data)
        if r.status_code != 201:
            raise Exception(r.content)
        return r.json()

    def peer_create_combined(self, name, crypto_params, owners):
        key_data = self.crypto_client.combine_keys(owners)
        return self.peer_create(name, crypto_params, key_data, owners)

    def get_owners(self, peer):
        owners_data = peer['owners']
        owners_data = sorted(owners_data, key=lambda data:data['position'])
        return [data['owner_key_id'] for data in owners_data]

    def peer_get(self, peer_id):
        r = self.peers.get(peer_id)
        if r.status_code != 200:
            raise Exception(r.content)
        return r.json()

    def endpoint_create(self, spec):
        keys = [
            'endpoint_id',
            'peer_id',
            'description',
            'endpoint_type',
            'endpoint_params',
            'public',
        ]
        data = pick_subdict(keys, spec)
        r = self.endpoints.create(data)
        if r.status_code != 201:
            raise Exception(r.content)
        return r.json()

    def endpoint_get(self, endpoint_id):
        r = self.endpoints.get(endpoint_id)
        if r.status_code != 200:
            raise Exception(r.content)
        return r.json()

    def cycle_create(self, endpoint_id):
        r = self.cycles.create({}, ref=endpoint_id)
        if r.status_code != 201:
            raise Exception(r.content)
        return r.json()

    def cycle_get(self, endpoint_id, current_cycle):
        r = self.cycles.get(str(current_cycle), ref=endpoint_id)
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise Exception(r.content)
        return r.json()

    def cycle_list(self, endpoint_id, state=None):
        params = {}
        if state is not None:
            params['flt__state'] = state
        r = self.cycles.list(params, ref=endpoint_id)
        if r.status_code != 200:
            raise Exception(r.content)
        return r.json()

    def cycle_bulk_upload(self, endpoint_id, cycle, messages):
        keys = ['sender', 'recipient', 'text', 'state']
        data = [pick_subdict(keys, msg) for msg in messages]
        data = {'messages': data}
        r = self.cycles.custom_post(
            'bulk-upload', str(cycle), data, ref=endpoint_id)
        if r.status_code != 201:
            raise Exception(r.content)
        return r.json()

    def cycle_purge(self, endpoint_id, cycle):
        r = self.cycles.custom_post('purge', str(cycle), {}, ref=endpoint_id)
        if r.status_code != 200:
            raise Exception(r.content)
        return r.json()

    def cycle_set_state(self, endpoint_id, cycle, state):
        data = {'state': state}
        r = self.cycles.partial_update(str(cycle), data, ref=endpoint_id)
        if r.status_code != 200:
            raise Exception(r.content)
        return r.json()

    def cycle_set_all_message_state(self, endpoint_id, cycle, state):
        data ={'messages': [{'id': -1, 'state': state}]}
        r = self.cycles.custom_post(
            'set-message-state', str(cycle), data, ref=endpoint_id)
        if r.status_code != 200:
            raise Exception(r.content)
        return r.json()

    def messages_list(self, endpoint_id, state=None, cycle=None):
        params = {}
        if state is not None:
            params['flt__state'] = state
        if cycle is not None:
            params['flt__cycle'] = cycle
        r = self.messages.list(params, ref=endpoint_id)
        if r.status_code != 200:
            raise Exception(r.content)
        return r.json()

    def message_send(self, endpoint_id, mixnet_peer, mixers, text, recipient):
        data = self.crypto_client.prepare_message(
            mixnet_peer, mixers, recipient, text)
        r = self.messages.create(data, ref=endpoint_id)
        if r.status_code != 201:
            raise Exception(r.content)
        return r.json()


def set_key_wizard():
    default = "create"
    response = ui.ask_value("action",
                            "No key available. Choose 'set' or 'create' "
                            "(default: '%s')" % default)
    if not response:
        response = default
    if response == "create":
        crypto_params = cfg.get("CRYPTO_PARAMS")
        key_settings = sphinxmix_backend.create_key_settings(crypto_params)
        ui.inform("Created key with values: %s" % key_settings)
    elif response == "set":
        key_settings = {}
        for name in sphinxmix_backend.KEY_SETTING_NAMES:
            value = ui.ask_value(name, "Set '%s'" % name)
            key_settings[name] = value
    else:
        raise ValueError()
    return key_settings
