import time
import sys
from consensus_client import client, utils, canonical
from consensus_client.config import Config
from zeus import core, zeus_sk
from pprint import pprint

hash_object = utils.hash_with_canonical


def contribute(negotiation_id, event):
    pass


def get_negotiation_consensus(negotiation_id):
    return 'cons_%s' % negotiation_id


def wait_negotiation(client, negotiation_id, wait=2):
    while True:
        negotiation = client.negotiation_retrieve(negotiation_id)
        consensus_id = negotiation['consensus_id']
        if consensus_id:
            return consensus_id
        time.sleep(wait)


def accept_negotiation(client, negotiation_id, event):
    return client.contribution_create(negotiation_id, event, accept=True)


def record_consensus(client, consensus_id, event_type, state, append=False):
    consensus = client.consensus_retrieve(consensus_id)

    print "Registering type=%s value=%s" % (event_type, consensus_id)
    if not append:
        state.set_value(event_type, consensus_id)
    else:
        values = state.get_value(event_type, default=[])
        values.append(consensus_id)
        state.set_value(event_type, values)

    consensuses = state.get_value('consensus', default={})
    consensuses[consensus_id] = consensus
    state.set_value('consensus', consensuses)


def announce_event(key, event, neg_id, pad):
    negotiations = pad.get_value('negotiations', {})
    negotiations[key] = {
        'event': event,
        'negotiation_id': neg_id,
    }
    pad.set_value('negotiations', negotiations)


def create_authority_event(identifier, doc, state, do_trustee_checks=True):
    trustees = doc['trustees']

    return {
        'type': 'authority',
        'signing_cryptosystem': hash_object(doc['cryptosystem']),
        'trustees': hash_object(trustees),
    }


def verify_create_authority_event(event, identifier, doc, state):
    computed_event = create_authority_event(identifier, doc, state)
    assert event == computed_event


def configuration_event(identifier, doc, state, do_trustee_checks=True):
    authority = state.get_value('authority')
    trustees = doc['trustees']

    return {
        'type': 'configuration',
        'authority_consensus_id': authority,
        'election_cryptosystem': hash_object(doc['cryptosystem']),
        'key_holders': hash_object(trustees),
        'election_name': 'election_name',
        'election_admin': 'election_admin',
    }


def verify_configuration_event(event, identifier, doc, state):
    computed_event = configuration_event(identifier, doc, state)
    assert event == computed_event


def activation_event(identifier, doc, state, do_trustee_checks=True):
    configured_election = state.get_value('configuration')

    return {
        'type': 'activation',
        'configuration_consensus_id': configured_election,
        'poll_name': 'poll_name',
        'poll_type': 'poll_type',
        'opens_at': 'timestamp',
        'closes_at': 'timestamp',
        'candidates': hash_object(doc['candidates']),
        'voters_hash': hash_object(doc['voters']),
        'excluded_voters_hash': hash_object(doc['excluded_voters']),
    }


def verify_activation_event(event, identifier, doc, state):
    computed_event = activation_event(identifier, doc, state)
    assert event == computed_event


def extract_votes_for_mixing(doc):
    votes_for_mixing, counted_list = core.extract_votes_for_mixing(
        doc['cryptosystem'], doc['election_public'],
        doc['cast_vote_index'], doc['cast_votes'],
        doc['votes'], doc['voters'], doc['excluded_voters'])
    return votes_for_mixing


def get_event_of_consensus(consensus):
    text = consensus['text']
    text = canonical.from_unicode_canonical(text)
    return text['body']


def closing_event(identifier, doc, state, do_trustee_checks=True):
    activation_id = state.get_value('activation')
    activation_consensus = state.get_value('consensus')[activation_id]
    activation_event = get_event_of_consensus(activation_consensus)
    assert activation_event['voters_hash'] == hash_object(doc['voters'])
    assert activation_event['excluded_voters_hash'] == hash_object(
        doc['excluded_voters'])

    votes_hash = hash_object(doc['votes'])
    votes_for_mixing = doc['votes_for_mixing']
    votes_for_mixing_hash = hash_object(votes_for_mixing)

    if do_trustee_checks:
        assert votes_for_mixing == extract_votes_for_mixing(doc)

    return {
        'type': 'closing',
        'activation_consensus_id': activation_id,
        'votes_hash': votes_hash,
        'mix_data_hash': votes_for_mixing_hash,
    }


def verify_closing_event(event, identifier, doc, state):
    computed_event = closing_event(identifier, doc, state)
    assert event == computed_event
    # also check event signatures


def notify_voters(doc):
    pass


def mixing_event(mix_round, doc, state, do_trustee_checks=True):
    if mix_round is None:
        mix_round = len(state.get('mixing') or [])

    print "Checking mix_round %s." % mix_round

    mix = doc['mixes'][mix_round]
    mix_data_hash = hash_object(mix)

    if do_trustee_checks:
        zeus_sk.verify_cipher_mix(mix)

    mix_input = mix['original_ciphers']
    mix_input_hash = hash_object(mix_input)

    prev_consensus_id = state.get_value('mixing')[-1] if mix_round \
                        else state.get_value('closing')
    prev_mix_data = doc['mixes'][mix_round - 1] if mix_round \
                    else doc['votes_for_mixing']
    prev_mix_data_hash = hash_object(prev_mix_data)
    prev_consensus = state.get_value('consensus')[prev_consensus_id]
    prev_event = get_event_of_consensus(prev_consensus)
    assert prev_event['mix_data_hash'] == prev_mix_data_hash

    prev_output = prev_mix_data['mixed_ciphers']
    prev_output_hash = hash_object(prev_output)
    assert prev_output_hash == mix_input_hash

    return {
        'type': 'mix',
        'prev_mix_consensus_id': prev_consensus_id,
        'mix_data_hash': mix_data_hash,
    }


def verify_mixing_event(event, mix_round, doc, state):
    computed_event = mixing_event(mix_round, doc, state)
    assert event == computed_event
    # also check event signatures


def decryption_event(identifier, doc, state, do_trustee_checks=True):
    mix_consensus_ids = state.get_value('mixing')
    last_mix_consensus_id = mix_consensus_ids[-1]

    last_mix_consensus = state.get_value('consensus')[last_mix_consensus_id]
    last_mix_event = get_event_of_consensus(last_mix_consensus)

    mix_data_hash = last_mix_event['mix_data_hash']

    last_mix = doc['mixes'][-1]
    assert hash_object(last_mix) == mix_data_hash

    mixed_ciphers = last_mix['mixed_ciphers']
    modulus, generator, order = doc['cryptosystem']
    factors_hashes = []
    for trustee_factors in doc['trustee_factors']:
        # Must check if public keys right
        trustee_public = trustee_factors['trustee_public']
        decryption_factors = trustee_factors['decryption_factors']
        core.verify_decryption_factors(
            modulus, generator, order,
            trustee_public, mixed_ciphers, decryption_factors)
        factors_hashes.append(
            hash_object(trustee_factors))

    return {
        'type': 'decryption',
        'last_mix_consensus_id': last_mix_consensus_id,
        'factors_hashes': factors_hashes,
    }


def verify_decryption_event(event, identifier, doc, state):
    computed_event = decryption_event(identifier, doc, state)
    assert event == computed_event
    # also check event signatures


ADMIN_ACTIONS = {
    'authority': create_authority_event,
    'configuration': configuration_event,
    'activation': activation_event,
    'closing': closing_event,
    'mixing': mixing_event,
    'decryption': decryption_event,
}


def get_event_key(event_type, identifier):
    suffix = '' if identifier is None else '_%s' % identifier
    return '%s%s' % (event_type, suffix)


def admin_do(event_type, identifier, doc, state, pad, client):
    print "ADMIN running %s %s" % (event_type, identifier)
    action = ADMIN_ACTIONS[event_type]
    event = action(identifier, doc, state, do_trustee_checks=False)
    event_key = get_event_key(event_type, identifier)
    neg_id = client.negotiation_create()['id']
    announce_event(event_key, event, neg_id, pad)
    consensus_id = wait_negotiation(client, neg_id)
    append = identifier is not None # for multiple mixes
    record_consensus(client, consensus_id, event_type, state, append)


VERIFIERS = {
    'authority': verify_create_authority_event,
    'configuration': verify_configuration_event,
    'activation': verify_activation_event,
    'closing': verify_closing_event,
    'mixing': verify_mixing_event,
    'decryption': verify_decryption_event,
}


def wait_event_message(event_key, pad, wait=2):
    while True:
        print 'Trustee waiting event: %s' % event_key
        negotiations = pad.get_value('negotiations', {})
        try:
            return negotiations[event_key]
        except KeyError:
            pad.reload()
            time.sleep(wait)


def trustee_do(event_type, identifier, doc, state, pad, client):
    print "TRUSTEE running %s %s" % (event_type, identifier)
    event_key = get_event_key(event_type, identifier)
    negotiation = wait_event_message(event_key, pad)
    negotiation_id = negotiation['negotiation_id']
    event = negotiation['event']
    verifier = VERIFIERS[event_type]
    verifier(event, identifier, doc, state)
    id_str = '' if identifier is None else '%s ' % identifier
    print '\nVerified event %sof type %s:' % (id_str, event_type)
    pprint(event)
    print
    contribution = accept_negotiation(client, negotiation_id, event)
    cons_id = wait_negotiation(client, negotiation_id)
    append = identifier is not None # for multiple mixes
    record_consensus(client, cons_id, event_type, state, append)


def get_client(cfg):
    secret_pem = cfg.get_value('SECRET_KEY')
    crypto = utils.ECDSAClient(secret_pem)
    endpoint = cfg.get_value('ENDPOINT')
    return client.Client(endpoint, crypto)


def run_admin(doc, cfg, pad):
    client = get_client(cfg)
    doc['votes_for_mixing'] = extract_votes_for_mixing(doc)
    admin_do('authority', None, doc, cfg, pad, client)
    admin_do('configuration', None, doc, cfg, pad, client)
    admin_do('activation', None, doc, cfg, pad, client)
    admin_do('closing', None, doc, cfg, pad, client)
    for i in range(len(doc['mixes'])):
        admin_do('mixing', i, doc, cfg, pad, client)
    admin_do('decryption', None, doc, cfg, pad, client)


def run_trustee(doc, cfg, pad):
    client = get_client(cfg)
    doc['votes_for_mixing'] = extract_votes_for_mixing(doc)
    trustee_do('authority', None, doc, cfg, pad, client)
    trustee_do('configuration', None, doc, cfg, pad, client)
    trustee_do('activation', None, doc, cfg, pad, client)
    trustee_do('closing', None, doc, cfg, pad, client)
    for i in range(len(doc['mixes'])):
        trustee_do('mixing', i, doc, cfg, pad, client)
    trustee_do('decryption', None, doc, cfg, pad, client)


def load_document(filename):
    with open(filename) as f:
        return canonical.from_canonical(f)


RUNNERS = {
    'ADMIN': run_admin,
    'TRUSTEE': run_trustee,
}


def main(cfg_file, pad_file, docfile):
    cfg = Config(cfg_file)
    role = cfg.get_value('ROLE')
    run = RUNNERS[role]

    pad = Config(pad_file)
    doc = load_document(docfile)
    run(doc, cfg, pad)


if __name__ == '__main__':
    cfg_file = sys.argv[1]
    pad_file = sys.argv[2]
    docfile = sys.argv[3]
    main(cfg_file, pad_file, docfile)
