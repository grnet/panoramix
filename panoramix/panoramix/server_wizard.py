import importlib

from panoramix.wizard_common import ui, abort, cfg, config_file, on
from panoramix import wizard_common as common


class Server(object):
    backend = None

    def register_backend(self, crypto_backend):
        self.backend = importlib.import_module(crypto_backend)

server = Server()


def inform_migrate():
    ui.inform("You need to setup your database once with\n"
              " panoramix-manage migrate")
    return True


def clean_url(url):
    http, sep, right = url.partition("://")
    if http not in ["http", "https"]:
        abort("Malformed URL")
    return right.rstrip('/')


def inform_launch():
    catalog_url = cfg.get("CATALOG_URL")
    ui.inform("Start server with\n"
              " %s=%s panoramix-manage runserver %s" % (
                  common.ENV_CONFIG, config_file, clean_url(catalog_url)))


def set_catalog_url():
    default = "http://127.0.0.1:8000/"
    description = "Set CATALOG_URL: (enter for default '%s')" % default
    value = ui.ask_value("CATALOG_URL", description)
    return value or default


def main():
    ui.inform("Welcome to Panoramix server wizard!")
    ui.inform("Configuration file is: %s" % config_file)
    ui.inform("Set PANORAMIX_CONFIG environment variable to override")
    on("CATALOG_URL", set_catalog_url)
    backend = on("CRYPTO_BACKEND", common.select_backend_wizard)
    server.register_backend(backend)
    on("CRYPTO_PARAMS", lambda: common.crypto_params_wizard_on(server))
    on("INFORM_MIGRATE", inform_migrate)
    inform_launch()


if __name__ == "__main__":
    main()
