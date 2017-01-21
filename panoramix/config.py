import os
import json
import importlib
from collections import OrderedDict


class Config(object):
    def __init__(self, config_file):
        self.config_file = config_file
        self._cfg = None

    def load(self):
        if os.path.exists(self.config_file):
            with open(self.config_file) as f:
                cfg_s = f.read()
        else:
            cfg_s = ''
        return json.loads(cfg_s, object_pairs_hook=OrderedDict)\
            if cfg_s else OrderedDict()

    def cfg(self):
        if self._cfg is None:
            self._cfg = self.load()
        return self._cfg

    def get(self, key, default=None):
        d = self.cfg().get(key)
        if d is None:
            if default is not None:
                return default
            return None
        return d["value"]

    def save(self):
        _cfg = self._cfg
        if _cfg is None:
            return
        with open(self.config_file, "w") as f:
            json.dump(_cfg, f, indent=2)

    def set_value(self, key, value, description=None):
        cfg = self.cfg()
        cfg[key] = {
            "value": value,
            "title": key,
            "description": description
        }
        self.save()

    def copy_to(self, key):
        return lambda value: self.set_value(key, value)

    def pop(self, key):
        cfg = self.cfg()
        d = cfg.pop(key)
        self.save()
        return d["value"]


ENV_HOME = os.environ.get('HOME', '.')
ENV_CONFIG = "PANORAMIX_CONFIG"
config_file = os.environ.get(
    ENV_CONFIG,
    os.path.join(ENV_HOME, '.panoramix.config'))

cfg = Config(config_file)


def get_backend():
    CRYPTO_BACKEND = cfg.get("CRYPTO_BACKEND")
    if CRYPTO_BACKEND is None:
        raise ValueError("CRYPTO_BACKEND is not set.")
    return importlib.import_module(CRYPTO_BACKEND)


def get_server_backend():
    crypto_module = get_backend()
    return crypto_module.get_server(cfg)
