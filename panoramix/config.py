import os
import json
import importlib


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
        return json.loads(cfg_s) if cfg_s else {}

    def cfg(self):
        if self._cfg is None:
            self._cfg = self.load()
        return self._cfg

    def get(self, key, default=None):
        return self.cfg().get(key, default)

    def save(self):
        _cfg = self._cfg
        if _cfg is None:
            return
        with open(self.config_file, "w") as f:
            json.dump(_cfg, f)

    def set_value(self, key, value):
        cfg = self.cfg()
        cfg[key] = value
        self.save()

    def copy_to(self, key):
        return lambda value: self.set_value(key, value)

    def remove(self, key):
        cfg = self.cfg()
        cfg.pop(key)
        self.save()


ENVVARIABLE = "PANORAMIX_CONFIG"
config_file = os.environ.get(ENVVARIABLE)
if config_file is None:
    print "You must specify the configuration file with the "\
    "PANORAMIX_CONFIG environment variable."
    exit()

cfg = Config(config_file)


def get_backend():
    CRYPTO_BACKEND = cfg.get("CRYPTO_BACKEND")
    if CRYPTO_BACKEND is None:
        raise ValueError("CRYPTO_BACKEND is not set.")
    return importlib.import_module(CRYPTO_BACKEND)


def get_server_backend():
    crypto_module = get_backend()
    return crypto_module.get_server(cfg)
