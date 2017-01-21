from panoramix.config import cfg


def inform(message):
    pass


def ask_value(title, description):
    value = cfg.get(title, None)
    if value is not None:
        return value

    cfg.set_value(title, None, description=description)
    raise StopIteration


def get_values():
    return cfg.cfg()
