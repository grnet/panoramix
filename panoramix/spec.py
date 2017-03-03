def afield(d=None):
    if d is None:
        d = {}
    r = {
        ".cli_option": {},
        ".field": {},
        ".drf_field": {},
    }
    r.update(d)
    return r


def astring(d=None):
    if d is None:
        d = {}
    specs = {
        ".string": {},
    }
    specs.update(d)
    return afield(specs)


def aninteger(d=None):
    if d is None:
        d = {}
    specs = {
        ".integer": {},
    }
    specs.update(d)
    return afield(specs)


def readonlystring(d=None):
    if d is None:
        d = {}
    specs = {
        ".readonly": {},
        ".string": {},
    }
    specs.update(d)
    return afield(specs)


def INFO():
    return {
        ".field": {},
        ".drf_field": {"onmodel": False},
        ".cli_option": {},
        ".writeonly": {},
        ".struct": {
            "operation": {
                ".field": {},
                ".drf_field": {"onmodel": False},
                ".cli_option": {},
                ".string": {},
                ".required": {},
                ".writeonly": {},
            },
            "resource": {
                ".field": {},
                ".drf_field": {"onmodel": False},
                ".cli_option": {},
                ".string": {},
                ".required": {},
                ".writeonly": {},
            },
            "id": {
                ".field": {},
                ".drf_field": {"onmodel": False},
                ".cli_option": {},
                ".string": {},
                ".writeonly": {},
            },
            "on_last_consensus_id": {
                ".field": {},
                ".drf_field": {"onmodel": False, "default": ""},
                ".cli_option": {},
                ".string": {},
                ".writeonly": {},
            },
        }
    }


def META():
    return {
        ".field": {},
        ".drf_field": {"onmodel": False},
        ".cli_option": {},
        ".writeonly": {},
        ".struct": {
            "signature": {
                ".field": {},
                ".drf_field": {"onmodel": False},
                ".cli_option": {},
                ".string": {},
                ".required": {},
                ".writeonly": {},
            },
            "key_data": {
                ".field": {},
                ".drf_field": {"onmodel": False},
                ".cli_option": {},
                ".string": {},
                ".required": {},
                ".writeonly": {},
            },
        }
    }


def BY_CONSENSUS():
    return {
        ".field": {},
        ".drf_field": {"onmodel": False},
        ".cli_option": {},
        ".writeonly": {},
        ".struct": {
            "consensus_id": {
                ".field": {},
                ".drf_field": {"onmodel": False},
                ".cli_option": {},
                ".string": {},
                ".required": {},
                ".writeonly": {},
            },
            "consensus_type": {
                ".field": {},
                ".drf_field": {"onmodel": False},
                ".cli_option": {},
                ".string": {},
                ".required": {},
                ".writeonly": {},
            },
            "consensus_part": {
                ".field": {},
                ".drf_field": {"onmodel": False},
                ".cli_option": {},
                ".integer": {},
                ".nullable": {},
                ".writeonly": {},
            }
        }
    }


def DRF(model, d=None):
    if d is None:
        d = {}
    r = {
        "model": model,
        "authentication_classes": ["panoramix.auth.Auth"],
        "permission_classes": [],
    }
    r.update(d)
    return r


def namespaced(d):
    return {
        ".field": {},
        ".drf_field": {"onmodel": False},
        ".cli_option": {},
        ".struct": d,
    }


NEGOTIATIONS = {
    ".cli_commands": {},
    ".collection": {},
    ".drf_collection": DRF("panoramix.models.Negotiation",
                           {"mixins": ["panoramix.functions.NegotiationView"],
                            "filter_fields": ["consensus"]}),
    "actions": {".create": {},
                ".retrieve": {},
                ".list": {}},
    "*": {
        "data": namespaced({
            "id": readonlystring(),
            "text": readonlystring(),
            "status": readonlystring(),
            "timestamp": afield({".datetime": {},
                                 ".readonly": {}}),
            "consensus": readonlystring({".nullable": {}}),
            "signings": afield({
                ".readonly": {},
                ".structarray": {
                    "signer_key_id": readonlystring(),
                    "signature": readonlystring(),
                }
            }),
        }),
        "info": INFO(),
        "meta": META(),
    }
}

CONTRIBUTIONS = {
    ".cli_commands": {},
    ".collection": {},
    ".drf_collection": DRF("panoramix.models.Contribution",
                           {"mixins": ["panoramix.functions.ContributionView"],
                            "filter_fields": ["negotiation", "id"]}),
    "actions": {".create": {},
                ".retrieve": {},
                ".list": {}},
    "*": {
        "data": namespaced({
            "negotiation": afield({".ref": {"to": "negotiations"},
                                   ".writeonly": {}}),
            "id": afield({".serial": {}, ".readonly": {}}),
            "text": astring(),
            "latest": afield({".boolean": {}, "readonly": {}}),
            "signer_key_id": astring(),
            "signature": astring(),
        }),
        "info": INFO(),
        "meta": META(),
    }
}


def CONSENSUS_LOGS():
    return afield({
        ".readonly": {},
        ".structarray": {
            "consensus_id": astring(),
            "timestamp": afield({".datetime": {}}),
            "status": astring(),
        }
    })

PEERS = {
    ".cli_commands": {},
    ".collection": {},
    ".drf_collection": DRF("panoramix.models.Peer",
                           {"mixins": ["panoramix.functions.PeerView"]}),
    "actions": {".list": {},
                ".create": {},
                ".retrieve": {}},
    "*": {
        "data": namespaced({
            "peer_id": astring(),  # .initwrite: {}
            "name": astring(),  # .initwrite: {}
            "key_type": aninteger(),  # .initwrite: {}
            "crypto_backend": astring({".blankable": {}}),  # .initwrite: {}
            "crypto_params": astring({".blankable": {}}),  # .initwrite: {}
            "key_data": astring(),  # .initwrite: {}
            "owners": afield({
                ".structarray": {
                    "owner_key_id": astring()}}),  # .initwrite: {}
            "status": astring({".required": {}}),
            "consensus_logs": CONSENSUS_LOGS(),
        }),
        "info": INFO(),
        "meta": META(),
        "by_consensus": BY_CONSENSUS(),
    }
}

ENDPOINTS = {
    ".cli_commands": {},
    ".collection": {},
    ".drf_collection": DRF("panoramix.models.Endpoint",
                           {"mixins": ["panoramix.functions.EndpointView"],
                            "filter_fields": ["peer_id", "status"]}),
    "actions": {".create": {},
                ".list": {},
                ".update": {},
                ".retrieve": {}},
    "*": {
        "data": namespaced({
            "endpoint_id": astring(),  # .initwrite: {}
            "peer_id": astring(),  # .initwrite: {}
            "description": astring({".blankable": {}}),  # .initwrite: {}
            "size_min": aninteger(),  # .initwrite: {}
            "size_max": aninteger(),  # .initwrite: {}
            "endpoint_type": astring(),  # .initwrite: {}
            "endpoint_params": astring(),  # .initwrite: {}
            "links": afield({
                ".structarray": {
                    "to_box": astring(),
                    "from_box": astring(),
                    "from_endpoint_id": astring()}}),  # .initwrite: {}
            "public": aninteger({".required": {}}),
            "status": astring({".required": {}}),
            "process_proof": astring(),
            "message_hashes": {
                ".cli_option": {},
                ".field": {},
                ".drf_field": {"onmodel": False},
                ".writeonly": {},
                ".structarray": {
                    "hash": {
                        ".cli_option": {},
                        ".field": {},
                        ".drf_field": {"onmodel": False},
                        ".string": {},
                        ".writeonly": {},
                    }
                }
            },
            "inbox_hash": readonlystring(),
            "outbox_hash": readonlystring(),
            "consensus_logs": CONSENSUS_LOGS(),
        }),
        "info": INFO(),
        "meta": META(),
        "by_consensus": BY_CONSENSUS(),
    }
}

MESSAGES = {
    ".cli_commands": {},
    ".collection": {},
    ".drf_collection": DRF("panoramix.models.Message",
                           {"mixins": ["panoramix.functions.MessageView"],
                            "filter_fields": ["endpoint_id", "box"]}),
    "actions": {".create": {},
                ".list": {}},
    "*": {
        "data": namespaced({
            "id": afield({".serial": {},
                          ".readonly": {}}),
            "serial": aninteger({".nullable": {}}),
            "endpoint_id": astring({".required": {}}),
            "sender": astring({".required": {}}),
            "recipient": astring({".required": {}}),
            "text": astring({".required": {}}),
            "box": astring({".required": {}}),
            "message_hash": astring({".readonly": {}}),
        }),
        "info": INFO(),
        "meta": META(),
        "by_consensus": BY_CONSENSUS(),
    }
}

SPEC = {
    ".endpoint": {},
    "panoramix": {
        "negotiations": NEGOTIATIONS,
        "contributions": CONTRIBUTIONS,
        "peers": PEERS,
        "endpoints": ENDPOINTS,
        "messages": MESSAGES,
    }
}

ROOT = "http://localhost:8000"
