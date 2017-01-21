import argparse

from panoramix import utils
from panoramix.client import safe_json_loads, filter_data_only
from panoramix import canonical
from panoramix.wizard_common import ui, BACKENDS, abort, client,\
    Block, cfg
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


def print_information():
    negotiation_id = cfg.get("CREATE_NEGOTIATION_ID")
    contribution_id = cfg.get("CREATE_CONTRIBUTION_ID")
    invitations = cfg.get("CREATE_INVITATIONS")
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
    r = client.run_contribution(
        negotiation_id, body, accept=True)
    d = safe_json_loads(r.text)
    contribution = d["data"]
    ui.inform("Sent contribution %s" % contribution["id"])
    return contribution


def check_ep_negotiation_wizard():
    negotiation_id = cfg.get("CREATE_EP_NEGOTIATION_ID")
    initial_contrib = cfg.get("CREATE_EP_CONTRIBUTION")
    return _check_ep_negotiation(negotiation_id, initial_contrib)


def check_ep_close_negotiation_wizard():
    negotiation_id = cfg.get("CREATE_EP_CLOSE_NEGOTIATION_ID")
    initial_contrib = cfg.get("CREATE_EP_CLOSE_CONTRIBUTION")
    return _check_ep_negotiation(negotiation_id, initial_contrib)


def check_ep_process_negotiation_wizard():
    negotiation_id = cfg.get("CREATE_EP_PROCESS_NEGOTIATION_ID")
    initial_contrib = cfg.get("CREATE_EP_PROCESS_CONTRIBUTION")
    return _check_ep_negotiation(negotiation_id, initial_contrib)


def create_ep_close_contribution():
    endpoint_id = cfg.get("EP_COMBINED_ID")
    negotiation_id = cfg.get("CREATE_EP_CLOSE_NEGOTIATION_ID")
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


def create_ep_process_contribution():
    peer_id = cfg.get("COMBINED_PEER_ID")
    endpoint_id = cfg.get("EP_COMBINED_ID")
    negotiation_id = cfg.get("CREATE_EP_PROCESS_NEGOTIATION_ID")
    messages, log = client.inbox_process(
        endpoint_id, peer_id, upload=True)
    next_neg = read_next_negotiation_id()
    r = client.record_process(endpoint_id, negotiation_id, log,
                              next_negotiation_id=next_neg)
    if r == "wrongstatus":
        abort("Wrong status")
    is_contrib, d = r
    assert is_contrib
    return d["data"]


def check_negotiation_wizard():
    negotiation_id = cfg.get("CREATE_NEGOTIATION_ID")
    invitations = set(cfg.get("CREATE_INVITATIONS"))
    me = cfg.get("PEER_ID")
    contributions = filter_data_only(client.contribution_list(negotiation_id))
    contributions = [c for c in contributions if c["latest"]]
    signers = [me]
    orig_body = None
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
    if invitations:
        raise Block("Invitations pending: %s" % invitations)
    ui.inform("All invited peers have joined. Sending accept contribution.")
    name = orig_body["data"]["name"]
    next_negotiation_id = orig_body["info"].get("next_negotiation_id")
    is_contrib, d = client.peer_create(
        name, set_key=True, owners=signers,
        negotiation_id=negotiation_id, accept=True,
        next_negotiation_id=next_negotiation_id)
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
    return canonical.from_canonical(
        canonical.from_unicode(negotiation["text"]))


def get_negotiation(negotiation_id):
    return client.negotiation_info(negotiation_id)


def finished_negotiation(neg_setting):
    negotiation_id = cfg.get(neg_setting)
    negotiation = get_negotiation(negotiation_id)
    return check_consensus(negotiation)


def apply_consensus(negotiation):
    consensus = negotiation["consensus"]
    text = get_negotiation_text(negotiation)
    ui.inform("Negotiation finished successfully. Applying consensus.")
    return client.apply_consensus(text["body"], consensus)["data"]


def create_combined_peer():
    negotiation = cfg.get("CREATE_FINISHED_NEGOTIATION")
    data = apply_consensus(negotiation)
    peer_id = data["peer_id"]
    ui.inform("Created combined peer %s." % peer_id)
    return peer_id


def prepare_output_file():
    cycle = cfg.get("CYCLE") - 1
    with open(output_cycle, "w") as f:
        f.write("%s" % cycle)
    ui.inform("Wrote cycle id: %s" % cycle)


def create_combined_endpoint():
    negotiation = cfg.get("CREATE_EP_FINISHED_NEGOTIATION")
    data = apply_consensus(negotiation)
    endpoint_id = data["endpoint_id"]
    prepare_output_file()
    ui.inform("Created endpoint %s." % endpoint_id)
    return endpoint_id


def create_close_endpoint():
    negotiation = cfg.get("CREATE_EP_CLOSE_FINISHED_NEGOTIATION")
    data = apply_consensus(negotiation)
    endpoint_id = data["endpoint_id"]
    ui.inform("Closed endpoint %s." % endpoint_id)
    return endpoint_id


def create_process_endpoint():
    negotiation = cfg.get("CREATE_EP_PROCESS_FINISHED_NEGOTIATION")
    data = apply_consensus(negotiation)
    endpoint_id = data["endpoint_id"]
    ui.inform("Processed endpoint %s." % endpoint_id)
    rs = client.messages_forward(endpoint_id)
    ui.inform("Forwarded %s messages" % len(rs))
    return endpoint_id


def join_combined_peer():
    negotiation = cfg.get("JOIN_FINISHED_NEGOTIATION")
    text = get_negotiation_text(negotiation)
    peer_id = text["body"]["data"]["peer_id"]
    peer = client.peer_info(peer_id)
    if peer is not None:
        ui.inform("Combined peer %s is created." % peer_id)
        return peer_id
    raise Block("Waiting for the combined peer to be created.")


def join_combined_endpoint():
    negotiation = cfg.get("JOIN_EP_FINISHED_NEGOTIATION")
    text = get_negotiation_text(negotiation)
    endpoint_id = text["body"]["data"]["endpoint_id"]
    endpoint = client.endpoint_info(endpoint_id)
    if endpoint is not None:
        ui.inform("Combined endpoint %s is created." % endpoint_id)
        return endpoint_id
    raise Block("Waiting for the Combined endpoint to be created.")


def register_peer_with_owners(combined_peer_id):
    cfg.set_value("COMBINED_PEER_ID", combined_peer_id)
    peer = client.peer_info(combined_peer_id)
    client.peer_import(combined_peer_id)
    for owner in peer["owners"]:
        client.peer_import(owner["owner_key_id"])


def join_backend_set():
    contrib = cfg.get("JOIN_COORD_INITIAL_CONTRIBUTION")
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


def join_crypto_params_set():
    contrib = cfg.get("JOIN_COORD_INITIAL_CONTRIBUTION")
    text = get_contribution_text(contrib)
    crypto_params = text["body"]["data"]["crypto_params"]
    crypto_params = canonical.from_canonical(
        canonical.from_unicode(crypto_params))
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


def join_contribution():
    response = get_join_response()
    negotiation_id = cfg.get("JOIN_NEGOTIATION_ID")
    initial_contrib = cfg.get("JOIN_COORD_INITIAL_CONTRIBUTION")
    invitation_id = cfg.get("JOIN_INVITATION_ID")
    text = get_contribution_text(initial_contrib)
    body = text["body"]
    extra_meta = text["meta"].copy()
    extra_meta["invitation_id"] = invitation_id
    r = client.run_contribution(
        negotiation_id, body, accept=False, extra_meta=extra_meta)
    d = safe_json_loads(r.text)
    contribution_id = d["data"]["id"]
    ui.inform("Sent contribution %s" % contribution_id)
    return contribution_id


def join_ep_close_contribution():
    endpoint_id = cfg.get("EP_COMBINED_ID")
    negotiation_id = cfg.get("JOIN_EP_CLOSE_NEGOTIATION_ID")
    initial_contrib = cfg.get("JOIN_EP_CLOSE_COORD_INITIAL_CONTRIBUTION")
    text = get_contribution_text(initial_contrib)
    body = text["body"]
    suggested_hashes = body["data"]["message_hashes"]
    endpoint = client.endpoint_info(endpoint_id)
    computed_hashes = client.check_endpoint_on_minimum(endpoint)
    if suggested_hashes != computed_hashes:
        abort("Couldn't agree on message hashes.")
    r = client.run_contribution(negotiation_id, body, accept=True)
    d = safe_json_loads(r.text)
    contribution = d["data"]
    ui.inform("Sent contribution %s" % contribution["id"])
    return contribution


def join_ep_process_contribution():
    peer_id = cfg.get("COMBINED_PEER_ID")
    endpoint_id = cfg.get("EP_COMBINED_ID")
    negotiation_id = cfg.get("JOIN_EP_PROCESS_NEGOTIATION_ID")
    initial_contrib = cfg.get("JOIN_EP_PROCESS_COORD_INITIAL_CONTRIBUTION")
    text = get_contribution_text(initial_contrib)
    body = text["body"]
    suggested_hashes = body["data"]["message_hashes"]
    msgs, log = client.inbox_process(endpoint_id, peer_id, upload=False)
    computed_hashes = log["message_hashes"]
    if suggested_hashes != computed_hashes:
        abort("Couldn't agree on message hashes.")
    r = client.run_contribution(negotiation_id, body, accept=True)
    d = safe_json_loads(r.text)
    contribution = d["data"]
    ui.inform("Sent contribution %s" % contribution["id"])
    return contribution


def join_ep_contribution():
    response = get_join_response()
    negotiation_id = cfg.get("JOIN_EP_NEGOTIATION_ID")
    initial_contrib = cfg.get("JOIN_EP_COORD_INITIAL_CONTRIBUTION")
    text = get_contribution_text(initial_contrib)
    body = text["body"]
    r = client.run_contribution(negotiation_id, body, accept=False)
    d = safe_json_loads(r.text)
    contribution = d["data"]
    ui.inform("Sent contribution %s" % contribution["id"])
    return contribution


def get_contribution_text(contribution):
    return canonical.from_canonical(
        canonical.from_unicode(contribution["text"]))


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


def join_coord_second_contribution():
    negotiation_id = cfg.get("JOIN_NEGOTIATION_ID")
    initial_contrib = cfg.get("JOIN_COORD_INITIAL_CONTRIBUTION")
    return _join_coord_second_contribution(
        negotiation_id, initial_contrib)


def join_ep_coord_second_contribution():
    negotiation_id = cfg.get("JOIN_EP_NEGOTIATION_ID")
    initial_contrib = cfg.get("JOIN_EP_COORD_INITIAL_CONTRIBUTION")
    return _join_coord_second_contribution(
        negotiation_id, initial_contrib, for_ep=True)


def _join_second_contribution(negotiation_id, contrib):
    text = get_contribution_text(contrib)
    body = text["body"]
    ui.inform("Sending second join contribution.")

    r = client.run_contribution(negotiation_id, body, accept=True)
    d = safe_json_loads(r.text)
    contribution_id = d["data"]["id"]
    ui.inform("Sent contribution %s" % contribution_id)
    return contribution_id


def join_second_contribution():
    negotiation_id = cfg.get("JOIN_NEGOTIATION_ID")
    contrib = cfg.get("JOIN_COORD_SECOND_CONTRIBUTION")
    return _join_second_contribution(negotiation_id, contrib)


def join_ep_second_contribution():
    negotiation_id = cfg.get("JOIN_EP_NEGOTIATION_ID")
    contrib = cfg.get("JOIN_EP_COORD_SECOND_CONTRIBUTION")
    return _join_second_contribution(negotiation_id, contrib)


def _check_initial_contribution(negotiation_id):
    contributions = get_contributions(negotiation_id)
    contrib = get_first_contribution(contributions)
    if contrib is None:
        raise Block("Waiting for first contribution")
    return contrib


def check_initial_contribution():
    negotiation_id = cfg.get("JOIN_NEGOTIATION_ID")
    return _check_initial_contribution(negotiation_id)


def check_ep_initial_contribution():
    negotiation_id = cfg.get("JOIN_EP_NEGOTIATION_ID")
    return _check_initial_contribution(negotiation_id)


def check_ep_close_initial_contribution():
    negotiation_id = cfg.get("JOIN_EP_CLOSE_NEGOTIATION_ID")
    return _check_initial_contribution(negotiation_id)


def check_ep_process_initial_contribution():
    negotiation_id = cfg.get("JOIN_EP_PROCESS_NEGOTIATION_ID")
    return _check_initial_contribution(negotiation_id)


def get_next_neg_from_contrib(contrib):
    text = get_contribution_text(contrib)
    body = text["body"]
    return body["info"].get("next_negotiation_id")


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
    on("PEER_NAME", lambda: ui.ask_value(
        "PEER_NAME", "Specify name to register as peer"))
    on("PEER_ID", do_register_wizard, client.peer_import)


def create_contribution_id():
    name = ui.ask_value("name", "Choose mixnet peer name")
    negotiation_id = cfg.get("CREATE_NEGOTIATION_ID")
    return create_provisional_peer_contrib(negotiation_id, name)


def create_invitations():
    num = int(ui.ask_value("invitations",
                           "Give number of invitations to create"))
    return mk_invitations(num)


def do_register_wizard():
    peer_name = cfg.get("PEER_NAME")
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


def get_description():
    return ui.ask_value("EP_DESCRIPTION", "Give description: ")


def get_endpoint_type():
    types = client.backend.ENDPOINT_TYPES
    default = types[0]
    endpoint_type = ui.ask_value(
        "ENDPOINT_TYPE",
        "Select endpoint type, one of %s (default: %s)" %
        (", ".join(types), default))
    if not endpoint_type:
        endpoint_type = default
    return endpoint_type


def get_endpoint_name():
    return ui.ask_value(
        "ENDPOINT_NAME", "Specify endpoint name to create on combined peer")


def get_endpoint_id():
    name = on("ENDPOINT_NAME", get_endpoint_name)
    cycle = cfg.get("CYCLE", default=1)
    endpoint_id = "%s_%s" % (name, cycle)
    cfg.set_value("ENDPOINT_ID", endpoint_id)
    cfg.set_value("CYCLE", cycle + 1)
    return endpoint_id


def create_ep_contribution():
    negotiation_id = cfg.get("CREATE_EP_NEGOTIATION_ID")
    peer_id = cfg.get("CREATE_COMBINED_PEER_ID")
    endpoint_id = get_endpoint_id()
    endpoint_type = on("ENDPOINT_TYPE", get_endpoint_type)
    size_min = on("MIN_SIZE", get_min_size)
    size_max = on("MAX_SIZE", get_max_size)
    description = on("EP_DESCRIPTION", get_description)
    required_params = client.backend.REQUIRED_PARAMS.get(endpoint_type, [])
    params = {}
    for key in required_params:
        value = ui.ask_value(key, "Specify %s: " % key)
        params[key] = value
    endpoint_params = canonical.to_canonical(params)
    next_neg = read_next_negotiation_id()
    is_contrib, d = client.endpoint_create(
        endpoint_id, peer_id, endpoint_type, endpoint_params, size_min,
        size_max, description, negotiation_id=negotiation_id,
        next_negotiation_id=next_neg)
    assert is_contrib
    return d["data"]


def _inform_send_message(endpoint_id, peer_id):
    cfg.set_value("EP_COMBINED_ID", endpoint_id)
    peer_href = client.mk_peer_hyperlink(peer_id)
    ui.inform("Read to accept messages to mixnet %s\n (endpoint '%s')." %
              (peer_href, endpoint_id))


def inform_send_message(endpoint_id):
    peer_id = cfg.get("CREATE_COMBINED_PEER_ID")
    return _inform_send_message(endpoint_id, peer_id)


def inform_join_send_message(endpoint_id):
    peer_id = cfg.get("JOIN_COMBINED_PEER_ID")
    return _inform_send_message(endpoint_id, peer_id)


def split_invitation(invitation):
    [negotiation_id, invitation_id] = invitation.split(INV_SEP)
    cfg.set_value("JOIN_NEGOTIATION_ID", negotiation_id)
    cfg.set_value("JOIN_INVITATION_ID", invitation_id)


def join_mixnet_wizard():
    on("JOIN_INVITATION",
       lambda: ui.ask_value("JOIN_INVITATION",
                            "Give invitation to create mix peer"),
       split_invitation)
    on("JOIN_COORD_INITIAL_CONTRIBUTION",
       check_initial_contribution, initial_contribution_info)
    on("JOIN_CRYPTO_BACKEND", join_backend_set, register_crypto_backend)
    on("JOIN_CRYPTO_PARAMS",
       join_crypto_params_set, cfg.copy_to("CRYPTO_PARAMS"))
    key_and_peer_wizard()
    on("JOIN_CONTRIBUTION_ID", join_contribution)
    on("JOIN_COORD_SECOND_CONTRIBUTION", join_coord_second_contribution)
    on("JOIN_SECOND_CONTRIBUTION_ID", join_second_contribution)
    on("JOIN_FINISHED_NEGOTIATION",
       lambda: finished_negotiation("JOIN_NEGOTIATION_ID"))
    on("JOIN_COMBINED_PEER_ID", join_combined_peer, register_peer_with_owners)


def join_endpoint_wizard():
    on("JOIN_EP_NEGOTIATION_ID", read_next_negotiation_id)
    on("JOIN_EP_COORD_INITIAL_CONTRIBUTION",
       check_ep_initial_contribution, register_next_negotiation_id)
    on("JOIN_EP_CONTRIBUTION", join_ep_contribution)
    on("JOIN_EP_COORD_SECOND_CONTRIBUTION", join_ep_coord_second_contribution)
    on("JOIN_EP_SECOND_CONTRIBUTION_ID", join_ep_second_contribution)
    on("JOIN_EP_FINISHED_NEGOTIATION",
       lambda: finished_negotiation("JOIN_EP_NEGOTIATION_ID"))

    on("JOIN_EP_COMBINED_ID", join_combined_endpoint, inform_join_send_message)


def _join_sphinxmix_wizard():
    join_endpoint_wizard()
    on("PEER_ENDPOINT", create_individual_endpoint)
    on("JOIN_EP_CLOSE_NEGOTIATION_ID", read_next_negotiation_id)
    on("JOIN_EP_CLOSE_COORD_INITIAL_CONTRIBUTION",
       check_ep_close_initial_contribution, register_next_negotiation_id)

    on("JOIN_EP_CLOSE_CONTRIBUTION", join_ep_close_contribution)
    on("JOIN_EP_CLOSE_FINISHED_NEGOTIATION",
       lambda: finished_negotiation("JOIN_EP_CLOSE_NEGOTIATION_ID"))

    on("JOIN_EP_PROCESS_NEGOTIATION_ID", read_next_negotiation_id)
    on("JOIN_EP_PROCESS_COORD_INITIAL_CONTRIBUTION",
       check_ep_process_initial_contribution, register_next_negotiation_id)

    on("JOIN_EP_PROCESS_CONTRIBUTION", join_ep_process_contribution)
    on("JOIN_EP_PROCESS_FINISHED_NEGOTIATION",
       lambda: finished_negotiation("JOIN_EP_PROCESS_NEGOTIATION_ID"))

    on("OWN_CLOSE", close_own_endpoint)
    on("OWN_PROCESS", process_own_endpoint)


def join_sphinxmix_wizard():
    while True:
        _join_sphinxmix_wizard()
        join_new_cycle_wizard()


def get_join_restart_response():
    if autodefault:
        return "yes"
    default = "yes"
    response = ui.ask_value(
        "RESTART", "Join a new cycle? (yes/no) (default: %s): " % default)
    if not response:
        return "yes"
    if response != "yes":
        exit()


def join_new_cycle_wizard():
    response = get_join_restart_response()
    ui.inform("Starting a new cycle...")
    cycle_settings = [
        "JOIN_EP_NEGOTIATION_ID", "JOIN_EP_COORD_INITIAL_CONTRIBUTION",
        "JOIN_EP_CONTRIBUTION", "JOIN_EP_COORD_SECOND_CONTRIBUTION",
        "JOIN_EP_SECOND_CONTRIBUTION_ID", "JOIN_EP_FINISHED_NEGOTIATION",
        "JOIN_EP_COMBINED_ID", "PEER_ENDPOINT",
        "JOIN_EP_CLOSE_NEGOTIATION_ID",
        "JOIN_EP_CLOSE_COORD_INITIAL_CONTRIBUTION",
        "JOIN_EP_CLOSE_CONTRIBUTION", "JOIN_EP_CLOSE_FINISHED_NEGOTIATION",
        "JOIN_EP_PROCESS_NEGOTIATION_ID",
        "JOIN_EP_PROCESS_COORD_INITIAL_CONTRIBUTION",
        "JOIN_EP_PROCESS_CONTRIBUTION", "JOIN_EP_PROCESS_FINISHED_NEGOTIATION",
        "OWN_CLOSE", "OWN_PROCESS",
    ]
    for s in cycle_settings:
        cfg.pop(s)


def create_mixnet_wizard():
    on("CREATE_CRYPTO_BACKEND",
       common.select_backend_wizard, register_crypto_backend)
    on("CREATE_CRYPTO_PARAMS",
       crypto_params_wizard, cfg.copy_to("CRYPTO_PARAMS"))
    key_and_peer_wizard()
    on("CREATE_NEGOTIATION_ID", new_negotiation_id_from_stream)
    on("CREATE_CONTRIBUTION_ID", create_contribution_id)
    on("CREATE_INVITATIONS", create_invitations)
    on("CREATE_INFORM", print_information)
    on("CREATE_SECOND_CONTRIBUTION_ID", check_negotiation_wizard)
    on("CREATE_FINISHED_NEGOTIATION",
       lambda: finished_negotiation("CREATE_NEGOTIATION_ID"))

    on("CREATE_COMBINED_PEER_ID",
       create_combined_peer, register_peer_with_owners)


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


def create_endpoint_wizard():
    on("CREATE_EP_NEGOTIATION_ID", new_negotiation_id_from_stream)
    on("CREATE_EP_CONTRIBUTION", create_ep_contribution)
    on("CREATE_EP_SECOND_CONTRIBUTION", check_ep_negotiation_wizard)
    on("CREATE_EP_FINISHED_NEGOTIATION",
        lambda: finished_negotiation("CREATE_EP_NEGOTIATION_ID"))
    on("CREATE_EP_COMBINED_ID", create_combined_endpoint, inform_send_message)


def _create_sphinxmix_wizard():
    create_endpoint_wizard()
    on("PEER_ENDPOINT", create_individual_endpoint)
    on("CREATE_EP_CLOSE_NEGOTIATION_ID", new_negotiation_id_from_stream)

    on("CREATE_EP_CLOSE_CONTRIBUTION", create_ep_close_contribution)
    on("CREATE_EP_CLOSE_SECOND_CONTRIBUTION",
       check_ep_close_negotiation_wizard)
    on("CREATE_EP_CLOSE_FINISHED_NEGOTIATION",
       lambda: finished_negotiation("CREATE_EP_CLOSE_NEGOTIATION_ID"))
    on("CREATE_EP_CLOSE_ID", create_close_endpoint)

    on("CREATE_EP_PROCESS_NEGOTIATION_ID", new_negotiation_id_from_stream)
    on("CREATE_EP_PROCESS_CONTRIBUTION", create_ep_process_contribution)
    on("CREATE_EP_PROCESS_SECOND_CONTRIBUTION",
       check_ep_process_negotiation_wizard)
    on("CREATE_EP_PROCESS_FINISHED_NEGOTIATION",
       lambda: finished_negotiation("CREATE_EP_PROCESS_NEGOTIATION_ID"))
    on("CREATE_EP_PROCESS_ID", create_process_endpoint)

    on("OWN_CLOSE", close_own_endpoint)
    on("OWN_PROCESS", process_own_endpoint)


def create_sphinxmix_wizard():
    while True:
        _create_sphinxmix_wizard()
        create_new_cycle_wizard()


def get_create_restart_response():
    if autodefault:
        return "yes"
    default = "yes"
    response = ui.ask_value(
        "RESTART", "Create a new cycle? (yes/no) (default: %s): " % default)
    if not response:
        return "yes"
    if response != "yes":
        exit()


def create_new_cycle_wizard():
    response = get_create_restart_response()
    ui.inform("Starting a new cycle...")
    cycle_settings = [
        "CREATE_EP_NEGOTIATION_ID", "CREATE_EP_CONTRIBUTION",
        "CREATE_EP_SECOND_CONTRIBUTION", "CREATE_EP_FINISHED_NEGOTIATION",
        "CREATE_EP_COMBINED_ID", "PEER_ENDPOINT",
        "CREATE_EP_CLOSE_NEGOTIATION_ID", "CREATE_EP_CLOSE_CONTRIBUTION",
        "CREATE_EP_CLOSE_SECOND_CONTRIBUTION",
        "CREATE_EP_CLOSE_FINISHED_NEGOTIATION",
        "CREATE_EP_CLOSE_ID", "CREATE_EP_PROCESS_NEGOTIATION_ID",
        "CREATE_EP_PROCESS_CONTRIBUTION",
        "CREATE_EP_PROCESS_SECOND_CONTRIBUTION",
        "CREATE_EP_PROCESS_FINISHED_NEGOTIATION",
        "CREATE_EP_PROCESS_ID",
        "OWN_CLOSE", "OWN_PROCESS",
    ]
    for s in cycle_settings:
        cfg.pop(s)


def role_dispatch(role):
    if role == "create":
        create_mixnet_wizard()
    elif role == "join":
        join_mixnet_wizard()


def create_individual_endpoint():
    crypto_backend = cfg.get("CRYPTO_BACKEND")
    if crypto_backend != BACKENDS["SPHINXMIX"]:
        return
    peer_id = cfg.get("PEER_ID")
    combined_endpoint_id = cfg.get("EP_COMBINED_ID")
    combined_endpoint = client.endpoint_info(combined_endpoint_id)
    endpoint_id = "%s_for_ep_%s" % (peer_id[:7], combined_endpoint_id)
    params = {
        "endpoint_id": endpoint_id,
        "peer_id": peer_id,
        "endpoint_type": "SPHINXMIX",
        "endpoint_params": canonical.to_canonical({}),
        "size_min": combined_endpoint["size_min"],
        "size_max": combined_endpoint["size_max"],
        "description": "processing endpoint",
    }
    endpoint = client.with_self_consensus(client.endpoint_create, params)
    endpoint_id = endpoint["endpoint_id"]
    ui.inform("Registered endpoint with ENDPOINT_ID: %s" % endpoint_id)
    return endpoint_id


def close_own_endpoint():
    endpoint_id = cfg.get("PEER_ENDPOINT")
    params = client.close_on_minimum_prepare(endpoint_id)
    if params == "wrongstatus":
        abort("Wrong status")
    if params == "nomin":
        raise Block("Waiting until minimum inbox size is reached.")
    endpoint = client.with_self_consensus(client.endpoint_action, params)
    endpoint_id = endpoint["endpoint_id"]
    ui.inform("Closed endpoint %s" % endpoint_id)
    return endpoint_id


def process_own_endpoint():
    peer_id = cfg.get("PEER_ID")
    endpoint_id = cfg.get("PEER_ENDPOINT")
    messages, log = client.inbox_process(
        endpoint_id, peer_id, upload=True)
    params = client.record_process_prepare(endpoint_id, log)
    if params == "wrongstatus":
        abort("Wrong status")
    endpoint = client.with_self_consensus(client.endpoint_action, params)
    endpoint_id = endpoint["endpoint_id"]
    ui.inform("Processed endpoint %s" % endpoint_id)
    rs = client.messages_forward(endpoint_id)
    log = []
    for resp_tuple in rs:
        log.append(" message %s to %s '%s'" % resp_tuple)
    ui.inform("Forwarded %s messages:\n%s" % (len(rs), "\n".join(log)))
    return endpoint_id


def create_zeus_wizard():
    return create_endpoint_wizard()


def join_zeus_wizard():
    return join_endpoint_wizard()


def sphinxmix_role_dispatch():
    role = cfg.get("SETUP_ROLE")
    if role == "create":
        return create_sphinxmix_wizard()
    if role == "join":
        return join_sphinxmix_wizard()


def zeus_role_dispatch():
    role = cfg.get("SETUP_ROLE")
    if role == "create":
        return create_zeus_wizard()
    if role == "join":
        return join_zeus_wizard()


BACKEND_WIZARDS = {
    BACKENDS["SPHINXMIX"]: sphinxmix_role_dispatch,
    BACKENDS["ZEUS"]: zeus_role_dispatch,
}


def backend_specific_wizard():
    crypto_backend = cfg.get("CRYPTO_BACKEND")
    wiz = BACKEND_WIZARDS.get(crypto_backend)
    if wiz is not None:
        return wiz()


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
    on("CATALOG_URL",
       set_catalog_url_wizard,
       client.register_catalog_url)
    on("SETUP_ROLE",
       lambda: ui.ask_value("role", "Choose 'create' or 'join' mixnet"),
       role_dispatch)
    backend_specific_wizard()


def show_contrib(contrib):
    return contrib["id"]


def show_consensus(neg):
    return neg["consensus"]

DISPLAY = {
    "CREATE_FINISHED_NEGOTIATION": show_consensus,
    "CREATE_EP_CONTRIBUTION": show_contrib,
    "CREATE_EP_SECOND_CONTRIBUTION": show_contrib,
    "JOIN_FINISHED_NEGOTIATION": show_consensus,
    "JOIN_COORD_INITIAL_CONTRIBUTION": show_contrib,
    "JOIN_COORD_SECOND_CONTRIBUTION": show_contrib,
    "JOIN_EP_COORD_INITIAL_CONTRIBUTION": show_contrib,
    "JOIN_EP_CONTRIBUTION": show_contrib,
    "JOIN_EP_COORD_SECOND_CONTRIBUTION": show_contrib,
    "CREATE_EP_FINISHED_NEGOTIATION": show_consensus,
    "JOIN_EP_FINISHED_NEGOTIATION": show_consensus,
}

on = common.on_meta(DISPLAY)

if __name__ == "__main__":
    main()
