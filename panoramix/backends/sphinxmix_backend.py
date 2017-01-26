from binascii import unhexlify
import base64
from hashlib import sha1
import random

from petlib import ecdsa, ec, bn
try:
    from sphinxmix import SphinxParams, SphinxClient, SphinxNode
except ImportError:
    raise ImportError("sphinxmix backend needs sphinxmix library")

from panoramix import canonical, utils

BACKEND_NAME = "SPHINXMIX"


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
    digest = sha1(body).digest()
    sig = ecdsa.do_ecdsa_sign(params.group.G, secret, digest)
    sig = tuple(map(bn_encode, sig))
    signature = {
        "r": sig[0],
        "s": sig[1],
        "public": public,
    }
    return canonical.to_canonical(signature)


def verify(mixnet_data, signature, params):
    signature = canonical.from_canonical(canonical.from_unicode(signature))
    digest = sha1(mixnet_data).digest()
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
    return canonical.from_canonical(utils.from_unicode(message))


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


def route_message(info, header, delta, params):
    routing = SphinxClient.PFdecode(params, info)
    flag = routing[0]
    if flag == SphinxClient.Relay_flag:
        recipient = routing[1]
        return recipient, mk_message(header, delta)
    elif flag == SphinxClient.Dest_flag:
        return tuple(SphinxClient.receive_forward(params, delta))
    raise ValueError("Unrecognized flag")


def process_sphinxmix(enc_messages, params, secret):
    random.shuffle(enc_messages)
    processed = []
    for message in enc_messages:
        decoded = decode_message(message)
        (tag, info, (header, delta)) = process_message(decoded, params, secret)
        recipient, processed_message = route_message(
            info, header, delta, params)
        processed.append((recipient, encode_message(processed_message)))
    return processed, None


class Server(object):
    def __init__(self, crypto_params):
        self.params = make_sphinxmix_params(crypto_params)

    def verify(self, mixnet_data, signature, public=None):
        return verify(mixnet_data, signature, self.params)

    def register_key(self, key_data):
        pass


def get_server(config):
    crypto_params = config["CRYPTO_PARAMS"]
    return Server(crypto_params)


class Client(object):
    def __init__(self, crypto_params, public, secret):
        self._crypto_params = crypto_params
        self.params = make_sphinxmix_params(crypto_params)
        self.public = public
        self.secret = bn.Bn.from_hex(secret)
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
        raise NotImplementedError()

    def encrypt(self, data, recipients):
        return encrypt(data, recipients, self.params)

    def process(self, endpoint, messages):
        endpoint_type = endpoint["endpoint_type"]
        if endpoint_type == "SPHINXMIX":
            return process_sphinxmix(messages, self.params, self.secret)
        raise ValueError("Unsupported endpoint type")


def get_client(config):
    crypto_params = config["CRYPTO_PARAMS"]
    public = config["PUBLIC"]
    secret = config["SECRET"]
    return Client(crypto_params, public, secret)
