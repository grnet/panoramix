from collections import namedtuple
import importlib

from apimas.clients.adapter import ApimasClientAdapter
from apimas.exceptions import ApimasClientException

from panoramix.spec import SPEC
from panoramix import canonical
from panoramix import utils


ClientTuple = namedtuple(
    "ClientTuple",
    ["peers", "contributions", "negotiations", "endpoints", "messages"])


def mk_clients(catalog_url):
    client_gen = ApimasClientAdapter(catalog_url)
    client_gen.construct(SPEC)
    clients = client_gen.get_clients()
    clients = dict((k.split('/')[-1], v) for (k, v) in clients.items())
    return ClientTuple(**clients)


def mk_info(resource, operation, ident=None):
    info = {
        "resource": resource,
        "operation": operation,
    }
    if ident is not None:
        info["id"] = ident
    return info


T_STRUCTURAL = "structural"


def mk_by_consensus(consensus_id, part=None):
    return {
        "consensus_id": consensus_id,
        "consensus_type": T_STRUCTURAL,
        "consensus_part": part,
    }


def filter_data_only(lst):
    return [d["data"] for d in lst]


def hash_dict_wrap(message_hashes):
    return [{"hash": mh} for mh in sorted(message_hashes)]


def include_next_negotiation_id(meta, next_negotiation_id):
    if next_negotiation_id is not None:
        meta["next_negotiation_id"] = next_negotiation_id
    return meta


INBOX = "INBOX"
OUTBOX = "OUTBOX"
PROCESSBOX = "PROCESSBOX"
ACCEPTED = "ACCEPTED"

CLOSED = "CLOSED"
PROCESSED = "PROCESSED"

STATUS_FOR_BOX = {
    ACCEPTED: CLOSED,
    OUTBOX: PROCESSED,
}


def get_setting_or_fail(cfg, name):
    value = cfg.get(name)
    if not value:
        raise ValueError("%s is not set" % name)
    return value


def mk_panoramix_client(cfg):
    client = PanoramixClient()
    client.register_catalog_url(get_setting_or_fail(cfg, "CATALOG_URL"))
    client.register_backend(get_setting_or_fail(cfg, "CRYPTO_BACKEND"))
    client.register_crypto_client(cfg)
    return client


class InputNotReady(Exception):
    pass


class NoLinks(Exception):
    pass



class PanoramixClient(object):
    catalog_url = None
    clients = None
    backend = None
    crypto_client = None
    mixnet = None

    def register_catalog_url(self, catalog_url):
        self.catalog_url = catalog_url
        self.clients = mk_clients(catalog_url)

    def register_backend(self, crypto_backend):
        self.backend = importlib.import_module(crypto_backend)

    def register_crypto_client(self, cfg):
        assert self.backend is not None
        self.crypto_client = self.backend.get_client(cfg)

    def register_mixnet(self, description):
        assert self.backend is not None
        self.mixnet = self.backend.mixnet_class(description)
        for peer in self.mixnet.known_peers:
            self.peer_import(peer)

    def mk_endpoint_hyperlink(self, endpoint_id):
        endpoint = self.clients.endpoints.endpoint.rstrip('/')
        return endpoint + '/' + endpoint_id + '/'

    def mk_peer_hyperlink(self, peer_id):
        endpoint = self.clients.peers.endpoint.rstrip('/')
        return endpoint + '/' + peer_id + '/'

    def mk_negotiation_hyperlink(self, negotiation_id):
        endpoint = self.clients.negotiations.endpoint.rstrip('/')
        return endpoint + '/' + negotiation_id + '/'

    def mk_signed_request(self, attrs):
        mixnet_body = canonical.to_canonical(attrs)
        signature = self.crypto_client.sign(mixnet_body)
        key_data = self.crypto_client.get_key_data()
        meta = "meta"
        assert meta not in attrs
        attrs[meta] = {
            "signature": signature,
            "key_data": key_data,
        }
        return attrs

    def run_contribution(self, negotiation_id, body, accept, extra_meta=None):
        meta = {}
        if extra_meta is not None:
            meta.update(extra_meta)
        meta["accept"] = accept
        text = {"body": body,
                "meta": meta}
        canonical_text = canonical.to_canonical(text)
        signature = self.crypto_client.sign(canonical_text)
        payload = {
            "info": mk_info("contribution", "create"),
            "data": {
                "negotiation": self.mk_negotiation_hyperlink(negotiation_id),
                "text": canonical_text,
                "signature": signature,
                "signer_key_id": self.crypto_client.get_keyid()
            },
        }
        request = self.mk_signed_request(payload)
        r = self.clients.contributions.create(data=request)
        return r

    def run_action(self, attrs, negotiation_id, accept, callpoint,
                   resource_id=None, extra_meta=None):
        if negotiation_id:
            r = self.run_contribution(
                negotiation_id, attrs, accept, extra_meta)
        else:
            request = self.mk_signed_request(attrs)
            kwargs = {"data": request}
            if resource_id is not None:
                kwargs["resource_id"] = resource_id
            r = callpoint(**kwargs)
        outp = r.json()
        return bool(negotiation_id), outp

    def negotiation_create(self):
        request = {}
        payload = {
            "info": mk_info("negotiation", "create"),
            "data": {},
        }
        request = self.mk_signed_request(payload)
        r = self.clients.negotiations.create(data=request)
        return r.json()["data"]

    def negotiation_info(self, negotiation_id):
        r = self.clients.negotiations.retrieve(negotiation_id)
        return r.json()["data"]

    def with_self_consensus(self, action, kwargs):
        negotiation = self.negotiation_create()
        negotiation_id = negotiation["id"]
        action_kwargs = kwargs.copy()
        action_kwargs["negotiation_id"] = negotiation_id
        action_kwargs["accept"] = True
        is_contrib, d = action(**action_kwargs)
        negotiation = self.negotiation_info(negotiation_id)
        consensus = negotiation["consensus"]
        if not consensus:
            raise ValueError("no consensus")
        action_kwargs = kwargs.copy()
        action_kwargs["consensus_id"] = consensus
        is_contrib, d = action(**action_kwargs)
        if is_contrib:
            raise ValueError("contrib not expected here")
        return d["data"]

    def get_callpoint(self, resource, operation):
        clients = self.clients
        CLIENT = {"peer": clients.peers,
                  "endpoint": clients.endpoints}
        return getattr(CLIENT[resource], operation)

    def apply_multipart_consensus(self, body, consensus_id):
        responses = []
        for part, parted_body in enumerate(body):
            responses.append(
                self.apply_consensus(parted_body, consensus_id, part))
        return responses

    def apply_consensus(self, body, consensus_id, part=None):
        info = body["info"]
        callpoint = self.get_callpoint(info["resource"], info["operation"])
        body["by_consensus"] = mk_by_consensus(consensus_id, part)
        resource_id = info.get("id")
        request = self.mk_signed_request(body)
        kwargs = {"data": request}
        if resource_id is not None:
            kwargs["resource_id"] = resource_id
        r = callpoint(**kwargs)
        return r.json()

    def peer_info(self, peer_id):
        try:
            r = self.clients.peers.retrieve(peer_id)
            return r.json()["data"]
        except ApimasClientException:
            return None

    def endpoint_info(self, endpoint_id):
        try:
            r = self.clients.endpoints.retrieve(endpoint_id)
            return r.json()["data"]
        except ApimasClientException:
            return None

    def next_negotiation_meta(self, next_negotiation_id):
        if next_negotiation_id is None:
            return None
        return {"next_negotiation_id": next_negotiation_id}

    def peer_create(self, name, set_key=True, owners=None, consensus_id=None,
                    negotiation_id=None, accept=False,
                    next_negotiation_id=None):
        if owners is None:
            owners = []
        owners_d = [{"owner_key_id": owner} for owner in owners]
        if set_key:
            if not owners:
                key_data = self.crypto_client.get_key_data()
            else:
                key_data = self.crypto_client.combine_keys(owners)
            key_id = self.crypto_client.get_key_id_from_key_data(key_data)
        else:
            key_data = ""
            key_id = ""
        crypto_params = self.crypto_client.get_crypto_params()
        key_type = self.crypto_client.get_key_type()
        info = mk_info("peer", "create")
        data = {
            "name": name,
            "peer_id": key_id,
            "key_data": key_data,
            "key_type": key_type,
            "crypto_backend": self.backend.BACKEND_NAME,
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

        extra_meta = self.next_negotiation_meta(next_negotiation_id)
        return self.run_action(attrs, negotiation_id, accept,
                               self.clients.peers.create,
                               extra_meta=extra_meta)

    def peer_import(self, peer_id):
        r = self.clients.peers.retrieve(peer_id)
        d = r.json()["data"]
        public_key = d["key_data"]
        self.crypto_client.register_key(public_key)
        return public_key

    def endpoints_create_contribution(
            self, descriptions, negotiation_id, accept=False,
            next_negotiation_id=None):
        body = []
        for description in descriptions:
            info = mk_info("endpoint", "create")
            data = dict(description)
            data["status"] = "OPEN"
            attrs = {
                "info": info,
                "data": data,
            }
            body.append(attrs)

        extra_meta = self.next_negotiation_meta(next_negotiation_id)
        r = self.run_contribution(negotiation_id, body, accept, extra_meta)
        return r.json()

    def endpoint_create(
            self, endpoint_id, peer_id, endpoint_type, endpoint_params,
            size_min, size_max, description, public=False, links=None,
            consensus_id=None, negotiation_id=None, accept=False,
            next_negotiation_id=None):
        info = mk_info("endpoint", "create")
        attrs = {
            "info": info,
            "data": {
                "endpoint_id": endpoint_id,
                "peer_id": peer_id,
                "endpoint_type": endpoint_type,
                "endpoint_params": endpoint_params,
                "description": description,
                "public": int(public),
                "links": links,
                "size_min": size_min,
                "size_max": size_max,
                "status": "OPEN",
            },
        }
        if consensus_id is not None:
            attrs["by_consensus"] = mk_by_consensus(consensus_id)

        extra_meta = self.next_negotiation_meta(next_negotiation_id)
        return self.run_action(attrs, negotiation_id, accept,
                               self.clients.endpoints.create,
                               extra_meta=extra_meta)

    def endpoint_list(self, peer_id=None, status=None):
        params = {"peer_id": peer_id, "status": status}
        r = self.clients.endpoints.list(params=params)
        return filter_data_only(r.json())

    def get_open_endpoint_of_peer(self, peer_id):
        endpoints = self.endpoint_list(peer_id=peer_id, status="OPEN")
        if not endpoints:
            return None
        return endpoints[0]

    def contribution_list(self, negotiation_id):
        params = {"negotiation": negotiation_id}

        r = self.clients.contributions.list(params=params)
        contribs = r.json()
        return contribs

    def contribution_accept(self, negotiation_id, contribution_id):
        data = {"id": contribution_id, "negotiation": negotiation_id}
        r = self.clients.contributions.retrieve(contribution_id, params=data)
        contrib = r.json()["data"]
        realtext = canonical.from_unicode_canonical(contrib["text"])
        body = realtext["body"]
        r = self.run_contribution(negotiation_id, body, True)
        d = r.json()["data"]
        return d

    def prepare_send_message(
            self, endpoint_id, box, text, sender, recipient, serial=None):
        data = {
            "box": box,
            "endpoint_id": endpoint_id,
            "text": text,
            "sender": sender,
            "recipient": recipient,
            "serial": serial,
        }

        attrs = {
            "info": mk_info("message", "create"),
            "data": data,
        }
        request = self.mk_signed_request(attrs)
        return request

    def construct_message(self, recipient, message):
        return self.crypto_client.prepare_message(
            self.mixnet, recipient, message)

    def send_message_to_mixnet(self, message):
        endpoint_id = self.mixnet.gateway["endpoint_id"]
        request = self.prepare_send_message(
            endpoint_id,
            INBOX,
            message.body,
            message.sender,
            message.recipient)
        r = self.clients.messages.create(data=request)
        return r.json()

    def message_send(self, endpoint_id, data, recipients):
        enc_data = self.crypto_client.encrypt(data, recipients)
        send_to = recipients[0]
        keyid = self.crypto_client.get_keyid()
        request = self.prepare_send_message(
            endpoint_id, INBOX, enc_data, keyid, send_to)
        r = self.clients.messages.create(data=request)
        return r.json()

    def box_list(self, endpoint_id, box):
        r = self.clients.messages.list(params={
            "endpoint_id": endpoint_id, "box": box})
        ms = r.json()
        return filter_data_only(ms)

    def get_latest_consensus(self, endpoint, on_status=None):
        consensus_logs = endpoint["consensus_logs"]
        latest = max(consensus_logs, key=lambda log: log["timestamp"])
        if on_status is not None and latest["status"] != on_status:
            return None
        return latest

    def check_endpoint_on_minimum(self, endpoint):
        size_min = endpoint["size_min"]
        size_max = endpoint["size_max"]
        inbox_messages = self.box_list(endpoint["endpoint_id"], INBOX)
        inbox_size = len(inbox_messages)
        if inbox_size < size_min:
            return []
        selected = inbox_messages[:size_max]
        message_hashes = [msg["message_hash"] for msg in selected]
        return hash_dict_wrap(message_hashes)

    def close_on_minimum_prepare(self, endpoint_id):
        endpoint = self.endpoint_info(endpoint_id)
        latest_consensus = self.get_latest_consensus(endpoint, "OPEN")
        if endpoint["status"] != "OPEN" or latest_consensus is None:
            return "wrongstatus"
        message_hashes = self.check_endpoint_on_minimum(endpoint)
        if not message_hashes:
            return "nomin"
        properties = {"message_hashes": message_hashes}
        return {"endpoint_id": endpoint_id, "status": "CLOSED",
                "properties": properties,
                "on_last_consensus_id": latest_consensus["consensus_id"]}

    def close_on_minimum(self, endpoint_id, negotiation_id,
                         next_negotiation_id=None):
        params = self.close_on_minimum_prepare(endpoint_id)
        if params in ["wrongstatus", "nomin"]:
            return params
        params["negotiation_id"] = negotiation_id
        params = include_next_negotiation_id(params, next_negotiation_id)
        return self.endpoint_action(**params)

    def record_process_prepare(self, endpoint_id, properties):
        endpoint = self.endpoint_info(endpoint_id)
        latest_consensus = self.get_latest_consensus(endpoint, "CLOSED")
        if endpoint["status"] != "CLOSED" or latest_consensus is None:
            return "wrongstatus"
        return {"endpoint_id": endpoint_id, "status": "PROCESSED",
                "properties": properties,
                "on_last_consensus_id": latest_consensus["consensus_id"]}

    def record_process(self, endpoint_id, negotiation_id, properties,
                       next_negotiation_id=None):
        params = self.record_process_prepare(endpoint_id, properties)
        if params == "wrongstatus":
            return params
        params["negotiation_id"] = negotiation_id
        params = include_next_negotiation_id(params, next_negotiation_id)
        return self.endpoint_action(**params)

    def endpoint_action(
            self, endpoint_id, status, properties, on_last_consensus_id=None,
            consensus_id=None, negotiation_id=None, accept=False,
            next_negotiation_id=None):

        info = mk_info("endpoint", "partial_update", endpoint_id)
        if on_last_consensus_id is not None:
            info["on_last_consensus_id"] = on_last_consensus_id

        data = {"status": status}
        data.update(properties)

        attrs = {
            "info": info,
            "data": data,
        }

        if consensus_id is not None:
            attrs["by_consensus"] = mk_by_consensus(consensus_id)

        extra_meta = self.next_negotiation_meta(next_negotiation_id)
        r = self.run_action(
            attrs, negotiation_id, accept,
            self.clients.endpoints.partial_update,
            resource_id=endpoint_id, extra_meta=extra_meta)
        self.clients = mk_clients(self.catalog_url)
        return r

    def transport_to_processbox(self, processed_data, endpoint):
        requests = []
        endpoint_id = endpoint["endpoint_id"]
        peer_id = endpoint["peer_id"]
        for serial, (recipient, text) in enumerate(processed_data):
            request = self.prepare_send_message(
                endpoint_id, PROCESSBOX, text,
                peer_id, recipient, serial=serial)
            requests.append(request)
        return requests

    def hash_serialized_messages(self, sender, processed_data):
        msg_hashes = []
        for serial, (recipient, text) in enumerate(processed_data):
            msg_hashes.append(
                utils.hash_message(text, sender, recipient, serial))
        return msg_hashes

    def mk_process_log(self, msg_hashes, proof, wrap=True):
        hashes = hash_dict_wrap(msg_hashes) if wrap else msg_hashes
        return {
            "message_hashes": hashes,
            "process_proof": canonical.to_canonical(proof),
        }

    def inbox_process(self, endpoint_id, peer_id, upload):
        endpoint_resp = self.clients.endpoints.retrieve(endpoint_id)
        endpoint = endpoint_resp.json()["data"]

        r = self.clients.messages.list(params={
            "endpoint_id": endpoint_id, "box": ACCEPTED})
        messages = filter_data_only(r.json())

        responses = []
        process_log = {}
        if not messages:
            return responses, process_log

        try:
            processed_data, proof = self.crypto_client.process(
                endpoint, messages)
        except utils.NoProcessing:
            return responses, process_log

        msg_hashes = self.hash_serialized_messages(peer_id, processed_data)
        process_log = self.mk_process_log(msg_hashes, proof)

        if upload:
            requests = self.transport_to_processbox(processed_data, endpoint)
            for request in requests:
                r = self.clients.messages.create(data=request)
                d = r.json()
                responses.append(d)

        return responses, process_log

    def messages_forward(self, endpoint_id):
        r = self.clients.messages.list(params={
            "endpoint_id": endpoint_id, "box": OUTBOX})
        messages = filter_data_only(r.json())
        responses = []
        for message in messages:
            responses.append(self.message_forward(message))
        return responses

    def write_to_file(self, message, filename):
        text = canonical.from_unicode_canonical(message["text"])
        with open(filename, "a") as f:
            f.write("%s\n\0" % utils.unicode_to_locale(text))
        return (message["id"], "file", filename)

    def message_forward(self, message):
        recipient = message["recipient"]
        separator = "://"
        resource_type, sep, value = recipient.partition(separator)
        if sep == separator and resource_type == "file":
            return self.write_to_file(message, value)

        to_endpoint = self.get_open_endpoint_of_peer(recipient)
        request = self.prepare_send_message(
            to_endpoint["endpoint_id"],
            INBOX,
            message["text"],
            message["sender"],
            recipient)
        r = self.clients.messages.create(data=request)
        return (message["id"], "peer", recipient)

    def check_input_is_ready(self, links):
        for link in links:
            from_endpoint = self.endpoint_info(link["from_endpoint_id"])
            from_box = link["from_box"]
            required_status = STATUS_FOR_BOX[from_box]
            if required_status != from_endpoint["status"]:
                raise InputNotReady()

    def get_links_for_box(self, endpoint, to_box):
        return  [link for link in endpoint["links"]
                 if link["to_box"] == to_box]

    def get_input_from_link(
            self, endpoint_id, to_box, serialized=False, dry_run=False):
        endpoint = self.endpoint_info(endpoint_id)
        links = self.get_links_for_box(endpoint, to_box)
        if not links:
            raise NoLinks()
        self.check_input_is_ready(links)

        serial = 0 if serialized else None
        responses = []
        msg_hashes = []
        for link in links:
            rs, mhs, serial = self.box_forward(
                from_endpoint_id=link["from_endpoint_id"],
                to_endpoint_id=endpoint_id,
                from_box=link["from_box"],
                to_box=link["to_box"],
                serial=serial,
                dry_run=dry_run)
            responses.extend(rs)
            msg_hashes.extend(mhs)
        return responses, hash_dict_wrap(msg_hashes)

    def box_forward(self, from_endpoint_id, to_endpoint_id,
                    from_box, to_box, serial=None, dry_run=False):
        r = self.clients.messages.list(params={
            "endpoint_id": from_endpoint_id, "box": from_box})
        messages = filter_data_only(r.json())
        responses = []
        msg_hashes = []
        for message in messages:
            msg_hash = utils.hash_message(
                message["text"],
                message["sender"],
                message["recipient"],
                serial)
            msg_hashes.append(msg_hash)
            if not dry_run:
                request = self.prepare_send_message(
                    to_endpoint_id,
                    to_box,
                    message["text"],
                    message["sender"],
                    message["recipient"],
                    serial=serial)
                r = self.clients.messages.create(data=request)
                d = r.json()
                responses.append(d)
            if serial is not None:
                serial += 1
        return responses, msg_hashes, serial

    def outbox_forward(self, from_endpoint_id, to_endpoint_id):
        return self.box_forward(
            from_endpoint_id, to_endpoint_id, OUTBOX, INBOX)
