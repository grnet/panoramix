import os
import json
import importlib

CONFIG_FILE = os.environ.get("PANORAMIX_CONFIG",
                             os.path.expanduser("~/.panoramixrc"))

if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE) as f:
        cfg_s = f.read()
else:
    cfg_s = ''

cfg = json.loads(cfg_s) if cfg_s else {}

CRYPTO_BACKEND = cfg["CRYPTO_BACKEND"]
crypto_module = importlib.import_module(CRYPTO_BACKEND)


def get_server_backend():
    return crypto_module.get_server(cfg)


def get_client_backend():
    return crypto_module.get_client(cfg)
