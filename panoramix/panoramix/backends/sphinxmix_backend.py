from binascii import unhexlify
import base64
from hashlib import sha256

from petlib import ecdsa, ec, bn
from sphinxmix import SphinxParams, SphinxClient, SphinxNode

from panoramix import canonical, utils, interface

BACKEND_NAME = "SPHINXMIX"


ENDPOINT_TYPES = [
    "SPHINXMIX_GATEWAY",
    "SPHINXMIX",
]


def mk_contributing_endpoint_id(peer_id, mixnet_id):
    return "%s_for_ep_%s" % (peer_id[:7], mixnet_id)


def compute_input_from(for_peer_id, owners, combined_endpoint_id):
    index = owners.index(for_peer_id)
    if index == 0:
        return combined_endpoint_id
    previous = mk_contributing_endpoint_id(
        owners[index - 1], combined_endpoint_id)
    return previous


def make_description(mixnet_name, combined_peer_id, owners, admin, size_min):
    endpoint_params = canonical.to_canonical({})
    in_endpoint = {
        "endpoint_id": mixnet_name,
        "peer_id": combined_peer_id,
        "endpoint_type": "SPHINXMIX_GATEWAY",
        "endpoint_params": endpoint_params,
        "public": True,
        "description": "Gateway for mixnet '%s'" % mixnet_name,
        "admin": admin,
    }

    link = {
        "from_endpoint_id": mk_contributing_endpoint_id(owners[-1], mixnet_name),
        "from_state": 'ACCEPTED',
    }
    out_endpoint = {
        "endpoint_id": mixnet_name + '_output',
        "peer_id": combined_peer_id,
        "endpoint_type": "SPHINXMIX_OUTPUT",
        "endpoint_params": endpoint_params,
        "public": True,
        "description": "Output of mixnet '%s'" % mixnet_name,
        "link": link,
        "admin": admin,
    }

    mix_endpoints = {}
    for peer_id in owners:
        endpoint_id = mk_contributing_endpoint_id(peer_id, mixnet_name)
        from_endpoint = compute_input_from(
            peer_id, owners, mixnet_name)
        link = {
            "from_endpoint_id": from_endpoint,
            "from_state": 'ACCEPTED',
        }
        mix_endpoints[peer_id] = {
            "endpoint_id": endpoint_id,
            "peer_id": peer_id,
            "endpoint_type": "SPHINXMIX",
            "endpoint_params": endpoint_params,
            "description": "Mixing node for '%s'" % mixnet_name,
            "public": False,
            "link": link,
            "admin": peer_id,
        }

    spec = {
        'input': in_endpoint,
        'output': out_endpoint,
        'mix_endpoints': mix_endpoints,
        'size_min': size_min,
    }
    return spec


REQUIRED_PARAMS = {}


def make_sphinxmix_params(crypto_params):
    GROUP = crypto_params["GROUP"]
    HEADER_LEN = crypto_params["HEADER_LEN"]
    BODY_LEN = crypto_params["BODY_LEN"]
    group = SphinxParams.Group_ECC(GROUP)
    return SphinxParams.SphinxParams(
        group=group, header_len=HEADER_LEN, body_len=BODY_LEN)


def mk_EcPt(hexvalue, params):
    return ec.EcPt.from_binary(unhexlify(hexvalue), params.group.G)


def bn_encode(num):
    return num.hex()


def bn_decode(s):
    return bn.Bn.from_hex(s)


def get_key_id_from_key_data(key_data):
    return str(key_data)


def sign(body, params, secret, public):
    digest = sha256(body).digest()
    sig = ecdsa.do_ecdsa_sign(params.group.G, secret, digest)
    sig = tuple(map(bn_encode, sig))
    signature = {
        "r": sig[0],
        "s": sig[1],
        "public": public,
    }
    return canonical.to_canonical(signature)


def verify(mixnet_data, signature, params):
    signature = canonical.from_unicode_canonical(signature)
    digest = sha256(mixnet_data).digest()
    sig = tuple(map(bn_decode, (signature["r"], signature["s"])))
    ver_key = mk_EcPt(signature["public"], params)
    valid = ecdsa.do_ecdsa_verify(params.group.G, ver_key, sig, digest)
    key_id = get_key_id_from_key_data(ver_key)
    return valid, key_id


def encode_header(header):
    alpha, beta, gamma = header
    return str(alpha), base64.b64encode(beta), base64.b64encode(gamma)


def decode_header(header, params):
    alpha, beta, gamma = header
    return (mk_EcPt(alpha, params),
            base64.b64decode(beta),
            base64.b64decode(gamma))


def encode_delta(delta):
    return base64.b64encode(delta)


def decode_delta(delta):
    return base64.b64decode(delta)


def mk_message(header, delta):
    return {"header": encode_header(header),
            "delta": encode_delta(delta)}


def unpack_message(message, params):
    header = message["header"]
    delta = message["delta"]
    return decode_header(header, params), decode_delta(delta)


def encode_message(message):
    return canonical.to_canonical(message)


def decode_message(message):
    return canonical.from_unicode_canonical(message)


def encrypt(data, recipients, params):
    dest = recipients[-1]
    routers = recipients[:-1]
    nodes_routing = [SphinxClient.Nenc(router) for router in routers]
    router_keys = [mk_EcPt(router, params) for router in routers]
    header, delta = SphinxClient.create_forward_message(
        params, nodes_routing, router_keys, dest, data)
    message = mk_message(header, delta)
    return encode_message(message)


def process_message(message, params, secret):
    header, delta = unpack_message(message, params)
    return SphinxNode.sphinx_process(params, secret, header, delta)


def route_message(info, header, delta, mac_key, params):
    routing = SphinxClient.PFdecode(params, info)
    flag = routing[0]
    if flag == SphinxClient.Relay_flag:
        recipient = routing[1]
        return recipient, encode_message(mk_message(header, delta))
    elif flag == SphinxClient.Dest_flag:
        return tuple(SphinxClient.receive_forward(params, mac_key, delta))
    raise ValueError("Unrecognized flag")


def process_sphinxmix(enc_messages, params, secret):
    enc_messages = [m["text"] for m in enc_messages]
    utils.secure_shuffle(enc_messages)
    processed = []
    for message in enc_messages:
        decoded = decode_message(message)
        (tag, info, (header, delta), mac_key) = process_message(
            decoded, params, secret)
        recipient, processed_message = route_message(
            info, header, delta, mac_key, params)
        processed.append((recipient, processed_message))
    return processed, None


class Server(object):
    def __init__(self, crypto_params):
        self.params = make_sphinxmix_params(crypto_params)

    def verify(self, mixnet_data, signature, public=None):
        return verify(mixnet_data, signature, self.params)

    def register_key(self, key_data):
        pass


def get_server(config):
    crypto_params = config.get("CRYPTO_PARAMS")
    return Server(crypto_params)


def get_owners_sorted(peer):
    owner_ids = []
    for owner in peer["owners"]:
        owner_id = owner["owner_key_id"]
        owner_ids.append(owner_id)
    owner_ids.sort()
    return owner_ids


class SphinxmixMixnet(interface.Mixnet):
    def __init__(self, description):
        self.description = description
        self.gateway = description["gateway"]
        self.mixnet_peer = description["mixnet_peer"]
        self.owners = get_owners_sorted(self.mixnet_peer)
        self.known_peers = self.owners + [self.mixnet_peer["peer_id"]]


mixnet_class = SphinxmixMixnet
key_type = 18


class Client(object):
    def __init__(self, crypto_params, public, secret):
        self._crypto_params = crypto_params
        self.params = make_sphinxmix_params(crypto_params)
        self.public = public
        self.secret = bn_decode(secret)
        self.key_id = public

    def get_key_data(self):
        return self.public

    def get_keyid(self):
        return self.key_id

    def get_key_info(self):
        return {'public': self.public,
                'key_id': self.key_id}

    def get_key_type(self):
        return 18

    def get_crypto_params(self):
        return canonical.to_canonical(self._crypto_params)

    def get_key_id_from_key_data(self, key_data):
        return get_key_id_from_key_data(key_data)

    def register_key(self, key_data):
        pass

    def sign(self, body):
        return sign(body, self.params, self.secret, self.public)

    def combine_keys(self, keys):
        # WARNING: not checked for cryptographic correctness;
        # used only to produce a common identifier
        publics = [mk_EcPt(key, self.params) for key in keys]
        result = ec.EcPt(self.params.group.G)
        for public in publics:
            result = result + public
        return str(result)

    def encrypt(self, data, recipients):
        return encrypt(data, recipients, self.params)

    def decide_route(self, mixers, recipient):
        return mixers + [recipient]

    def prepare_message(self, mixnet_peer, mixers, recipient, message):
        route = self.decide_route(mixers, recipient)
        enc_data = self.encrypt(message, route)
        sender = self.get_keyid()
        return {'sender': sender, 'recipient': mixnet_peer, 'text': enc_data}

    def process(self, endpoint, messages):
        endpoint_type = endpoint["endpoint_type"]
        if endpoint_type == "SPHINXMIX":
            return process_sphinxmix(messages, self.params, self.secret)
        if endpoint_type == "SPHINXMIX_GATEWAY":
            raise utils.NoProcessing(endpoint_type)
        if endpoint_type == "SPHINXMIX_OUTPUT":
            raise utils.NoProcessing(endpoint_type)
        raise ValueError("Unsupported endpoint type")


def get_client(config):
    crypto_params = config.get("CRYPTO_PARAMS")
    key_settings = config.get("KEY", {})
    public = key_settings.get("PUBLIC")
    secret = key_settings.get("SECRET")
    return Client(crypto_params, public, secret)


def get_default_crypto_params():
    return {"GROUP": 713,
            "HEADER_LEN": 192,
            "BODY_LEN": 1024}


def create_key(params):
    secret = params.group.gensecret()
    public = params.group.expon(params.group.g, [secret])
    return secret, public


KEY_SETTING_NAMES = ["SECRET", "PUBLIC"]


def create_key_settings(crypto_params):
    params = make_sphinxmix_params(crypto_params)
    secret, public = create_key(params)
    secret = bn_encode(secret)
    public = str(public)
    return {"SECRET": secret, "PUBLIC": public}
