import os
import time

from panoramix.config import cfg, config_file, ENV_CONFIG
from panoramix.client import PanoramixClient
from panoramix import ui_term, ui_web
ui_mods = {
    'ui_term': ui_term,
    'ui_web': ui_web,
}

ui_choice = os.environ.get('PANORAMIX_UI_MODULE', 'ui_term')
ui = ui_mods.get(ui_choice, 'ui_term')


BACKENDS = {
    "ZEUS": "panoramix.backends.zeus_backend",
    "SPHINXMIX": "panoramix.backends.sphinxmix_backend",
    # "GPG": "panoramix.backends.gpg_backend",
}


def abort(text=None):
    if text:
        ui.inform(text)
    ui.inform("Aborted.")
    exit()


client = PanoramixClient()


INTERVAL = 1


class Block(BaseException):
    pass


def retry(action):
    def inner():
        message = None
        while True:
            try:
                return action()
            except Block as e:
                if e.message != message:
                    message = e.message
                    ui.inform(message)
                time.sleep(INTERVAL)
    return inner


def on(setting, action):
    print "ON %s" % setting
    value = cfg.get(setting)
    if value is None:
        value = action()
        cfg.set_value(setting, value)
    return value


def select_backend_wizard():
    default = "SPHINXMIX"
    name = ui.ask_value(
        "backend",
        "Select backend, one of %s (default: '%s')"
        % (", ".join(BACKENDS.keys()), default))
    if not name:
        name = default
    return BACKENDS[name]


def set_key_wizard():
    default = "create"
    response = ui.ask_value("action",
                            "No key available. Choose 'set' or 'create' "
                            "(default: '%s')" % default)
    if not response:
        response = default
    if response == "create":
        crypto_params = cfg.get("CRYPTO_PARAMS")
        key_settings = client.backend.create_key_settings(crypto_params)
        ui.inform("Created key with values: %s" % key_settings)
    elif response == "set":
        key_settings = {}
        for name in client.backend.KEY_SETTING_NAMES:
            value = ui.ask_value(name, "Set '%s'" % name)
            key_settings[name] = value
    else:
        raise ValueError()
    return key_settings


def crypto_params_wizard_on(obj):
    default_crypto_params = obj.backend.get_default_crypto_params()
    crypto_params = {}
    for key, default_value in default_crypto_params.iteritems():
        typ = type(default_value)
        response = ui.ask_value(key,
                                ("Set %s (default: '%s')" %
                                 (key, default_value)))
        crypto_params[key] = typ(response) if response else default_value
    return crypto_params
