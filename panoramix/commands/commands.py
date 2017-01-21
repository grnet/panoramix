from __future__ import unicode_literals

import sys

import json
from panoramix import utils
from panoramix.config import cfg
import panoramix.client as client_lib
from panoramix.client import mk_panoramix_client
from panoramix import canonical

from cliff.command import Command
from cliff.show import ShowOne
from cliff.lister import Lister

reload(sys)
sys.setdefaultencoding('UTF-8')


def safe_json_loads(s):
    try:
        return json.loads(s)
    except ValueError:
        print >> sys.stderr, s
        raise


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
        client = mk_panoramix_client(cfg)
        info = client.crypto_client.get_key_info()
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
        _cfg = cfg.cfg()
        return _cfg.keys(), _cfg.values()


class hashes_wrap(Command):
    def take_action(self, parsed_args):
        hashes = [line[:-1] for line in sys.stdin]
        wrapped_hash_log = {
            "message_hashes": client_lib.hash_dict_wrap(hashes)
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

        cfg.set_value(key, conversion(value))
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
        cfg.remove(key)
        print("Deleted key '%s' from config." % key)


class NegotiationCommand(Command):
    def get_parser(self, prog_name):
        parser = Command.get_parser(self, prog_name)
        args = ["--negotiation-id"]
        add_arguments(parser, args)
        parser.add_argument("--accept", action="store_true", default=False)
        return parser


class peer_create(NegotiationCommand):
    """ Create a new peer """

    def get_parser(self, prog_name):
        parser = NegotiationCommand.get_parser(self, prog_name)
        args = ["--name", "--key-file", "--owners", "--consensus-id"]
        add_arguments(parser, args)
        return parser

    def take_action(self, parsed_args):
        client = mk_panoramix_client(cfg)
        vargs = vars(parsed_args)
        consensus_id = vargs["consensus_id"]
        negotiation_id = vargs["negotiation_id"]
        accept = vargs["accept"]
        name = vargs["name"]
        if name is None:
            name = cfg.get("NAME")
        name = utils.to_unicode(name)
        owners = vargs["owners"]
        owners = owners.split(',') if owners else []

        is_contrib, d = client.peer_create(
            name, True, owners, consensus_id, negotiation_id, accept)
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
        client = mk_panoramix_client(cfg)
        client.peer_import(peer_id)
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
        client = mk_panoramix_client(cfg)
        d = client.peer_info(peer_id)
        return d.keys(), d.values()


class peer_list(Lister):
    """ List all peers """

    def take_action(self, parsed_args):
        client = mk_panoramix_client(cfg)
        r = client.clients.peers.list()
        ps = safe_json_loads(r.text)
        return from_list_of_dict(filter_data_only(ps))


class negotiation_create(Command):
    """ Initiate a new negotiation process """

    def take_action(self, parsed_args):
        client = mk_panoramix_client(cfg)
        neg_dict = client.negotiation_create()
        neg_id = neg_dict["id"]
        print(neg_id)


class negotiation_list(Lister):
    """ List negotiations """

    def take_action(self, parsed_args):
        client = mk_panoramix_client(cfg)
        r = client.clients.negotiations.list()
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
        client = mk_panoramix_client(cfg)
        neg = client.negotiation_info(negotiation_id)
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
        client = mk_panoramix_client(cfg)
        contribs = client.contribution_list(negotiation_id)
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
        client = mk_panoramix_client(cfg)
        d = client.contribution_accept(negotiation_id, contribution_id)
        print("%s" % d["id"])


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
        client = mk_panoramix_client(cfg)
        r = client.run_contribution(negotiation_id, body, accept)
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
        client = mk_panoramix_client(cfg)
        r = client.clients.negotiations.list(
            params={"consensus": consensus_id})
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

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        peer_id = vargs["peer_id"]
        endpoint_id = vargs["endpoint_id"]
        endpoint_type = vargs["endpoint_type"]
        params = dict(vargs["param"] or [])
        endpoint_params = canonical.to_canonical(params)
        size_min = int(vargs["size_min"])
        size_max = int(vargs["size_max"])
        description = vargs["description"] or ""
        consensus_id = vargs["consensus_id"]
        negotiation_id = vargs["negotiation_id"]
        accept = vargs["accept"]

        client = mk_panoramix_client(cfg)
        is_contrib, d = client.endpoint_create(
            endpoint_id, peer_id, endpoint_type, endpoint_params,
            size_min, size_max, description, consensus_id,
            negotiation_id, accept)
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
        endpoint_id = vargs["endpoint_id"]
        client = mk_panoramix_client(cfg)
        d = client.endpoint_info(endpoint_id)
        return d.keys(), d.values()


class endpoint_list(Lister):
    """ List endpoints of a given peer """

    def get_parser(self, prog_name):
        parser = Lister.get_parser(self, prog_name)
        args = ["--peer-id", "--status"]
        add_arguments(parser, args)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        peer_id = vargs["peer_id"]
        status = vargs["status"]
        client = mk_panoramix_client(cfg)
        es = client.endpoint_list(peer_id=peer_id, status=status)
        return from_list_of_dict(es)


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
        client = mk_panoramix_client(cfg)
        d = client.message_send(endpoint_id, data, recipients)
        print("%s" % d["data"]["id"])


class EndpointAction(NegotiationCommand):
    STATUS = None

    def get_parser(self, prog_name):
        parser = NegotiationCommand.get_parser(self, prog_name)
        args = ["--endpoint-id", "--from-log",
                "--on-last-consensus-id", "--consensus-id"]
        add_arguments(parser, args)
        return parser

    def take_action(self, parsed_args):
        vargs = vars(parsed_args)
        endpoint_id = vargs["endpoint_id"]
        from_log = vargs["from_log"]
        with open(from_log) as f:
            properties = json.load(f)
        on_last_consensus_id = vargs.get("on_last_consensus_id")
        consensus_id = vargs.get("consensus_id")
        negotiation_id = vargs["negotiation_id"]
        accept = vargs["accept"]

        client = mk_panoramix_client(cfg)
        is_contrib, d = client.endpoint_action(
            endpoint_id, self.STATUS, properties, on_last_consensus_id,
            consensus_id, negotiation_id, accept)
        id_key = "id" if is_contrib else "endpoint_id"
        print("%s" % d["data"][id_key])


class inbox_close(EndpointAction):
    """ close an endpoint's inbox """
    STATUS = "CLOSED"


class processed_ack(EndpointAction):
    """ acknowledge an endpoint's outbox """
    STATUS = "PROCESSED"


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

        client = mk_panoramix_client(cfg)
        responses, process_log = client.inbox_process(
            endpoint_id, peer_id, upload)

        for response in responses:
            print("%s" % response["data"]["id"])
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
        client = mk_panoramix_client(cfg)
        ms = client.box_list(endpoint_id, self.BOX)
        return from_list_of_dict(ms)


class inbox_list(BoxLister):
    """ List messages of a cycle inbox """
    BOX = client_lib.INBOX


class accepted_list(BoxLister):
    """ List messages accepted by a cycle """
    BOX = client_lib.ACCEPTED


class processed_list(BoxLister):
    """ List messages processed by a cycle """
    BOX = client_lib.PROCESSBOX


class outbox_list(BoxLister):
    """ List messages of a cycle outbox """
    BOX = client_lib.OUTBOX


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
        client = mk_panoramix_client(cfg)
        responses = client.outbox_forward(from_endpoint_id, to_endpoint_id)
        if not responses:
            print "No messages"
            return
        for response in responses:
            print("%s" % response["data"]["id"])
