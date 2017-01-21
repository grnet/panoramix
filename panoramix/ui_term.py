from panoramix.config import cfg


def inform(message):
    print message


def ask_value(title, description):
    prompt = "%s\n%s: " % (description, title)
    value = raw_input(prompt).strip()
    return value


def get_values():
    return cfg.cfg()
