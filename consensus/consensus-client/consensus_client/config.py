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

    def reload(self):
        self._cfg = self.load()

    def cfg(self):
        if self._cfg is None:
            self._cfg = self.load()
        return self._cfg

    def get_value(self, key, default=None):
        value = self.cfg().get(key)
        return value if value is not None else default

    def save(self):
        _cfg = self._cfg
        if _cfg is None:
            return
        with open(self.config_file, "w") as f:
            json.dump(_cfg, f, indent=2)

    def set_value(self, key, value):
        cfg = self.cfg()
        cfg[key] = value
        self.save()

    def copy_to(self, key):
        return lambda value: self.set_value(key, value)

    def pop(self, key):
        cfg = self.cfg()
        value = cfg.pop(key, None)
        self.save()
        return value
