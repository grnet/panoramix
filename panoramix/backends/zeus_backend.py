import os
import json
from collections import namedtuple

from panoramix.backends import zeus_crypto as core
from panoramix import utils
from panoramix import canonical

BACKEND_NAME = "ZEUS"

ZeusParams = namedtuple("ZeusParams", ["modulus", "generator", "order"])


def make_zeus_params(crypto_params):
    modulus = crypto_params["modulus"]
    generator = crypto_params["generator"]
    order = crypto_params["order"]
    return ZeusParams(modulus, generator, order)


def get_key_id_from_key_data(key_data):
    return unicode(utils.hash_string(key_data))


def verify(mixnet_data, signature, public, params):
    signature = canonical.from_unicode_canonical(signature)
    crypto = signature['crypto']
    modulus = crypto['modulus']
    generator = crypto['generator']
    order = crypto['order']

    if modulus != params.modulus or \
       generator != params.generator or order != params.order:
        raise ValueError("cryptographic parameters mismatch")

    element = core.element_from_texts_hash(
        modulus, generator, order, mixnet_data)
    if element != signature['e']:
        return False, None

    if public is None:
        public_int = signature['public']
        public = utils.int_to_unicode(public_int)
    else:
        public_int = utils.unicode_to_int(public)

    key_id = get_key_id_from_key_data(public)
    valid = bool(core.verify_element_signature(
        signature, modulus, generator, order, public_int))
    return valid, key_id


def sign(body, params, secret, public):
    modulus = params.modulus
    generator = params.generator
    order = params.order
    element = core.element_from_texts_hash(modulus, generator, order, body)
    signature = core.sign_element(element, modulus, generator, order, secret)
    signature['public'] = public
    return canonical.to_canonical(signature)


class Registry(object):
    def __init__(self, registry_path):
        self.registry_path = registry_path

    def _get_registry(self):
        s = None
        if os.path.isfile(self.registry_path):
            with open(self.registry_path, "r") as f:
                s = f.read()
        if not s:
            return {}
        return json.loads(s)

    def _write(self, registry):
        with open(self.registry_path, "w") as f:
            json.dump(registry, f)

    def get_key(self, key_id):
        registry = self._get_registry()
        return registry[key_id]

    def register_key(self, public_key):
        registry = self._get_registry()
        key_id = get_key_id_from_key_data(public_key)
        registry[key_id] = public_key
        self._write(registry)


def make_combined_public(publics, params):
    result = 1
    for public in publics:
        result = (result * public) % params.modulus
    return result


def encrypt(data, recipient_key, params):
    modulus = params.modulus
    generator = params.generator
    order = params.order
    data = int(data)
    [alpha, beta, rnd] = core.encrypt(
        data, modulus, generator, order, recipient_key)
    [commitment, challenge, response] = core.prove_encryption(
        modulus, generator, order, alpha, beta, rnd)
    return encode_message([alpha, beta, commitment, challenge, response])


def get_mixing_input(enc_tuples, params, public):
    mixing_input = {}
    mixing_input['modulus'] = params.modulus
    mixing_input['generator'] = params.generator
    mixing_input['order'] = params.order
    mixing_input['public'] = public

    ciphers = [(m[0], m[1]) for m in enc_tuples]
    mixing_input['mixed_ciphers'] = ciphers
    return mixing_input


def encode_message(message):
    return canonical.to_canonical(message)


def decode_message(message):
    return canonical.from_unicode_canonical(message)


def extract_proof(mixing_output):
    keys = ["challenge",
            "cipher_collections",
            "random_collections",
            "offset_collections"]
    return {key: mixing_output[key] for key in keys}


def get_unique_recipient(messages):
    recipients = set(m["recipient"] for m in messages)
    if len(recipients) != 1:
        raise ValueError("non-unique recipient")
    return recipients.pop()


def process_sk_mix(endpoint, messages, params):
    endpoint_params = canonical.from_unicode_canonical(
        endpoint["endpoint_params"])
    election_public = utils.unicode_to_int(
        endpoint_params["election_public"])

    message_texts = [m["text"] for m in messages]
    recipient = get_unique_recipient(messages)
    mixed_messages, proof = mix(message_texts, params, election_public)
    return utils.with_recipient(mixed_messages, recipient), proof


def mix(enc_messages, params, election_public):
    enc_tuples = [decode_message(m) for m in enc_messages]
    mixing_input = get_mixing_input(enc_tuples, params, election_public)
    mixing_output = core.mix_ciphers(mixing_input)
    mixed_messages = mixing_output.pop('mixed_ciphers')
    proof = extract_proof(mixing_output)
    encoded_mixed_messages = [encode_message(m) for m in mixed_messages]
    return encoded_mixed_messages, proof


def decrypt_one(message, params, secret):
    modulus = params.modulus
    generator = params.generator
    order = params.order
    message = decode_message(message)
    alpha = message[0]
    beta = message[1]
    decr = core.decrypt(modulus, generator, order, secret, alpha, beta)
    return str(decr), None


def process_sk_decrypt(messages, params, secret):
    message_texts = [m["text"] for m in messages]
    recipient = get_unique_recipient(messages)
    decrypted, proof = decrypt(message_texts, params, secret)
    return utils.with_recipient(decrypted, recipient), proof


def decrypt(messages, params, secret):
    cleartexts_with_proofs = [
        decrypt_one(message, params, secret) for message in messages]
    decrypted, proof = utils.unzip(cleartexts_with_proofs)
    return decrypted, proof


def process_sk_partial_decrypt(messages, params, secret):
    message_texts = [m["text"] for m in messages]
    recipient = get_unique_recipient(messages)
    decr_messages, proof = partial_decrypt(message_texts, params, secret)
    return utils.with_recipient(decr_messages, recipient), proof


def partial_decrypt(messages, params, secret):
    modulus = params.modulus
    generator = params.generator
    order = params.order
    ciphers = [decode_message(m) for m in messages]
    factors = core.compute_decryption_factors(
        modulus, generator, order, secret, ciphers, nr_parallel=0)
    betas = [beta for (_, beta) in ciphers]
    result = zip(factors, betas)
    return [encode_message(result)], None


def process_sk_combine(messages, params):
    message_texts = [m["text"] for m in messages]
    recipient = get_unique_recipient(messages)
    combined_messages, proof = combine(message_texts, params)
    return utils.with_recipient(combined_messages, recipient), proof


def combine(messages, params):
    modulus = params.modulus
    generator = params.generator
    order = params.order
    factors_collection_with_betas = [decode_message(m) for m in messages]
    factors_collection = []
    common_betas = None
    for factors_with_betas in factors_collection_with_betas:
        factors, betas = utils.unzip(factors_with_betas)
        factors_collection.append(factors)
        if common_betas is None:
            common_betas = betas
        else:
            if common_betas != betas:
                raise AssertionError("different betas")
    combined_factors = core.combine_decryption_factors(
        modulus, factors_collection)
    results = []
    for combined_factor, beta in zip(combined_factors, common_betas):
        results.append(core.decrypt_with_decryptor(
            modulus, generator, order, beta, combined_factor))
        encoded_results = [encode_message(m) for m in results]
    return encoded_results, None


class Server(object):
    def __init__(self, crypto_params):
        self.params = make_zeus_params(crypto_params)

    def verify(self, mixnet_data, signature, public=None):
        return verify(mixnet_data, signature, public, self.params)

    def register_key(self, key_data):
        pass


def get_server(config):
    CRYPTO_PARAMS = config.get("CRYPTO_PARAMS", core._default_crypto)
    return Server(CRYPTO_PARAMS)


class Client(object):
    def __init__(self, crypto_params, registry_path, public, secret):
        self._crypto_params = crypto_params
        self.params = make_zeus_params(crypto_params)
        self.registry = Registry(registry_path)
        self.public = public
        self.secret = secret
        self.key_id = get_key_id_from_key_data(self.get_key_data())

    def get_key_data(self):
        return utils.int_to_unicode(self.public)

    def get_keyid(self):
        return self.key_id

    def get_key_info(self):
        return {'public': self.public,
                'key_id': self.key_id}

    def get_key_type(self):
        return 16

    def get_crypto_params(self):
        return canonical.to_canonical(self._crypto_params)

    def get_key_id_from_key_data(self, key_data):
        return get_key_id_from_key_data(key_data)

    def register_key(self, key_data):
        return self.registry.register_key(key_data)

    def sign(self, body):
        return sign(body, self.params, self.secret, self.public)

    def combine_keys(self, keys):
        get_key = self.registry.get_key
        publics = [utils.unicode_to_int(get_key(key_id))
                   for key_id in keys]
        return utils.int_to_unicode(make_combined_public(publics, self.params))

    def encrypt(self, data, recipients):
        if len(recipients) != 1:
            raise ValueError("only one recipient is allowed")
        key_id = recipients[0]
        recipient_key = utils.unicode_to_int(self.registry.get_key(key_id))
        return encrypt(data, recipient_key, self.params)

    def process(self, endpoint, messages):
        endpoint_type = endpoint["endpoint_type"]
        if endpoint_type == "ZEUS_BOOTH":
            raise utils.NoProcessing(endpoint_type)
        if endpoint_type == "ZEUS_SK_MIX":
            return process_sk_mix(endpoint, messages, self.params)
        if endpoint_type == "ZEUS_SK_PARTIAL_DECRYPT":
            return process_sk_partial_decrypt(
                messages, self.params, self.secret)
        if endpoint_type == "ZEUS_SK_DECRYPT":
            return process_sk_decrypt(messages, self.params, self.secret)
        if endpoint_type == "ZEUS_SK_COMBINE":
            return process_sk_combine(messages, self.params)
        raise ValueError("Unsupported endpoint type")


ENDPOINT_TYPES = [
    "ZEUS_BOOTH",
    "ZEUS_SK_MIX",
    "ZEUS_SK_PARTIAL_DECRYPT",
    "ZEUS_SK_DECRYPT",
    "ZEUS_SK_COMBINE",
]

REQUIRED_PARAMS = {
    "ZEUS_SK_MIX": ["election_public"],
}


def mk_default_registry_path(public):
    key_id = get_key_id_from_key_data(utils.int_to_unicode(public))
    return os.path.expanduser("~/.panoramixregistry." + key_id)


def get_default_crypto_params():
    return core._default_crypto


def get_client(config):
    crypto_params = config.get("CRYPTO_PARAMS", get_default_crypto_params())
    key_settings = config.get("KEY", {})
    public = key_settings.get("PUBLIC")
    secret = key_settings.get("SECRET")
    registry_path = config.get("REGISTRY_PATH")
    if registry_path is None:
        registry_path = mk_default_registry_path(public)
    return Client(crypto_params, registry_path, public, secret)


def create_key(params, secret=None):
    modulus = params.modulus
    generator = params.generator
    order = params.order
    if secret is None:
        secret = core.get_random_int(1, order)
    secret = secret % order
    public = core.pow(generator, secret, modulus)
    return secret, public


KEY_SETTING_NAMES = ["SECRET", "PUBLIC"]


def create_key_settings(crypto_params):
    params = make_zeus_params(crypto_params)
    secret, public = create_key(params)
    return {"SECRET": secret, "PUBLIC": public}
