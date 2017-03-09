from panoramix.config import cfg
from panoramix.utils import unicode_to_locale


def inform(message):
    print unicode_to_locale(message)


def ask_value(title, description):
    prompt = "%s\n%s: " % (
        unicode_to_locale(description), unicode_to_locale(title))
    value = raw_input(prompt).strip()
    return value


def get_values():
    return cfg.cfg()
