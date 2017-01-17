from __future__ import unicode_literals

import sys
reload(sys)
sys.setdefaultencoding('UTF-8')

import json
import hashlib
from apimas.modeling.clients import ApimasClientAdapter

from panoramix import canonical
from panoramix import utils
from panoramix.config import get_client_backend, cfg, CONFIG_FILE

from cliff.command import Command
from cliff.show import ShowOne
from cliff.lister import Lister

backend = get_client_backend()


from panoramix.spec import SPEC, ROOT as DEFAULT_ROOT

ROOT = cfg.get("CATALOG_URL", DEFAULT_ROOT)
client_gen = ApimasClientAdapter(ROOT)
client_gen.construct(SPEC)
client_gen.apply()
clients =client_gen.get_clients()

peers = clients["peers"]
contributions = clients["contributions"]
negotiations = clients["negotiations"]
endpoints = clients["endpoints"]
messages_client = clients["messages"]


INBOX = "INBOX"
OUTBOX = "OUTBOX"
PROCESSBOX = "PROCESSBOX"
ACCEPTED = "ACCEPTED"


def mk_negotiation_hyperlink(negotiation_id):
    endpoint = negotiations.endpoint.rstrip('/')
    return endpoint + '/' + negotiation_id + '/'


def safe_json_loads(s):
    try:
        return json.loads(s)
    except ValueError:
        print >> sys.stderr, s
        raise


def mk_info(resource, operation, ident=None):
    info = {
        "resource": resource,
        "operation": operation,
    }
    if ident is not None:
        info["id"] = ident
    return info


def tag_reference(dest):
    return ["ref", dest]


def tag_value(value):
    return ["val", value]


T_STRUCTURAL = "structural"


def mk_by_consensus(consensus_id):
    return {
        "consensus_id": consensus_id,
        "consensus_type": T_STRUCTURAL,
    }


def mk_signed_request(attrs):
    mixnet_body = canonical.to_canonical(attrs)
    signature = backend.sign(mixnet_body)
    key_data = backend.get_key_data()
    meta = "meta"
    assert meta not in attrs
    attrs[meta] = {
        "signature": signature,
        "key_data": key_data,
    }
    return attrs


def filter_data_only(lst):
    return [d["data"] for d in lst]


def from_list_of_dict(lst):
    if not lst:
        return [], []
    keys = lst[0].keys()
    values = []
    for elem in lst:
        v = []
        for key in keys:
            v.append(elem[key])
        values.append(v)
    return keys, values


class key_show(ShowOne):
    """ Show your crypto key """

    def take_action(self, parsed_args):
        info = backend.get_key_info()
        return info.keys(), info.values()


def add_arguments(parser, args):
    for arg in args:
        parser.add_argument(arg)


T_INT = "int"
T_STRING = "string"


CONVERSIONS = {
    T_INT: int,
    T_STRING: lambda x: x,
}


class config_list(ShowOne):
    def take_action(self, parsed_args):
        return cfg.keys(), cfg.values()


def hash_dict_wrap(message_hashes):
    return [{"hash": mh} for mh in sorted(message_hashes)]


class hashes_wrap(Command):
    def take_action(self, parsed_args):
        hashes = [line[:-1] for line in sys.stdin]
        wrapped_hash_log = {
            "message_hashes": hash_dict_wrap(hashes)
        }
        print json.dumps(wrapped_hash_log)


class config_set(Command):
    def get_parser(self, prog_name):
        parser = Command.get_parser(self, prog_name)
        args = ["--key", "--value", "--type"]
        add_arguments(parser, args)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        key = utils.to_unicode(vargs["key"])
        value = utils.to_unicode(vargs["value"])
        typ = vargs["type"] or T_STRING
        conversion = CONVERSIONS.get(typ)
        if conversion is None:
            print("Unrecognized type %s" % typ)
        cfg[key] = conversion(value)

        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f)
        print("Wrote '%s': %s in config." % (key, value))


class config_unset(Command):
    def get_parser(self, prog_name):
        parser = Command.get_parser(self, prog_name)
        args = ["--key"]
        add_arguments(parser, args)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        key = utils.to_unicode(vargs["key"])
        cfg.pop(key)
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f)
        print("Deleted key '%s' from config." % key)


class NegotiationCommand(Command):
    def get_parser(self, prog_name):
        parser = Command.get_parser(self, prog_name)
        args = ["--negotiation-id"]
        add_arguments(parser, args)
        parser.add_argument("--accept", action="store_true", default=False)
        return parser

    def run_action(self, vargs, callpoint, resource_id=None):
        negotiation_id = vargs["negotiation_id"]
        accept = vargs["accept"]
        attrs = self.mk_attrs(vargs)
        if negotiation_id:
            r = run_contribution(negotiation_id, attrs, accept)
        else:
            request = mk_signed_request(attrs)
            kwargs = {"data": request}
            if resource_id is not None:
                kwargs["resource_id"] = resource_id
            r = callpoint(**kwargs)
        outp = r.text
        if outp:
            outp = safe_json_loads(outp)
        return bool(negotiation_id), outp


class peer_create(NegotiationCommand):
    """ Create a new peer """

    def get_parser(self, prog_name):
        parser = NegotiationCommand.get_parser(self, prog_name)
        args = ["--name", "--key-file", "--owners", "--consensus-id"]
        add_arguments(parser, args)
        return parser

    def mk_attrs(self, vargs):
        consensus_id = vargs["consensus_id"]
        name = vargs["name"]
        if name is None:
            name = cfg.get("NAME")
        name = utils.to_unicode(name)
        key_type = backend.get_key_type()
        owners = vargs["owners"]
        owners = owners.split(',') if owners else []
        owners_d = [{"owner_key_id": owner} for owner in owners]
        key_file = vargs["key_file"]
        if key_file:
            with open(key_file) as f:
                key_specs = json.load(f)
                key_data = key_specs["key_data"]
        elif not owners:
            key_data = backend.get_key_data()
        else:
            key_data = backend.combine_keys(owners)
        key_id = backend.get_key_id_from_key_data(key_data)
        crypto_params = backend.get_crypto_params()
        info = mk_info("peer", "create")
        data = {
            "name": name,
            "peer_id": key_id,
            "key_data": key_data,
            "key_type": key_type,
            "crypto_params": crypto_params,
            "owners": owners_d,
            "status": "READY",
        }
        attrs = {
            "info": info,
            "data": data,
        }
        if consensus_id is not None:
            attrs["by_consensus"] = mk_by_consensus(consensus_id)
        return attrs

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        is_contrib, d = self.run_action(vargs, peers.create)
        id_key = "id" if is_contrib else "peer_id"
        print("%s" % d["data"][id_key])


class peer_import(Command):
    """ Import a peer's public key to your local registry """

    def get_parser(self, prog_name):
        parser = Command.get_parser(self, prog_name)
        args = ["--peer-id"]
        add_arguments(parser, args)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        peer_id = vargs["peer_id"]
        r = peers.retrieve(peer_id)
        d = safe_json_loads(r.text)["data"]
        public_key = d["key_data"]
        backend.register_key(public_key)
        m = "Imported public key for %s in your local registry" % peer_id
        print(m)


class peer_info(ShowOne):
    """ Show peer info """

    def get_parser(self, prog_name):
        parser = ShowOne.get_parser(self, prog_name)
        args = ["--peer-id"]
        add_arguments(parser, args)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        peer_id = vargs["peer_id"]
        r = peers.retrieve(peer_id)
        d = safe_json_loads(r.text)["data"]
        return d.keys(), d.values()


class peer_list(Lister):
    """ List all peers """

    def take_action(self, parsed_args):
        r = peers.list()
        ps = safe_json_loads(r.text)
        return from_list_of_dict(filter_data_only(ps))


class negotiation_create(Command):
    """ Initiate a new negotiation process """

    def take_action(self, parsed_args):
        request = {}
        payload = {
            "info": mk_info("negotiation", "create"),
            "data": {},
        }
        request = mk_signed_request(payload)
        r = negotiations.create(data=request)
        neg_dict = safe_json_loads(r.text)["data"]
        neg_id = neg_dict["id"]
        print(neg_id)


class negotiation_list(Lister):
    """ List negotiations """

    def take_action(self, parsed_args):
        r = negotiations.list()
        ps = safe_json_loads(r.text)
        return from_list_of_dict(filter_data_only(ps))


class negotiation_info(ShowOne):
    """ Get the negotiation status and contributions """

    def get_parser(self, prog_name):
        parser = ShowOne.get_parser(self, prog_name)
        args = ["--negotiation-id"]
        add_arguments(parser, args)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        negotiation_id = vargs["negotiation_id"]
        r = negotiations.retrieve(negotiation_id)
        neg = safe_json_loads(r.text)["data"]
        return neg.keys(), neg.values()


class contribution_list(Lister):
    def get_parser(self, prog_name):
        parser = Lister.get_parser(self, prog_name)
        args = ["--negotiation-id"]
        add_arguments(parser, args)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        negotiation_id = vargs["negotiation_id"]
        params={"negotiation": negotiation_id}

        r = contributions.list(params=params)
        contribs = filter_data_only(safe_json_loads(r.text))

        listing = []

        for contrib in contribs:
            if not contrib["latest"]:
                continue
            realtext = canonical.from_canonical(
                canonical.from_unicode(contrib["text"]))
            listing.append({
                "body": realtext["body"],
                "meta": realtext["meta"],
                "id": contrib["id"],
                "signer_key_id": contrib["signer_key_id"],
                })
        return from_list_of_dict(listing)


class contribution_accept(Command):
    def get_parser(self, prog_name):
        parser = Command.get_parser(self, prog_name)
        args = ["--negotiation-id", "--contribution-id"]
        add_arguments(parser, args)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        negotiation_id = vargs["negotiation_id"]
        contribution_id = int(vargs["contribution_id"])
        data = {"id": contribution_id, "negotiation": negotiation_id}
        r = contributions.retrieve(contribution_id, params=data)
        contrib = safe_json_loads(r.text)["data"]
        realtext = canonical.from_canonical(
            canonical.from_unicode(contrib["text"]))
        body = realtext["body"]
        r = run_contribution(negotiation_id, body, True)
        d = safe_json_loads(r.text)["data"]
        print("%s" % d["id"])


def run_contribution(negotiation_id, body, accept):
    meta = {}
    meta["accept"] = accept
    text = {"body": body,
            "meta": meta}
    canonical_text = canonical.to_canonical(text)
    signature = backend.sign(canonical_text)
    payload = {
        "info": mk_info("contribution", "create"),
        "data": {
            "negotiation": mk_negotiation_hyperlink(negotiation_id),
            "text": canonical_text,
            "signature": signature,
            "signer_key_id": backend.get_keyid()
        },
    }
    request = mk_signed_request(payload)
    r = contributions.create(data=request)
    return r


class negotiation_contribute(Command):
    """ Add to the negotiation a signed text you endorse """

    def get_parser(self, prog_name):
        parser = Command.get_parser(self, prog_name)
        args = ["--negotiation-id", "--body"]
        add_arguments(parser, args)
        parser.add_argument("--accept", action="store_true", default=False)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        negotiation_id = vargs["negotiation_id"]
        body = vargs["body"]
        accept = vargs["accept"]
        r = run_contribution(negotiation_id, body, accept)
        print(r.text)


class consensus_info(ShowOne):
    """ Get details of a consensus """

    def get_parser(self, prog_name):
        parser = ShowOne.get_parser(self, prog_name)
        args = ["--consensus-id"]
        add_arguments(parser, args)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        consensus_id = vargs["consensus_id"]
        r = negotiations.list(params={"consensus": consensus_id})
        conses = safe_json_loads(r.text)
        assert len(conses) == 1
        cons = conses[0]["data"]
        return cons.keys(), cons.values()


class endpoint_create(NegotiationCommand):
    """ create an endpoint """

    def get_parser(self, prog_name):
        parser = NegotiationCommand.get_parser(self, prog_name)
        args = ["--peer-id", "--endpoint-type",
                "--endpoint-id", "--size-min", "--size-max",
                "--description", "--consensus-id"]
        add_arguments(parser, args)
        parser.add_argument("--param", action="append",
                            nargs=2, metavar=("KEY", "VALUE"))
        return parser

    def mk_attrs(self, vargs):
        peer_id = vargs["peer_id"]
        endpoint_id = vargs["endpoint_id"]
        endpoint_type = vargs["endpoint_type"]
        params = dict(vargs["param"] or [])
        endpoint_params = canonical.to_canonical(params)
        size_min = int(vargs["size_min"])
        size_max = int(vargs["size_max"])
        description = vargs["description"] or ""
        consensus_id = vargs["consensus_id"]
        attrs = {
            "info": mk_info("endpoint", "create"),
            "data": {
                "endpoint_id": endpoint_id,
                "peer_id": peer_id,
                "endpoint_type": endpoint_type,
                "endpoint_params": endpoint_params,
                "description": description,
                "size_min": size_min,
                "size_max": size_max,
                "status": "OPEN",
            },
        }
        if consensus_id is not None:
            attrs["by_consensus"] = mk_by_consensus(consensus_id)
        return attrs

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        is_contrib, d = self.run_action(vargs, endpoints.create)
        id_key = "id" if is_contrib else "endpoint_id"
        print("%s" % d["data"][id_key])


class endpoint_info(ShowOne):
    """ Show endpoint info """

    def get_parser(self, prog_name):
        parser = ShowOne.get_parser(self, prog_name)
        args = ["--endpoint-id"]
        add_arguments(parser, args)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        peer_id = vargs["endpoint_id"]
        r = endpoints.retrieve(peer_id)
        d = safe_json_loads(r.text)["data"]
        return d.keys(), d.values()


class endpoint_list(Lister):
    """ List endpoints of a given peer """

    def get_parser(self, prog_name):
        parser = Lister.get_parser(self, prog_name)
        args = ["--peer-id"]
        add_arguments(parser, args)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        peer_id = vargs["peer_id"]
        r = endpoints.list(params={"peer_id": peer_id})
        cs = safe_json_loads(r.text)
        return from_list_of_dict(filter_data_only(cs))


def hash_message(text, sender, recipient):
    hasher = hashlib.sha256()
    hasher.update(text)
    hasher.update(sender)
    hasher.update(recipient)
    return hasher.hexdigest()


def prepare_send_message(
        endpoint_id, box, text, sender, recipient, send_hash=False):
    data = {
        "box": box,
        "endpoint_id": endpoint_id,
        "text": text,
        "sender": sender,
        "recipient": recipient,
    }

    msg_hash = hash_message(text, sender, recipient)
    if send_hash:
        data["message_hash"] = msg_hash

    attrs = {
        "info": mk_info("message", "create"),
        "data": data,
    }
    request = mk_signed_request(attrs)
    return request, msg_hash


class message_send(Command):
    """ Send a message to an open cycle of a peer """

    def get_parser(self, prog_name):
        parser = Command.get_parser(self, prog_name)
        args = ["--recipients", "--endpoint-id", "--data"]
        add_arguments(parser, args)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        recipients = vargs["recipients"]
        recipients = recipients.split(',')
        endpoint_id = vargs["endpoint_id"]
        data = vargs["data"]
        enc_data = backend.encrypt(data, recipients)
        send_to = recipients[0]
        request, _ = prepare_send_message(
            endpoint_id, INBOX, enc_data, backend.get_keyid(), send_to)
        r = messages_client.create(data=request)
        d = safe_json_loads(r.text)
        print("%s" % d["data"]["id"])


class EndpointAction(NegotiationCommand):
    STATUS = None

    def get_parser(self, prog_name):
        parser = NegotiationCommand.get_parser(self, prog_name)
        args = ["--endpoint-id", "--from-log",
                "--on-last-consensus-id", "--consensus-id"]
        add_arguments(parser, args)
        return parser

    def mk_attrs(self, vargs):
        endpoint_id = vargs["endpoint_id"]
        from_log = vargs["from_log"]
        with open(from_log) as f:
            log = json.load(f)

        on_last_consensus_id = vargs.get("on_last_consensus_id")
        consensus_id = vargs.get("consensus_id")
        info = mk_info("endpoint", "partial_update", endpoint_id)
        if on_last_consensus_id is not None:
            info["on_last_consensus_id"] = on_last_consensus_id

        data = {"status": self.STATUS}
        data.update(log)

        attrs = {
            "info": info,
            "data": data,
        }

        if consensus_id is not None:
            attrs["by_consensus"] = mk_by_consensus(consensus_id)
        return attrs

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        endpoint_id = vargs["endpoint_id"]
        is_contrib, d = self.run_action(
            vargs, endpoints.partial_update, resource_id=endpoint_id)
        id_key = "id" if is_contrib else "peer_id"
        print("%s" % d["data"][id_key])


class inbox_close(EndpointAction):
    """ close an endpoint's inbox """
    STATUS = "CLOSED"


class processed_ack(EndpointAction):
    """ acknowledge an endpoint's outbox """
    STATUS = "PROCESSED"


def compute_messages_hash(msg_hashes):
    sorted_hashes = sorted(msg_hashes)
    hasher = hashlib.sha256()
    for msg_hash in sorted_hashes:
        hasher.update(msg_hash)
        return hasher.hexdigest()


class inbox_process(Command):
    """ Get all inbox messages, process them and upload to outbox """

    def get_parser(self, prog_name):
        parser = Command.get_parser(self, prog_name)
        args = ["--peer-id", "--endpoint-id", "--process-log-file"]
        add_arguments(parser, args)
        parser.add_argument("--upload", action="store_true", default=False)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        process_log_file = vargs["process_log_file"]

        upload = vargs["upload"]
        peer_id = vargs["peer_id"]
        endpoint_id = vargs["endpoint_id"]
        endpoint_resp = endpoints.retrieve(endpoint_id)
        endpoint = safe_json_loads(endpoint_resp.text)["data"]

        r = messages_client.list(params={
            "endpoint_id": endpoint_id, "box": ACCEPTED})
        messages = filter_data_only(safe_json_loads(r.text))
        if not messages:
            print("No messages")
            return
        messages_text = [m["text"] for m in messages]
        processed_data, proof = backend.process(endpoint, messages_text)
        requests = []
        msg_hashes = []
        for recipient, text in processed_data:
            if recipient is None:
                recipient = "dummy_next_recipient"
            request, msg_hash = prepare_send_message(
                endpoint_id, PROCESSBOX, text,
                peer_id, recipient, send_hash=False)
            requests.append(request)
            msg_hashes.append(msg_hash)

        if upload:
            for request in requests:
                r = messages_client.create(data=request)
                d = safe_json_loads(r.text)
                print("%s" % d["data"]["id"])

        process_log = {
            "message_hashes": hash_dict_wrap(msg_hashes),
            "process_proof": canonical.to_canonical(proof),
        }
        with open(process_log_file, "w") as f:
            json.dump(process_log, f)
        print("Wrote process log in '%s'." % process_log_file)


class BoxLister(Lister):
    BOX = None

    def get_parser(self, prog_name):
        parser = Lister.get_parser(self, prog_name)
        args = ["--endpoint-id"]
        add_arguments(parser, args)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        endpoint_id = vargs["endpoint_id"]
        r = messages_client.list(params={
            "endpoint_id": endpoint_id, "box": self.BOX})
        ms = safe_json_loads(r.text)
        return from_list_of_dict(filter_data_only(ms))


class inbox_list(BoxLister):
    """ List messages of a cycle inbox """
    BOX = INBOX


class accepted_list(BoxLister):
    """ List messages accepted by a cycle """
    BOX = ACCEPTED


class processed_list(BoxLister):
    """ List messages processed by a cycle """
    BOX = PROCESSBOX


class outbox_list(BoxLister):
    """ List messages of a cycle outbox """
    BOX = OUTBOX


class outbox_forward(Command):
    def get_parser(self, prog_name):
        parser = Command.get_parser(self, prog_name)
        args = ["--from-endpoint-id", "--to-endpoint-id"]
        add_arguments(parser, args)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        from_endpoint_id = vargs["from_endpoint_id"]
        to_endpoint_id = vargs["to_endpoint_id"]

        r = messages_client.list(params={
            "endpoint_id": from_endpoint_id, "box": OUTBOX})
        messages = filter_data_only(safe_json_loads(r.text))
        if not messages:
            print("No messages")
            return
        for message in messages:
            request, msg_hash = prepare_send_message(
                to_endpoint_id,
                INBOX,
                message["text"],
                message["sender"],
                message["recipient"])
            r = messages_client.create(data=request)
            d = safe_json_loads(r.text)
            print("%s" % d["data"]["id"])
