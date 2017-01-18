import sys
import hashlib
import json
from collections import namedtuple
import importlib

from apimas.modeling.clients import ApimasClientAdapter
from apimas.modeling.core.exceptions import ApimasClientException

from panoramix.spec import SPEC
from panoramix import canonical


def safe_json_loads(s):
    try:
        return json.loads(s)
    except ValueError:
        print >> sys.stderr, s
        raise


ClientTuple = namedtuple(
    "ClientTuple",
    ["peers", "contributions", "negotiations", "endpoints", "messages"])


def mk_clients(catalog_url):
    client_gen = ApimasClientAdapter(catalog_url)
    client_gen.construct(SPEC)
    client_gen.apply()
    return ClientTuple(**client_gen.get_clients())


def mk_info(resource, operation, ident=None):
    info = {
        "resource": resource,
        "operation": operation,
    }
    if ident is not None:
        info["id"] = ident
    return info


T_STRUCTURAL = "structural"


def mk_by_consensus(consensus_id):
    return {
        "consensus_id": consensus_id,
        "consensus_type": T_STRUCTURAL,
    }


def filter_data_only(lst):
    return [d["data"] for d in lst]


def hash_message(text, sender, recipient):
    hasher = hashlib.sha256()
    hasher.update(text)
    hasher.update(sender)
    hasher.update(recipient)
    return hasher.hexdigest()


def hash_dict_wrap(message_hashes):
    return [{"hash": mh} for mh in sorted(message_hashes)]


INBOX = "INBOX"
OUTBOX = "OUTBOX"
PROCESSBOX = "PROCESSBOX"
ACCEPTED = "ACCEPTED"


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


class PanoramixClient(object):
    catalog_url = None
    clients = None
    backend = None
    crypto_client = None

    def register_catalog_url(self, catalog_url):
        self.catalog_url = catalog_url
        self.clients = mk_clients(catalog_url)

    def register_backend(self, crypto_backend):
        self.backend = importlib.import_module(crypto_backend)

    def register_crypto_client(self, cfg):
        assert self.backend is not None
        self.crypto_client = self.backend.get_client(cfg)

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
                   resource_id=None):
        if negotiation_id:
            r = self.run_contribution(negotiation_id, attrs, accept)
        else:
            request = self.mk_signed_request(attrs)
            kwargs = {"data": request}
            if resource_id is not None:
                kwargs["resource_id"] = resource_id
            r = callpoint(**kwargs)
        outp = r.text
        if outp:
            outp = safe_json_loads(outp)
        return bool(negotiation_id), outp

    def negotiation_create(self):
        request = {}
        payload = {
            "info": mk_info("negotiation", "create"),
            "data": {},
        }
        request = self.mk_signed_request(payload)
        r = self.clients.negotiations.create(data=request)
        return safe_json_loads(r.text)["data"]

    def negotiation_info(self, negotiation_id):
        r = self.clients.negotiations.retrieve(negotiation_id)
        return safe_json_loads(r.text)["data"]

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
        return d["data"]["peer_id"]

    def peer_info(self, peer_id):
        try:
            r = self.clients.peers.retrieve(peer_id)
            return safe_json_loads(r.text)["data"]
        except ApimasClientException:
            return None

    def endpoint_info(self, endpoint_id):
        try:
            r = self.clients.endpoints.retrieve(endpoint_id)
            return safe_json_loads(r.text)["data"]
        except ApimasClientException:
            return None

    def peer_create(self, name, set_key=True, owners=None, consensus_id=None,
                    negotiation_id=None, accept=False):
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

        return self.run_action(attrs, negotiation_id, accept,
                               self.clients.peers.create)

    def peer_import(self, peer_id):
        r = self.clients.peers.retrieve(peer_id)
        d = safe_json_loads(r.text)["data"]
        public_key = d["key_data"]
        self.crypto_client.register_key(public_key)
        return public_key

    def endpoint_create(
            self, endpoint_id, peer_id, endpoint_type, endpoint_params,
            size_min, size_max, description, consensus_id=None,
            negotiation_id=None, accept=False):
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

        return self.run_action(attrs, negotiation_id, accept,
                               self.clients.endpoints.create)

    def contribution_list(self, negotiation_id):
        params = {"negotiation": negotiation_id}

        r = self.clients.contributions.list(params=params)
        contribs = filter_data_only(safe_json_loads(r.text))
        return contribs

    def contribution_accept(self, negotiation_id, contribution_id):
        data = {"id": contribution_id, "negotiation": negotiation_id}
        r = self.clients.contributions.retrieve(contribution_id, params=data)
        contrib = safe_json_loads(r.text)["data"]
        realtext = canonical.from_canonical(
            canonical.from_unicode(contrib["text"]))
        body = realtext["body"]
        r = self.run_contribution(negotiation_id, body, True)
        d = safe_json_loads(r.text)["data"]
        return d

    def prepare_send_message(
            self, endpoint_id, box, text, sender, recipient, send_hash=False):
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
        request = self.mk_signed_request(attrs)
        return request, msg_hash

    def message_send(self, endpoint_id, data, recipients):
        enc_data = self.crypto_client.encrypt(data, recipients)
        send_to = recipients[0]
        keyid = self.crypto_client.get_keyid()
        request, _ = self.prepare_send_message(
            endpoint_id, INBOX, enc_data, keyid, send_to)
        r = self.clients.messages.create(data=request)
        return safe_json_loads(r.text)

    def box_list(self, endpoint_id, box):
        r = self.clients.messages.list(params={
            "endpoint_id": endpoint_id, "box": box})
        ms = safe_json_loads(r.text)
        return filter_data_only(ms)

    def endpoint_action(
            self, endpoint_id, status, properties, on_last_consensus_id=None,
            consensus_id=None, negotiation_id=None, accept=False):

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

        return self.run_action(
            attrs, negotiation_id, accept,
            self.clients.endpoints.partial_update,
            resource_id=endpoint_id)

    def inbox_process(self, endpoint_id, peer_id, upload):
        endpoint_resp = self.clients.endpoints.retrieve(endpoint_id)
        endpoint = safe_json_loads(endpoint_resp.text)["data"]

        r = self.clients.messages.list(params={
            "endpoint_id": endpoint_id, "box": ACCEPTED})
        messages = filter_data_only(safe_json_loads(r.text))

        responses = []
        process_log = {}
        if not messages:
            return responses, process_log

        messages_text = [m["text"] for m in messages]
        processed_data, proof = self.crypto_client.process(
            endpoint, messages_text)
        requests = []
        msg_hashes = []
        for recipient, text in processed_data:
            if recipient is None:
                recipient = "dummy_next_recipient"
            request, msg_hash = self.prepare_send_message(
                endpoint_id, PROCESSBOX, text,
                peer_id, recipient, send_hash=False)
            requests.append(request)
            msg_hashes.append(msg_hash)

        if upload:
            for request in requests:
                r = self.clients.messages.create(data=request)
                d = safe_json_loads(r.text)
                responses.append(d)

        process_log = {
            "message_hashes": hash_dict_wrap(msg_hashes),
            "process_proof": canonical.to_canonical(proof),
        }
        return responses, process_log

    def outbox_forward(self, from_endpoint_id, to_endpoint_id):
        r = self.clients.messages.list(params={
            "endpoint_id": from_endpoint_id, "box": OUTBOX})
        messages = filter_data_only(safe_json_loads(r.text))
        responses = []
        if not messages:
            return responses

        for message in messages:
            request, msg_hash = self.prepare_send_message(
                to_endpoint_id,
                INBOX,
                message["text"],
                message["sender"],
                message["recipient"])
            r = self.clients.messages.create(data=request)
            d = safe_json_loads(r.text)
            responses.append(d)
        return responses
