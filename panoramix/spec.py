from collections import namedtuple

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


def achoice(choices, d=None):
    if d is None:
        d = {}
    specs = {
        ".choices": {"allowed": to_choices(choices)}
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


def to_choices(choice_namedtuple):
    return list(choice_namedtuple)


def mk_tuple(name, fields):
    tpl = namedtuple(name, fields)
    return tpl(*fields)


NegotiationStatus = mk_tuple("NegotiationStatus", ["OPEN", "DONE"])
PeerStatus = mk_tuple("PeerStatus", ["READY", "DELETED"])
EndpointStatus = mk_tuple("EndpointStatus",
                          ["OPEN", "FULL", "CLOSED", "PROCESSED"])
Box = mk_tuple("Box", ["INBOX", "ACCEPTED", "PROCESSBOX", "OUTBOX"])


# Key types:
# RSA_ENC_SIG = 1
# RSA_ENC = 2
# RSA_SIG = 3
# ELGAMAL = 16
# DSA = 17
# ELLIPTIC_CURVE = 18
# ECDSA = 19




NEGOTIATIONS = {
    ".cli_commands": {},
    ".collection": {},
    ".drf_collection": DRF("panoramix.models.Negotiation",
                           {"mixins": ["panoramix.functions.NegotiationView"],
                            "filter_fields": ["consensus"]}),
    ".actions": {".create": {},
                 ".retrieve": {},
                 ".list": {}},
    "*": {
        "data": namespaced({
            "id": readonlystring(),
            "text": readonlystring(),
            "status": achoice(NegotiationStatus, {".readonly": {}}),
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
    ".actions": {".create": {},
                 ".retrieve": {},
                 ".list": {}},
    "*": {
        "data": namespaced({
            "negotiation": afield({".ref": {"to": "panoramix/negotiations"},
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


def CONSENSUS_LOGS(choices):
    return afield({
        ".readonly": {},
        ".structarray": {
            "consensus_id": astring(),
            "timestamp": afield({".datetime": {}}),
            "status": achoice(choices),
        }
    })


PEERS = {
    ".cli_commands": {},
    ".collection": {},
    ".drf_collection": DRF("panoramix.models.Peer",
                           {"mixins": ["panoramix.functions.PeerView"]}),
    ".actions": {".list": {},
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
            "status": achoice(PeerStatus, {".required": {}}),
            "consensus_logs": CONSENSUS_LOGS(PeerStatus),
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
    ".actions": {".create": {},
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
                    "to_box": achoice(Box),
                    "from_box": achoice(Box),
                    "from_endpoint_id": astring()}}),  # .initwrite: {}
            "public": aninteger({".required": {}}),
            "status": achoice(EndpointStatus, {".required": {}}),
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
            "consensus_logs": CONSENSUS_LOGS(EndpointStatus),
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
    ".actions": {".create": {},
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
            "box": achoice(Box, {".required": {}}),
            "message_hash": astring({".readonly": {}}),
        }),
        "info": INFO(),
        "meta": META(),
    }
}

SPEC = {
    "panoramix": {
        ".endpoint": {},
        "negotiations": NEGOTIATIONS,
        "contributions": CONTRIBUTIONS,
        "peers": PEERS,
        "endpoints": ENDPOINTS,
        "messages": MESSAGES,
    }
}

ROOT = "http://localhost:8000"
