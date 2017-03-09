import os
import gnupg
import re
import shutil

from panoramix import utils

BACKEND_NAME = "GPG"


def write_to_file(s, prefix):
    filename = prefix + utils.hash_string(s)
    filepath = os.path.join("/tmp", filename)
    with open(filepath, "w") as f:
        f.write(s)
    return filepath


def get_key_id_from_key_data(key_data, gpg):
    packets = gpg.list_packets(key_data)
    lines = packets.data.splitlines()
    c = re.compile(r'\tkeyid: (.*)')
    for line in lines:
        m = re.match(c, line)
        if m is not None:
            return m.group(1)


def verify(request, signature, public, working_gpg, gpg_path):
    req_filepath = write_to_file(request, "r")
    sig_filepath = write_to_file(signature, "s")

    if public:
        gpg_homename = "gpg_" + utils.hash_string(signature)[0:10]
        gpg_homepath = os.path.join("/tmp", gpg_homename)
        tmp_gpg = gnupg.GPG(homedir=gpg_homepath, binary=gpg_path)
        tmp_gpg.import_keys(public)
        verif_gpg = tmp_gpg
    else:
        verif_gpg = working_gpg
    with open(req_filepath) as req_file:
        v = verif_gpg.verify_file(req_file, sig_filepath)

    os.remove(req_filepath)
    os.remove(sig_filepath)
    shutil.rmtree(gpg_homepath)
    return v.valid, v.key_id


def register_key(key_data, gpg):
    gpg.import_keys(key_data)


def get_key_info(key_id, gpg):
    keys = gpg.list_keys()
    for key in keys:
        if key["keyid"] == key_id:
            return key
    return None


def get_key_type(key_id, gpg):
    info = get_key_info(key_id, gpg)
    return int(info['algo'])


def combine_keys(key_ids):
    raise NotImplementedError()


def sign(body, gpg, key_id, passphrase):
    sig_obj = gpg.sign(body,
                       default_key=key_id, passphrase=passphrase,
                       clearsign=False, detach=True)
    assert sig_obj.status == 'begin signing'
    return sig_obj.data


def encrypt(data, peer_ids, gpg):
    if len(peer_ids) != 1:
        raise ValueError("only one recipient is allowed")
    peer_id = peer_ids[0]
    enc = gpg.encrypt(data, peer_id)
    assert enc.status == "encryption ok"
    return enc.data


def mix(encrypted_messages):
    utils.secure_shuffle(encrypted_messages)
    return encrypted_messages


def decrypt_one(message, gpg, passphrase):
    decr = gpg.decrypt(message, passphrase=passphrase)
    assert decr.status == 'decryption ok'
    return decr.data


def decrypt(messages, gpg, passphrase):
    return [decrypt_one(message, gpg, passphrase) for message in messages]


def peel_onion(encrypted_messages, gpg, passphrase):
    encrypted_messages = [m["text"] for m in encrypted_messages]
    mixed = mix(encrypted_messages)
    return (utils.with_recipient(decrypt(mixed, gpg, passphrase),
                                 "dummy_recipinet"),
            None)


def gateway(messages):
    recipients_with_text = [(m["recipient"], m["text"]) for m in messages]
    return recipients_with_text, None


class Server(object):
    def __init__(self, gpg_homedir, gpg_path):
        self.GPG_HOMEDIR = gpg_homedir
        self.GPG_PATH = gpg_path
        self.GPG = gnupg.GPG(homedir=gpg_homedir, binary=gpg_path)

    def verify(self, request, signature, public=None):
        return verify(request, signature, public, self.GPG, self.GPG_PATH)

    def register_key(self, key_data):
        register_key(key_data, self.GPG)


def get_server(config):
    GPG_HOMEDIR = config.get("GPG_HOMEDIR")
    GPG_PATH = config.get("GPG_PATH")
    return Server(GPG_HOMEDIR, GPG_PATH)


class Client(object):
    def __init__(self, gpg_homedir, gpg_path, keyid, passphrase):
        self.GPG_HOMEDIR = gpg_homedir
        self.GPG_PATH = gpg_path
        self.GPG = gnupg.GPG(homedir=gpg_homedir, binary=gpg_path)
        self.key_id = keyid
        self.passphrase = passphrase

    def get_key_data(self):
        return self.GPG.export_keys(self.key_id)

    def get_keyid(self):
        return self.key_id

    def get_key_info(self):
        return get_key_info(self.key_id, self.GPG)

    def get_key_type(self):
        return get_key_type(self.key_id, self.GPG)

    def get_crypto_params(self):
        return "GPG"

    def get_key_id_from_key_data(self, key_data):
        return get_key_id_from_key_data(key_data, self.GPG)

    def register_key(self, key_data):
        register_key(key_data, self.GPG)

    def sign(self, body):
        return sign(body, self.GPG, self.key_id, self.passphrase)

    def encrypt(self, data, recipients):
        return encrypt(data, recipients, self.GPG)

    def process(self, endpoint, messages):
        endpoint_type = endpoint["endpoint_type"]
        if endpoint_type == "ONION":
            return peel_onion(messages, self.GPG, self.passphrase)
        if endpoint_type == "GATEWAY":
            return gateway(messages)
        raise ValueError("Unsupported endpoint type")


def get_client(config):
    GPG_HOMEDIR = config.get("GPG_HOMEDIR")
    GPG_PATH = config.get("GPG_PATH")
    key_settings = config.get("KEY", {})
    GPG_KEYID = key_settings.get("GPG_KEYID")
    GPG_PASSPHRASE = key_settings.get("GPG_PASSPHRASE")
    return Client(GPG_HOMEDIR, GPG_PATH, GPG_KEYID, GPG_PASSPHRASE)
