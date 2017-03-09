from collections import namedtuple


def afield(d=None):
    if d is None:
        d = {}
    r = {
        ".field": {},
        ".drf_field": {},
    }
    r.update(d)
    return r


def type_field(typ, construct=None):
    if construct is None:
        construct = lambda x: x

    def inner(*args, **kwargs):
        value = kwargs.get("value")
        if value is None:
            value = {}
        specs = {typ: construct(value)}
        d = {arg: {} for arg in args}
        specs.update(d)
        return afield(specs)
    return inner


astring = type_field(".string")
atext = type_field(".text")
aninteger = type_field(".integer")
adatetime = type_field(".datetime")
aboolean = type_field(".boolean")
aserial = type_field(".serial")
astruct = type_field(".struct")
astructarray = type_field(".structarray")
aref = type_field(".ref")
achoices = type_field(
    ".choices",
    construct=lambda choices: {"allowed": to_choices(choices)})


def nondb(d, **kwargs):
    drf_field = d[".drf_field"]
    drf_field["onmodel"] = False
    for key, value in kwargs.iteritems():
        drf_field[key] = value
    return d


def INFO():
    return nondb(astruct(".writeonly", value={
        "operation": nondb(astring(".required", ".writeonly")),
        "resource": nondb(astring(".required", ".writeonly")),
        "id": nondb(astring(".writeonly")),
        "on_last_consensus_id": nondb(astring(".writeonly"), default="")
    }))


def META():
    return nondb(astruct(".writeonly", value={
        "signature": nondb(atext(".required", ".writeonly")),
        "key_data": nondb(atext(".required", ".writeonly")),
    }))


def BY_CONSENSUS():
    return nondb(astruct(".writeonly", value={
        "consensus_id": nondb(astring(".required", ".writeonly")),
        "consensus_type": nondb(astring(".required", ".writeonly")),
        "consensus_part": nondb(aninteger(".nullable", ".writeonly")),
    }))


def DRF(model, d=None):
    if d is None:
        d = {}
    r = {
        "model": model,
        "authentication_classes": ["panoramix.server.auth.Auth"],
        "permission_classes": [],
    }
    r.update(d)
    return r


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
    ".collection": {},
    ".drf_collection": DRF("panoramix.server.models.Negotiation",
                           {"mixins":
                            ["panoramix.server.functions.NegotiationView"],
                            "filter_fields": ["consensus"]}),
    ".actions": {".create": {},
                 ".retrieve": {},
                 ".list": {}},
    "*": {
        "data": nondb(astruct(value={
            "id": astring(".readonly"),
            "text": atext(".readonly"),
            "status": achoices(".readonly", value=NegotiationStatus),
            "timestamp": adatetime(".readonly"),
            "consensus": astring(".readonly", ".nullable"),
            "signings": astructarray(".readonly", value={
                    "signer_key_id": astring(".readonly"),
                    "signature": atext(".readonly")}),
        })),
        "info": INFO(),
        "meta": META(),
    }
}

CONTRIBUTIONS = {
    ".collection": {},
    ".drf_collection": DRF("panoramix.server.models.Contribution",
                           {"mixins":
                            ["panoramix.server.functions.ContributionView"],
                            "filter_fields": ["negotiation", "id"]}),
    ".actions": {".create": {},
                 ".retrieve": {},
                 ".list": {}},
    "*": {
        "data": nondb(astruct(value={
            "negotiation": aref(".writeonly",
                                value={"to": "panoramix/negotiations"}),
            "id": aserial(".readonly"),
            "text": atext(),
            "latest": aboolean(".readonly"),
            "signer_key_id": astring(),
            "signature": atext(),
        })),
        "info": INFO(),
        "meta": META(),
    }
}


def CONSENSUS_LOGS(choices):
    return astructarray(".readonly", value={
        "consensus_id": astring(),
        "timestamp": adatetime(),
        "status": achoices(value=choices),
    })


PEERS = {
    ".collection": {},
    ".drf_collection": DRF("panoramix.server.models.Peer",
                           {"mixins":
                            ["panoramix.server.functions.PeerView"]}),
    ".actions": {".list": {},
                 ".create": {},
                 ".retrieve": {}},
    "*": {
        "data": nondb(astruct(value={
            "peer_id": astring(),  # .initwrite: {}
            "name": astring(),  # .initwrite: {}
            "key_type": aninteger(),  # .initwrite: {}
            "crypto_backend": astring(".blankable"),  # .initwrite: {}
            "crypto_params": atext(".blankable"),  # .initwrite: {}
            "key_data": atext(),  # .initwrite: {}
            "owners": astructarray(value={
                "owner_key_id": astring()}),  # .initwrite: {}
            "status": achoices(".required", value=PeerStatus),
            "consensus_logs": CONSENSUS_LOGS(PeerStatus),
        })),
        "info": INFO(),
        "meta": META(),
        "by_consensus": BY_CONSENSUS(),
    }
}


ENDPOINTS = {
    ".collection": {},
    ".drf_collection": DRF("panoramix.server.models.Endpoint",
                           {"mixins":
                            ["panoramix.server.functions.EndpointView"],
                            "filter_fields": ["peer_id", "status"]}),
    ".actions": {".create": {},
                 ".list": {},
                 ".update": {},
                 ".retrieve": {}},
    "*": {
        "data": nondb(astruct(value={
            "endpoint_id": astring(),  # .initwrite: {}
            "peer_id": astring(),  # .initwrite: {}
            "description": astring(".blankable"),  # .initwrite: {}
            "size_min": aninteger(),  # .initwrite: {}
            "size_max": aninteger(),  # .initwrite: {}
            "endpoint_type": astring(),  # .initwrite: {}
            "endpoint_params": atext(),  # .initwrite: {}
            "links": astructarray(value={
                "to_box": achoices(value=Box),
                "from_box": achoices(value=Box),
                "from_endpoint_id": astring()}),  # .initwrite: {}
            "public": aninteger(".required"),
            "status": achoices(".required", value=EndpointStatus),
            "process_proof": atext(),
            "message_hashes": nondb(astructarray(".writeonly", value={
                    "hash": nondb(astring(".writeonly"))})),
            "inbox_hash": astring(".readonly"),
            "outbox_hash": astring(".readonly"),
            "consensus_logs": CONSENSUS_LOGS(EndpointStatus),
        })),
        "info": INFO(),
        "meta": META(),
        "by_consensus": BY_CONSENSUS(),
    }
}


MESSAGES = {
    ".collection": {},
    ".drf_collection": DRF("panoramix.server.models.Message",
                           {"mixins":
                            ["panoramix.server.functions.MessageView"],
                            "filter_fields": ["endpoint_id", "box"]}),
    ".actions": {".create": {},
                 ".list": {}},
    "*": {
        "data": nondb(astruct(value={
            "id": aserial(".readonly"),
            "serial": aninteger(".nullable"),
            "endpoint_id": astring(".required"),
            "sender": astring(".required"),
            "recipient": astring(".required"),
            "text": atext(".required"),
            "box": achoices(".required", value=Box),
            "message_hash": astring(".readonly"),
        })),
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
