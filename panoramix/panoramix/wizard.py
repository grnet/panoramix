import argparse
import time

from panoramix import utils
from panoramix.client import filter_data_only, \
    PROCESSBOX, INBOX, OUTBOX, ACCEPTED, NoLinks, InputNotReady
from panoramix import canonical
from panoramix.wizard_common import ui, BACKENDS, abort, client,\
    Block, cfg, retry, on
from panoramix import wizard_common as common

output_cycle = "/tmp/mixnet_cycle"

autodefault = False


def create_provisional_peer_contrib(neg_id, name):
    peer_id = cfg.get("PEER_ID")
    next_neg = read_next_negotiation_id()
    is_contrib, d = client.peer_create(
        name, set_key=False, owners=[peer_id], negotiation_id=neg_id,
        next_negotiation_id=next_neg)
    assert is_contrib
    return d["data"]["id"]


def mk_invitations(num):
    return [utils.generate_random_key() for _ in xrange(num)]


INV_SEP = '|'


def print_information(negotiation_id, contribution_id, invitations):
    combined_invitations = [INV_SEP.join([negotiation_id, inv])
                            for inv in invitations]
    ui.inform("Send invitations to peers:\n  %s" %
              "\n  ".join(combined_invitations))
    ui.inform("Your initial proposal is contribution: %s" % contribution_id)
    return True


def check_invitation(invitations, invitation_id):
    try:
        invitations.remove(invitation_id)
    except KeyError:
        raise ValueError("unrecognized invitation id")


def check_signer(owners, signer):
    try:
        owners.remove(signer)
    except KeyError:
        raise ValueError("unrecognized signer")


def _check_ep_negotiation(negotiation_id, initial_contrib):
    contributions = filter_data_only(client.contribution_list(negotiation_id))
    contributions = [c for c in contributions if c["latest"]]
    combined_peer_id = cfg.get("CREATE_COMBINED_PEER_ID")
    combined_peer = client.peer_info(combined_peer_id)
    owners = set(unpack_owners(combined_peer["owners"]))

    orig_body = None
    for contribution in contributions:
        signer = contribution["signer_key_id"]
        text = get_contribution_text(contribution)
        body = text["body"]
        if orig_body is None:
            orig_body = body
        if orig_body != body:
            raise ValueError("contribution texts differ")
        check_signer(owners, signer)
    if owners:
        raise Block("Contribution pending from: %s" % owners)
    ui.inform("All peer owners have agreed. Sending accept contribution.")
    text = get_contribution_text(initial_contrib)
    body = text["body"]
    meta = text["meta"]
    meta = hash_meta_next_negotiation(meta)
    r = client.run_contribution(
        negotiation_id, body, accept=True, extra_meta=meta)
    d = r.json()
    contribution = d["data"]
    ui.inform("Sent contribution %s" % contribution["id"])
    return contribution


def create_ep_close_contribution(endpoint_id, negotiation_id):
    next_neg = read_next_negotiation_id()
    r = client.close_on_minimum(endpoint_id, negotiation_id,
                                next_negotiation_id=next_neg)
    if r == "wrongstatus":
        abort("Wrong status")
    if r == "nomin":
        raise Block("Waiting until minimum inbox size is reached.")
    is_contrib, d = r
    assert is_contrib
    return d["data"]


def do_processing(endpoint_id, peer_id):
    responses, log = client.inbox_process(endpoint_id, peer_id, upload=True)
    return log


def create_ep_record_contribution(endpoint_id, negotiation_id, log):
    next_neg = read_next_negotiation_id()
    r = client.record_process(endpoint_id, negotiation_id, log,
                              next_negotiation_id=next_neg)
    if r == "wrongstatus":
        abort("Wrong status")
    is_contrib, d = r
    assert is_contrib
    return d["data"]


def apply_endpoint_consensus(endpoint_id, negotiation):
    data = apply_consensus(negotiation)
    endpoint_id = data["endpoint_id"]
    ui.inform("Applied action for endpoint %s." % endpoint_id)
    return endpoint_id


def operate_on_closed_endpoint_coord(endpoint_id):
    setting = suffixed_setting(endpoint_id)
    neg_id = on(setting("PROCESS_NEGOTIATION_ID"),
                new_negotiation_id_from_stream)

    hashes = on(setting("LINKED_PROCESSBOX"),
       lambda: get_endpoint_input(endpoint_id, PROCESSBOX))

    if hashes is None:
        peer_id = cfg.get("PEER_ID")
        log = on(setting("PROCESSING"),
           lambda: do_processing(endpoint_id, peer_id))
    else:
        log = client.mk_process_log(hashes, "", wrap=False)

    contrib = on(setting("PROCESS_CONTRIBUTION"),
       lambda: create_ep_record_contribution(endpoint_id, neg_id, log))
    on(setting("PROCESS_SECOND_CONTRIBUTION"),
       lambda: _check_ep_negotiation(neg_id, contrib))
    finished_neg = on(setting("PROCESS_FINISHED_NEGOTIATION"),
       lambda: finished_negotiation(neg_id))
    on(setting("APPLY_PROCESS"),
       lambda: apply_endpoint_consensus(endpoint_id, finished_neg))


def operate_on_closed_endpoint_contrib(endpoint_id):
    setting = suffixed_setting(endpoint_id)
    neg_id = on(setting("PROCESS_NEGOTIATION_ID"), read_next_negotiation_id)
    contrib = on(setting("PROCESS_COORD_INITIAL_CONTRIBUTION"),
                 lambda: _check_initial_contribution(neg_id))
    register_next_negotiation_id(contrib)

    on(setting("PROCESS_CONTRIBUTION"),
       lambda: join_ep_process_contribution(endpoint_id, neg_id, contrib))
    on(setting("PROCESS_FINISHED_NEGOTIATION"),
       lambda: finished_negotiation(neg_id))


def operate_own_endpoint(endpoint_id):
    setting = suffixed_setting(endpoint_id)
    on(setting("OWN_INBOX"), lambda: get_own_endpoint_input(endpoint_id))
    on(setting("OWN_CLOSE"), lambda: close_own_endpoint(endpoint_id))
    on(setting("OWN_PROCESS"), lambda: process_own_endpoint(endpoint_id))


def suffixed_setting(endpoint_id):
    def f(name):
        return "%s_%s" % (name, endpoint_id)
    return f


def operate_on_open_endpoint_coord(endpoint_id):
    setting = suffixed_setting(endpoint_id)
    neg_id = on(setting("CLOSE_NEGOTIATION_ID"),
                new_negotiation_id_from_stream)

    on(setting("LINKED_INBOX"),
       lambda: get_endpoint_input(endpoint_id, INBOX))

    contrib = on(setting("CLOSE_CONTRIBUTION"),
       lambda: create_ep_close_contribution(endpoint_id, neg_id))

    on(setting("CLOSE_SECOND_CONTRIBUTION"),
       lambda: _check_ep_negotiation(neg_id, contrib))

    finished_neg = on(setting("CLOSE_FINISHED_NEGOTIATION"),
       lambda: finished_negotiation(neg_id))

    on(setting("CREATE_EP_CLOSE_ID"),
       lambda: apply_endpoint_consensus(endpoint_id, finished_neg))


def operate_on_open_endpoint_contrib(endpoint_id):
    setting = suffixed_setting(endpoint_id)
    neg_id = on(setting("CLOSE_NEGOTIATION_ID"), read_next_negotiation_id)

    contrib = on(setting("CLOSE_COORD_INITIAL_CONTRIBUTION"),
                 lambda: _check_initial_contribution(neg_id))
    register_next_negotiation_id(contrib)

    on(setting("CLOSE_CONTRIBUTION"),
       lambda: join_ep_close_contribution(endpoint_id, neg_id, contrib))

    on(setting("CLOSE_FINISHED_NEGOTIATION"),
       lambda: finished_negotiation(neg_id))


OPERATE_DISPATCH = {
    ("OPEN", "create"): operate_on_open_endpoint_coord,
    ("OPEN", "join"): operate_on_open_endpoint_contrib,
    ("CLOSED", "create"): operate_on_closed_endpoint_coord,
    ("CLOSED", "join"): operate_on_closed_endpoint_contrib,
}


def operate(endpoint_ids, peer_id, combined_peer_id, role):
    status = []
    remaining = []
    for endpoint_id in endpoint_ids:
        endpoint = client.endpoint_info(endpoint_id)
        owner = endpoint["peer_id"]
        if owner == peer_id:
            try:
                operate_own_endpoint(endpoint_id)
            except Block:
                remaining.append(endpoint_id)
        elif owner == combined_peer_id:
            status = endpoint["status"]
            if status == "PROCESSED":
                continue
            remaining.append(endpoint_id)
            op = OPERATE_DISPATCH.get((status, role))
            try:
                op(endpoint_id)
            except Block:
                pass
    return remaining


def check_negotiation_wizard(negotiation_id, invitations):
    me = cfg.get("PEER_ID")
    contributions = filter_data_only(client.contribution_list(negotiation_id))
    contributions = [c for c in contributions if c["latest"]]
    signers = [me]
    orig_body = None
    orig_next_negotiation_id = read_next_negotiation_id()
    for contribution in contributions:
        signer = contribution["signer_key_id"]
        text = get_contribution_text(contribution)
        body = text["body"]
        if orig_body is None:
            orig_body = body
        if orig_body != body:
            raise ValueError("contribution texts differ")
        meta = text["meta"]
        invitation_id = meta.get("invitation_id")
        if invitation_id is not None:
            check_invitation(invitations, invitation_id)
            client.peer_import(signer)
            signers.append(signer)
            # print "Imported peer %s" % signer
        elif signer != me:
            raise ValueError("uninvited contribution!")
        next_negotiation_id = meta.get("next_negotiation_id")
        if next_negotiation_id != orig_next_negotiation_id:
            raise ValueError("wrong next_negotiation_id")
    if invitations:
        raise Block("Invitations pending: %s" % invitations)
    ui.inform("All invited peers have joined. Sending accept contribution.")
    name = orig_body["data"]["name"]
    next_negotiation_id = orig_body["info"].get("next_negotiation_id")
    hashed_next_negotiation_id = utils.hash_string(orig_next_negotiation_id)
    is_contrib, d = client.peer_create(
        name, set_key=True, owners=signers,
        negotiation_id=negotiation_id, accept=True,
        next_negotiation_id=hashed_next_negotiation_id)
    assert is_contrib
    contrib_id = d["data"]["id"]
    ui.inform("Your new contribution id is: %s" % contrib_id)
    return contrib_id


def check_consensus(negotiation):
    consensus = negotiation["consensus"]
    if consensus is None:
        raise Block("No consensus yet.")
    ui.inform("Consensus reached: %s" % consensus)
    return negotiation


def get_negotiation_text(negotiation):
    return canonical.from_unicode_canonical(negotiation["text"])


def get_negotiation(negotiation_id):
    return client.negotiation_info(negotiation_id)


def finished_negotiation(negotiation_id):
    negotiation = get_negotiation(negotiation_id)
    return check_consensus(negotiation)


def apply_multipart_consensus(negotiation):
    consensus = negotiation["consensus"]
    text = get_negotiation_text(negotiation)
    ui.inform("Negotiation finished successfully. Applying consensus.")
    rs = client.apply_multipart_consensus(text["body"], consensus)
    return filter_data_only(rs)


def apply_consensus(negotiation):
    consensus = negotiation["consensus"]
    text = get_negotiation_text(negotiation)
    ui.inform("Negotiation finished successfully. Applying consensus.")
    return client.apply_consensus(text["body"], consensus)["data"]


def create_combined_peer(negotiation):
    data = apply_consensus(negotiation)
    peer_id = data["peer_id"]
    ui.inform("Created combined peer %s." % peer_id)
    return peer_id


def prepare_output_file():
    cycle = cfg.get("CYCLE") - 1
    with open(output_cycle, "w") as f:
        f.write("%s" % cycle)
    ui.inform("Wrote cycle id: %s" % cycle)


def create_multiple_endpoints(negotiation):
    data_list = apply_multipart_consensus(negotiation)
    for data in data_list:
        endpoint_id = data["endpoint_id"]
        prepare_output_file()
        ui.inform("Created endpoint %s." % endpoint_id)
    return data_list


def join_combined_peer(negotiation):
    text = get_negotiation_text(negotiation)
    peer_id = text["body"]["data"]["peer_id"]
    peer = client.peer_info(peer_id)
    if peer is not None:
        ui.inform("Combined peer %s is created." % peer_id)
        return peer_id
    raise Block("Waiting for the combined peer to be created.")


def join_combined_endpoint(negotiation):
    text = get_negotiation_text(negotiation)
    endpoints = filter_data_only(text["body"])
    for endpoint_descr in endpoints:
        endpoint_id = endpoint_descr["endpoint_id"]
        endpoint = client.endpoint_info(endpoint_id)
        if endpoint is not None:
            ui.inform("Endpoint '%s' is created." % endpoint_id)
        else:
            raise Block(
                "Waiting for endpoint '%s' to be created." % endpoint_id)
    return endpoints


def register_peer_with_owners(combined_peer_id):
    cfg.set_value("COMBINED_PEER_ID", combined_peer_id)
    peer = client.peer_info(combined_peer_id)
    client.peer_import(combined_peer_id)
    for owner in peer["owners"]:
        client.peer_import(owner["owner_key_id"])


def join_backend_set(contrib):
    text = get_contribution_text(contrib)
    crypto_backend = text["body"]["data"]["crypto_backend"]
    default = "accept"
    response = ui.ask_value("response",
                            "Proposed crypto backend: '%s'; "
                            "'accept' or 'abort'? (default: '%s')" %
                            (crypto_backend, default))
    if not response:
        response = default
    if response == "accept":
        crypto_backend = BACKENDS[crypto_backend]
        return crypto_backend
    elif response == "abort":
        abort()


def join_crypto_params_set(contrib):
    text = get_contribution_text(contrib)
    crypto_params = text["body"]["data"]["crypto_params"]
    crypto_params = canonical.from_unicode_canonical(crypto_params)
    default = "accept"
    response = ui.ask_value("response",
                            "Proposed crypto params: '%s'; "
                            "'accept' or 'abort'? (default: '%s')" %
                            (crypto_params, default))
    if not response:
        response = default
    if response == "accept":
        return crypto_params
    elif response == "abort":
        abort()


def get_contributions(negotiation_id):
    return filter_data_only(client.contribution_list(negotiation_id))


def get_first_contribution(contribs):
    if not contribs:
        return None
    return min(contribs, key=lambda c: c["id"])


def get_latest_of_peer(contribs, peer):
    for contrib in contribs:
        if contrib["signer_key_id"] == peer and contrib["latest"]:
            return contrib
    return None


def get_join_response():
    default = "yes"
    if autodefault:
        return default
    response = ui.ask_value("response",
                            "Send join contribution? (yes/no) (default: '%s')"
                            % default)
    if not response:
        return default
    if response != "yes":
        abort()


def join_contribution(negotiation_id, initial_contrib, invitation_id):
    response = get_join_response()
    text = get_contribution_text(initial_contrib)
    body = text["body"]
    extra_meta = text["meta"].copy()
    extra_meta["invitation_id"] = invitation_id
    r = client.run_contribution(
        negotiation_id, body, accept=False, extra_meta=extra_meta)
    d = r.json()
    contribution_id = d["data"]["id"]
    ui.inform("Sent contribution %s" % contribution_id)
    return contribution_id


def join_ep_close_contribution(endpoint_id, negotiation_id, initial_contrib):
    text = get_contribution_text(initial_contrib)
    body = text["body"]
    suggested_hashes = body["data"]["message_hashes"]
    endpoint = client.endpoint_info(endpoint_id)
    try:
        hashes = get_endpoint_input(endpoint_id, INBOX, dry_run=True)
        if hashes is not None and suggested_hashes != hashes:
            abort("Hash mismatch for linked inbox")
    except (InputNotReady, NoLinks) as e:
        pass

    computed_hashes = client.check_endpoint_on_minimum(endpoint)
    if suggested_hashes != computed_hashes:
        abort("Couldn't agree on message hashes when closing.")
    meta = hash_meta_next_negotiation(text["meta"])
    r = client.run_contribution(
        negotiation_id, body, accept=True, extra_meta=meta)
    d = r.json()
    contribution = d["data"]
    ui.inform("Sent contribution %s" % contribution["id"])
    return contribution


def join_ep_process_contribution(endpoint_id, negotiation_id, initial_contrib):
    text = get_contribution_text(initial_contrib)
    body = text["body"]
    suggested_hashes = body["data"]["message_hashes"]

    r = client.get_input_from_link(
        endpoint_id, PROCESSBOX, serialized=True, dry_run=True)
    if r is None:
        raise ValueError("input is missing")
    responses, computed_hashes = r
    if suggested_hashes != computed_hashes:
        abort("Couldn't agree on message hashes when processing.")
    meta = hash_meta_next_negotiation(text["meta"])
    r = client.run_contribution(
        negotiation_id, body, accept=True, extra_meta=meta)
    d = r.json()
    contribution = d["data"]
    ui.inform("Sent contribution %s" % contribution["id"])
    return contribution


def join_ep_contribution(negotiation_id, initial_contrib):
    response = get_join_response()
    text = get_contribution_text(initial_contrib)
    body = text["body"]
    r = client.run_contribution(negotiation_id, body, accept=False)
    d = r.json()
    contribution = d["data"]
    ui.inform("Sent contribution %s" % contribution["id"])
    return contribution


def get_contribution_text(contribution):
    return canonical.from_unicode_canonical(contribution["text"])


def mk_owner_d(owner):
    return {"owner_key_id": owner}


def unpack_owners(owners):
    return [o["owner_key_id"] for o in owners]


def check_ep_compare_texts(orig_text, new_text):
    orig_body = orig_text["body"]
    new_body = new_text["body"]
    if orig_body != new_body:
        abort("Contribution body has changed.")


def check_compare_texts(orig_text, new_text):
    orig_body = orig_text["body"]
    new_body = new_text["body"]
    me = cfg.get("PEER_ID")
    orig_data = orig_body["data"].copy()
    new_data = new_body["data"].copy()
    orig_owners = orig_data.pop("owners")
    new_owners = new_data.pop("owners")
    orig_data.pop("key_data")
    orig_data.pop("peer_id")
    new_key_data = new_data.pop("key_data")
    new_peer_id = new_data.pop("peer_id")

    if orig_data != new_data:
        abort("Contribution data has changed.")
    if orig_owners[0] not in new_owners:
        abort("Coordinator missing from owners.")
    if mk_owner_d(me) not in new_owners:
        abort("Peer missing from owners.")
    new_owners_list = unpack_owners(new_owners)
    for owner in new_owners_list:
        client.peer_import(owner)
    combined_data = client.crypto_client.combine_keys(new_owners_list)
    combined_key = client.crypto_client.get_key_id_from_key_data(combined_data)
    if combined_data != new_key_data:
        abort("Wrong combined key data.")
    if combined_key != new_peer_id:
        abort("Wrong combined peer id.")


def _join_coord_second_contribution(
        negotiation_id, initial_contrib, for_ep=False):
    coordinator = initial_contrib["signer_key_id"]
    contributions = get_contributions(negotiation_id)
    contrib = get_latest_of_peer(contributions, coordinator)
    assert contrib is not None
    if initial_contrib["id"] == contrib["id"]:
        raise Block("Waiting for the negotiation's second round.")
    text = get_contribution_text(contrib)
    meta = text["meta"]
    if not meta["accept"]:
        abort("Not an accepted contribution.")
    initial_text = get_contribution_text(initial_contrib)
    check = check_ep_compare_texts if for_ep else check_compare_texts
    check(initial_text, text)
    return contrib


def hash_meta_next_negotiation(meta):
    next_negotiation_id = meta["next_negotiation_id"]
    meta["next_negotiation_id"] = utils.hash_string(next_negotiation_id)
    return meta


def check_hashed_next_negotiation_id(meta):
    next_negotiation_id = read_next_negotiation_id()
    hashed_next_negotiation_id = meta.get("next_negotiation_id")
    if hashed_next_negotiation_id != utils.hash_string(next_negotiation_id):
        raise ValueError("wrong next_negotiation_id hash")


def _join_second_contribution(negotiation_id, contrib):
    text = get_contribution_text(contrib)
    body = text["body"]
    meta = text["meta"]
    check_hashed_next_negotiation_id(meta)
    ui.inform("Sending second join contribution.")

    r = client.run_contribution(
        negotiation_id, body, accept=True, extra_meta=meta)
    d = r.json()
    contribution_id = d["data"]["id"]
    ui.inform("Sent contribution %s" % contribution_id)
    return contribution_id


def _check_initial_contribution(negotiation_id):
    contributions = get_contributions(negotiation_id)
    contrib = get_first_contribution(contributions)
    if contrib is None:
        raise Block("Waiting for first contribution")
    return contrib


def get_next_neg_from_contrib(contrib):
    text = get_contribution_text(contrib)
    meta = text["meta"]
    return meta.get("next_negotiation_id")


def register_next_negotiation_id(contrib):
    next_neg = get_next_neg_from_contrib(contrib)
    set_next_negotiation_id(next_neg)


def initial_contribution_info(contrib):
    register_next_negotiation_id(contrib)
    contrib_id = contrib["id"]
    signer = contrib["signer_key_id"]
    ui.inform("Negotiation initialized by peer %s with contribution %s." % (
        signer, contrib_id))


def register_crypto_backend(crypto_backend):
    cfg.set_value("CRYPTO_BACKEND", crypto_backend)
    client.register_backend(crypto_backend)


def crypto_params_wizard():
    return common.crypto_params_wizard_on(client)


def key_and_peer_wizard():
    on("KEY", common.set_key_wizard)
    client.register_crypto_client(cfg)
    name = on("PEER_NAME", lambda: utils.locale_to_unicode(
        ui.ask_value("PEER_NAME", "Specify name to register as peer")))
    peer_id = on("PEER_ID", lambda: do_register_wizard(name))
    client.peer_import(peer_id)


def create_contribution_id(negotiation_id):
    name = utils.locale_to_unicode(
        ui.ask_value("name", "Choose mixnet peer name"))
    return create_provisional_peer_contrib(negotiation_id, name)


def create_invitations():
    num = int(ui.ask_value("invitations",
                           "Give number of invitations to create"))
    return mk_invitations(num)


def do_register_wizard(peer_name):
    peer = client.with_self_consensus(
        client.peer_create, {"name": peer_name})
    peer_id = peer["peer_id"]
    ui.inform("Registered peer with PEER_ID: %s" % peer_id)
    return peer_id


def new_negotiation_id():
    return client.negotiation_create()["id"]


def get_min_size():
    return int(ui.ask_value("MIN_SIZE", "Specify minimum size"))


def get_max_size():
    return int(ui.ask_value("MAX_SIZE", "Specify maximum size: "))


def get_endpoint_name():
    return utils.locale_to_unicode(ui.ask_value(
        "ENDPOINT_NAME", "Specify endpoint name to create on combined peer"))


def get_endpoint_id(cycle):
    name = on("ENDPOINT_NAME", get_endpoint_name)
    endpoint_id = "%s_%s" % (name, cycle)
    return endpoint_id


def create_ep_contribution(cycle, negotiation_id, peer_id):
    peer = client.peer_info(peer_id)
    owners = sorted(unpack_owners(peer["owners"]))
    endpoint_id = get_endpoint_id(cycle)
    size_min = on("MIN_SIZE", get_min_size)
    size_max = on("MAX_SIZE", get_max_size)
    next_neg = read_next_negotiation_id()

    attrs = client.backend.make_description(
        endpoint_id, peer_id, owners, size_min, size_max)

    d = client.endpoints_create_contribution(
        attrs, negotiation_id, accept=False, next_negotiation_id=next_neg)
    return d["data"]


def inform_send_message(endpoints):
    public_endpoint = [e for e in endpoints if e["public"]][0]
    public_endpoint_href = client.mk_endpoint_hyperlink(
        public_endpoint["endpoint_id"])
    ui.inform("Ready to accept messages to mixnet %s\n." %
              public_endpoint_href)


def split_invitation(invitation):
    parts = invitation.split(INV_SEP)
    cfg.set_value("JOIN_NEGOTIATION_ID", parts[0])
    cfg.set_value("JOIN_INVITATION_ID", parts[1])
    return parts


def join_mixnet_wizard():
    inv = on("JOIN_INVITATION",
             lambda: ui.ask_value("JOIN_INVITATION",
                                  "Give invitation to create mix peer"))

    negotiation_id, invitation_id = split_invitation(inv)
    contrib = on("JOIN_COORD_INITIAL_CONTRIBUTION",
                 lambda: _check_initial_contribution(negotiation_id))
    initial_contribution_info(contrib)

    backend = on("JOIN_CRYPTO_BACKEND",
                 lambda: join_backend_set(contrib))
    register_crypto_backend(backend)

    crypto_params = on("JOIN_CRYPTO_PARAMS",
                       lambda: join_crypto_params_set(contrib))
    on("CRYPTO_PARAMS", lambda: crypto_params)
    key_and_peer_wizard()

    on("JOIN_CONTRIBUTION_ID",
       lambda: join_contribution(negotiation_id, contrib, invitation_id))

    second_contrib = on(
        "JOIN_COORD_SECOND_CONTRIBUTION",
        retry(
            lambda: _join_coord_second_contribution(negotiation_id, contrib)))

    on("JOIN_SECOND_CONTRIBUTION_ID",
       lambda: _join_second_contribution(negotiation_id, second_contrib))

    finished_neg = on("JOIN_FINISHED_NEGOTIATION",
                      retry(lambda: finished_negotiation(negotiation_id)))

    combined_peer_id = on("COMBINED_PEER_ID",
                          retry(lambda: join_combined_peer(finished_neg)))
    register_peer_with_owners(combined_peer_id)


def join_endpoint_wizard(cycle):
    setting = suffixed_setting(cycle)
    neg_id = on(setting("EP_NEGOTIATION_ID"), read_next_negotiation_id)

    contrib = on(setting("EP_COORD_INITIAL_CONTRIBUTION"),
                 retry(lambda: _check_initial_contribution(neg_id)))
    register_next_negotiation_id(contrib)

    on(setting("EP_CONTRIBUTION"),
       lambda: join_ep_contribution(neg_id, contrib))

    second_contrib = on(setting("EP_COORD_SECOND_CONTRIBUTION"),
                        retry(lambda: _join_coord_second_contribution(
                            neg_id, contrib, for_ep=True)))

    on(setting("EP_SECOND_CONTRIBUTION_ID"),
       lambda: _join_second_contribution(neg_id, second_contrib))

    finished_neg = on(setting("EP_FINISHED_NEGOTIATION"),
                      retry(lambda: finished_negotiation(neg_id)))

    endpoints = on(setting("EP_COMBINED_ID"),
                   retry(lambda: join_combined_endpoint(finished_neg)))
    inform_send_message(endpoints)
    return endpoints


def get_restart_response(role):
    if autodefault:
        return "yes"
    default = "yes"
    verb = role.capitalize()
    response = ui.ask_value(
        "RESTART", "%s a new cycle? (yes/no) (default: %s): " %
        (verb, default))
    if not response:
        return "yes"
    if response != "yes":
        exit()


def create_mixnet_wizard():
    backend = on("CREATE_CRYPTO_BACKEND", common.select_backend_wizard)
    register_crypto_backend(backend)
    crypto_params = on("CREATE_CRYPTO_PARAMS", crypto_params_wizard)
    on("CRYPTO_PARAMS", lambda: crypto_params)
    key_and_peer_wizard()
    neg_id = on("CREATE_NEGOTIATION_ID", new_negotiation_id_from_stream)
    contrib = on("CREATE_CONTRIBUTION_ID",
                 lambda: create_contribution_id(neg_id))
    invitations = on("CREATE_INVITATIONS", create_invitations)
    on("CREATE_INFORM",
       lambda: print_information(neg_id, contrib, invitations))
    on("CREATE_SECOND_CONTRIBUTION_ID",
       retry(lambda: check_negotiation_wizard(neg_id, invitations)))
    finished_neg = on("CREATE_FINISHED_NEGOTIATION",
                      retry(lambda: finished_negotiation(neg_id)))

    combined_peer_id = on("CREATE_COMBINED_PEER_ID",
       lambda: create_combined_peer(finished_neg))
    register_peer_with_owners(combined_peer_id)


def set_next_negotiation_id(value):
    cfg.set_value("NEXT_NEGOTIATION_ID", value)


def create_next_negotiation_id():
    value = new_negotiation_id()
    cfg.set_value("NEXT_NEGOTIATION_ID", value)


def read_next_negotiation_id():
    return cfg.get("NEXT_NEGOTIATION_ID")


def new_negotiation_id_from_stream():
    neg_id = read_next_negotiation_id()
    if neg_id is None:
        neg_id = new_negotiation_id()
    create_next_negotiation_id()
    return neg_id


def create_endpoint_wizard(cycle, combined_peer_id):
    setting = suffixed_setting(cycle)
    neg_id = on(setting("EP_NEGOTIATION_ID"), new_negotiation_id_from_stream)
    contrib = on(setting("EP_CONTRIBUTION"),
                 lambda: create_ep_contribution(
                     cycle, neg_id, combined_peer_id))

    on(setting("EP_SECOND_CONTRIBUTION"),
       retry(lambda: _check_ep_negotiation(neg_id, contrib)))

    finished_neg = on(setting("EP_FINISHED_NEGOTIATION"),
        retry(lambda: finished_negotiation(neg_id)))
    endpoints = on(setting("ENDPOINTS"),
       lambda: create_multiple_endpoints(finished_neg))
    inform_send_message(endpoints)
    return endpoints


def mixnet_creation_wizard(role):
    if role == "create":
        create_mixnet_wizard()
    elif role == "join":
        join_mixnet_wizard()


def get_endpoint_input(endpoint_id, box, dry_run=False):
    try:
        responses, msg_hashes = client.get_input_from_link(
            endpoint_id, box, serialized=True, dry_run=dry_run)
        if not dry_run:
            ui.inform("Collected input for %s of '%s'." % (box, endpoint_id))
        return msg_hashes
    except InputNotReady:
        m = "Waiting to collect %s for endpoint '%s'" % (box, endpoint_id)
        raise Block(m)
    except NoLinks:
        return None


def get_own_endpoint_input(endpoint_id):
    try:
        r = client.get_input_from_link(endpoint_id, INBOX)
        ui.inform("Collected input for inbox of %s." % endpoint_id)
    except InputNotReady:
        raise Block("Waiting to collect inbox.")
    return endpoint_id


def close_own_endpoint(endpoint_id):
    params = client.close_on_minimum_prepare(endpoint_id)
    if params == "wrongstatus":
        abort("Wrong status")
    if params == "nomin":
        raise Block("Waiting until minimum inbox size is reached.")
    endpoint = client.with_self_consensus(client.endpoint_action, params)
    endpoint_id = endpoint["endpoint_id"]
    ui.inform("Closed endpoint %s" % endpoint_id)
    return endpoint_id


def process_own_endpoint(endpoint_id):
    peer_id = cfg.get("PEER_ID")
    messages, log = client.inbox_process(
        endpoint_id, peer_id, upload=True)
    params = client.record_process_prepare(endpoint_id, log)
    if params == "wrongstatus":
        abort("Wrong status")
    endpoint = client.with_self_consensus(client.endpoint_action, params)
    endpoint_id = endpoint["endpoint_id"]
    ui.inform("Processed endpoint %s" % endpoint_id)
    return endpoint_id


def handle_endpoints_wizard(role):
    while True:
        cycle = on("CYCLE", lambda: 1)

        peer_id = cfg.get("PEER_ID")
        combined_peer_id = cfg.get("COMBINED_PEER_ID")

        if role == "create":
            endpoints = create_endpoint_wizard(cycle, combined_peer_id)
        elif role == "join":
            endpoints = join_endpoint_wizard(cycle)

        endpoint_ids = [e["endpoint_id"] for e in endpoints]
        remaining = endpoint_ids
        while remaining:
            ui.inform("Still need to handle endpoints %s." % remaining)
            remaining = operate(remaining, peer_id, combined_peer_id, role)
            time.sleep(3)
        get_restart_response(role)
        ui.inform("Starting a new cycle...")
        cfg.set_value("CYCLE", cycle + 1)


def set_catalog_url_wizard():
    default = "http://127.0.0.1:8000/"
    response = ui.ask_value("CATALOG_URL",
                            "Set CATALOG_URL (default: '%s')" % default)
    if not response:
        response = default
    return response


parser = argparse.ArgumentParser(description='Panoramix wizard.')
parser.add_argument('--yes', default=False, action="store_true",
                    help='auto-accept questions')


def main():
    args = parser.parse_args()
    global autodefault
    autodefault = args.yes
    ui.inform("Welcome to Panoramix wizard!")
    ui.inform("Configuration file is: %s" % common.config_file)
    ui.inform("Set PANORAMIX_CONFIG environment variable to override")
    catalog_url = on("CATALOG_URL", set_catalog_url_wizard)
    client.register_catalog_url(catalog_url)
    role = on("SETUP_ROLE",
              lambda: ui.ask_value("role", "Choose 'create' or 'join' mixnet"))
    mixnet_creation_wizard(role)
    handle_endpoints_wizard(role)


if __name__ == "__main__":
    main()
