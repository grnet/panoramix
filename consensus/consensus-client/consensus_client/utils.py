import base64
import hashlib
import ecdsa
from consensus_client import canonical


def hash_string(s):
    return hashlib.sha256(s).hexdigest()


def hash_with_canonical(obj):
    return hash_string(canonical.to_canonical(obj))


def prepare_text(body, accept):
    meta = {'accept': accept}
    text = {'body': body, 'meta': meta}
    return canonical.to_canonical(text)


def has_accept_meta(text):
    unpacked_text = canonical.from_unicode_canonical(text)
    meta = unpacked_text.get("meta", {})
    return meta.get("accept", False)


def make_ecdsa_signing_key():
    sk = ecdsa.SigningKey.generate()
    return sk.to_pem()


def compute_ecdsa_key_id(vk):
    return hash_string(vk.to_string())


class ECDSAClient(object):
    def __init__(self, secret=None):
        self.secret = secret

        if self.secret:
            self.sk = ecdsa.SigningKey.from_pem(self.secret)
            vk = self.sk.get_verifying_key()
            self.public = vk.to_pem()
            self.key_id = compute_ecdsa_key_id(vk)

    def sign(self, text):
        assert self.secret
        sig = base64.b64encode(self.sk.sign(text))
        return canonical.to_canonical({'sig': sig, 'public': self.public})

    def verify(self, signature, text):
        signature = canonical.from_unicode_canonical(signature)
        sig = base64.b64decode(signature['sig'])
        public = signature['public']
        vk = ecdsa.VerifyingKey.from_pem(public)
        try:
            assert vk.verify(sig, text)
            return compute_ecdsa_key_id(vk)
        except:
            return None
