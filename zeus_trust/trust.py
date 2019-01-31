import time
import sys
import os
import base64
import specular
import json

from trustpanel.base import PeerOperation, short, hash_file, \
    get_last_consensus, DATA_FILE_DIR, SimpleHttpClient, launch
from zeus_trust.spec import domain
from zeus_trust import options


@specular.make_constructor
def validate_sign_key(spec, loc, value, top_spec):
    crypto_loc = loc[:-2] + ('signing_cryptosystem',)
    signing_cryptosystem = top_spec[crypto_loc]
    # check value wrt signing_cryptosystem
    return True


def get_last_of_stage(records, stage):
    instances = sorted(records.keys())
    instances = [(s, i) for (s, i) in instances if s == stage]
    if not instances:
        return None
    return records[instances[-1]]


def get_sub_keys(doc, node):
    return {key.partition('/')[2] for key in doc.keys()
            if key.startswith(node + '/')}


@specular.make_constructor
def validate_shares(spec, global_artifacts):
    record = get_last_of_stage(global_artifacts['records'], 'stage_A')
    doc = record['document']
    trustees = get_sub_keys(doc, 'trustees')
    registered = set(dict(spec.iter_level_values()).keys())
    return trustees == registered


@specular.make_constructor
def validate_mixes(spec, global_artifacts):
    record = get_last_of_stage(global_artifacts['records'], 'stage_C')
    doc = record['document']
    mixers = get_sub_keys(doc, 'mixers')
    registered = set(dict(spec.iter_level_values()).keys())
    return mixers == registered


@specular.make_constructor
def validate_decryptions(spec, global_artifacts):
    record = get_last_of_stage(global_artifacts['records'], 'stage_B')
    doc = record['document']
    shares = get_sub_keys(doc, 'public_shares')
    registered = set(dict(spec.iter_level_values()).keys())
    return shares == registered


VALIDATORS = {
    '.sign_key': validate_sign_key,
    '.shares': validate_shares,
    '.mixes': validate_mixes,
    '.decryptions': validate_decryptions,
}


def make_election_key():
    s = os.urandom(16)
    return base64.urlsafe_b64encode(s).rstrip('=')


def generate_random_key():
    s = os.urandom(8)
    return base64.urlsafe_b64encode(s).rstrip('=')


class ZeusPeerOperation(PeerOperation):
    def __init__(self, consensus_endpoint, dataloc, negotiation_id, username,
                 options):
        self.election_key = None
        PeerOperation.__init__(self,
                               consensus_endpoint, dataloc,
                               negotiation_id, username)
        self.spec = domain.compile_spec({'.negotiation.zeus': {}})
        self.options = options
        self.validators = VALIDATORS

    def report_file(self, filename):
        filepath = os.path.join(self.curr_file_dir, filename)
        link = os.path.join(self.files_location, filename)
        report = {'link': link,
                  'hash': short(hash_file(filepath))}
        return json.dumps(report)

    def hash_candidates(self):
        return self.report_file('candidates')

    def hash_voters(self):
        return self.report_file('voters')

    def hash_votes(self):
        return self.report_file('votes')

    def mix_and_verify(self):
        mix = self.report_file('mixed_data')
        # Verify mixes here
        return self.username, mix

    def make_decryption_factors(self):
        decryption = self.report_file('decryption_factors')
        # Verify decryption here
        return self.username, decryption

    def set_election_public(self, election_cryptosystem, path=None):
        if election_cryptosystem != 'ElGamalIntegers':
            raise Exception('Unsupported cryptosystem' % election_cryptosystem)
        self.election_key = make_election_key()
        return self.username, self.election_key

    def unset_election_public(self):
        self.election_key = None

    def get_signing_key(self):
        return self.username, short(self.client.crypto_client.key_id)

    def new_extension(self):
        record = get_last_of_stage(self.records, 'stage_E')
        if not record:
            ident = 1
        else:
            doc = record['document']
            extensions = get_sub_keys(doc, 'extensions')
            ident = len(extensions) + 1

        return "Ext_%s" % ident, None

    FUNCTIONS = {
        'hash_candidates': hash_candidates,
        'hash_voters': hash_voters,
        'hash_votes': hash_votes,
        'mix_and_verify': mix_and_verify,
        'make_decryption_factors': make_decryption_factors,
        'set_election_public': set_election_public,
        'set_signing_crypto': PeerOperation.set_signing_crypto,
        'get_signing_key': get_signing_key,
        'get_last_consensus': get_last_consensus,
        'unregister_crypto': PeerOperation.unregister_crypto,
        'unset_election_public': unset_election_public,
        'new_extension': new_extension,
    }


def prepare_data(neg):
    curr_file_dir = os.path.join(DATA_FILE_DIR, short(neg))
    os.makedirs(curr_file_dir)

    ELECTION_DOCUMENTS = {
        'default': {
            'candidates': "['a', 'b', 'c']",
            'voters': "['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l']",
            'votes': "['va', 'vs', 'vd', 'vf', 'vg', 'vh']",
            'mixed_data': "['va', 'vd', 'vf', 'vg', 'vh', 'vs']",
            'decryption_factors': "['a', 'a', 'b', 'c', 'c', 'c']",
        },
    }
    for key, value in ELECTION_DOCUMENTS['default'].iteritems():
        with open(os.path.join(curr_file_dir, key), 'w') as f:
            f.write(value)


def run(no_of_trustees, port=9000):
    neg = generate_random_key()
    prepare_data(neg)

    host = '0.0.0.0'
    schema = 'http://'
    hostport = '%s%s:%s' % (schema, host, port)
    dataloc = os.path.join(hostport, 'data')

    handlers = {}
    for i in range(no_of_trustees):
        username = 'trustee%s' % (i+1)
        handler = ZeusPeerOperation(
            'http://127.0.0.1:8000/consensus', dataloc, neg, username,
            options.TRUSTEE_OPTIONS)
        handlers[username] = handler

    print "Launching Flask for %s trustees..." % no_of_trustees
    return launch(handlers, host, port, True)


def test(use_flask, serve=False):
    from pprint import pprint
    neg = generate_random_key()
    prepare_data(neg)

    if use_flask:
        host = '127.0.0.1'
        port = 5000
        schema = 'http://'
        hostport = '%s%s:%s' % (schema, host, port)
        dataloc = os.path.join(hostport, 'data')
    else:
        dataloc = DATA_FILE_DIR

    print "negotiation id:", neg
    trustee1 = ZeusPeerOperation(
        'http://127.0.0.1:8000/consensus', dataloc, neg, 'trustee1',
        options.TRUSTEE_OPTIONS)

    trustee2 = ZeusPeerOperation(
        'http://127.0.0.1:8000/consensus', dataloc, neg, 'trustee2',
        options.TRUSTEE_OPTIONS)
    mixer = ZeusPeerOperation(
        'http://127.0.0.1:8000/consensus', dataloc, neg, 'mixer1',
        options.MIXER_OPTIONS)

    if use_flask:
        handlers = {
            trustee1.username: trustee1,
            trustee2.username: trustee2,
            mixer.username: mixer,
        }
        flask_thread = launch(handlers, host, port, serve)
        print "Launched flask thread:", flask_thread.ident
        time.sleep(1)

        trustee1_client = SimpleHttpClient(trustee1.username, hostport)
        trustee2_client = SimpleHttpClient(trustee2.username, hostport)
        mixer_client = SimpleHttpClient(mixer.username, hostport)
    else:
        trustee1_client = trustee1
        trustee2_client = trustee2
        mixer_client = mixer

    response = trustee1_client.get_overview()
    assert response['next_stage'] == 'stage_A'
    assert response['next_instance'] == 1

    # STAGE A
    response = trustee1_client.query_stage('stage_A', 1)
    # response: no our_node_analysis (no transition proposed yet)
    assert response['label'] == 'PROPOSE'

    mixer_response = mixer_client.query_stage('stage_A', 1)
    assert not mixer_response['options']

    response = trustee1_client.update_document(
        'stage_A', 1,
        {'signing_cryptosystem': 'ECDSA',
         'trustees': {'signing_cryptosystem': 'ECDSA'}
        })
    # response: None -> (1, 'NOACK') === PROPOSE
    assert response['label'] == 'PROPOSE'
    assert 'trustees/trustee1' in response['document']

    trustee1_client.contribute('stage_A', 1)
    response = trustee1_client.query_stage('stage_A', 1)
    # response: (1, 'NOACK') -> (0, 'ACK') \ AUTOCLOSE
    #           len signers = 1            / (unwanted)
    assert response['label'] == 'AUTOCLOSE'

    response = trustee2_client.query_stage('stage_A', 1)
    # response: (1, 'NOACK') -> (1, 'ACK') === CONSENT
    assert response['label'] == 'CONSENT'

    response = trustee2_client.update_document(
        'stage_A', 1,
        {'signing_cryptosystem': 'RSA',
        })
    # response: (1, 'NOACK') -> (2, 'CONFLICT') === CONFLICT
    assert response['label'] == 'CONFLICT'

    response = trustee2_client.update_document(
        'stage_A', 1,
        {'trustees': {'signing_cryptosystem': 'ECDSA'},
         'signing_cryptosystem': 'ECDSA',
        })
    # response: (1, 'NOACK') -> (2, 'NOACK') === ENHANCE
    assert response['label'] == 'ENHANCE'

    trustee2_client.contribute('stage_A', 1)
    response = trustee1_client.query_stage('stage_A', 1)
    # response: (2, 'NOACK') -> (1, 'ACK') === CONSENT
    assert response['label'] == 'CONSENT'

    trustee1_client.contribute('stage_A', 1)
    response = trustee1_client.query_stage('stage_A', 1)
    # response: (1, 'ACK') -> (1, 'ACK') === WAIT
    assert response['label'] == 'WAIT'

    response = trustee2_client.query_stage('stage_A', 1)
    # response: (1, 'NOACK') -> (0, 'ACK') \ FINISH
    #           len signers > 1            /
    assert response['label'] == 'FINISH'
    response = trustee2_client.contribute('stage_A', 1)
    # response: status == 'DONE'
    assert response['status'] == 'DONE'

    response = trustee1_client.query_stage('stage_A', 1)
    # response: status == 'DONE'
    assert response['status'] == 'DONE'

    assert 'consensus_id' in response
    pprint(response)
    mixer_client.query_stage('stage_A', 1)

    response = trustee1_client.get_overview()
    report = response['reports'][-1]
    assert report['stage'] == 'stage_A'
    assert report['instance'] == 1
    assert report['completed'] == False
    assert response['next_stage'] == 'stage_A'
    assert response['next_instance'] == 2

    response = trustee1_client.query_stage('stage_A', 2)

    response = trustee1_client.update_document(
        'stage_A', 2,
        {'trustees': 'lock'})
    response = trustee1_client.contribute('stage_A', 2)
    assert response['label'] == 'AUTOCLOSE'

    response = trustee2_client.query_stage('stage_A', 2)
    assert response['label'] == 'CONSENT'
    response = trustee2_client.contribute('stage_A', 2)
    assert response['label'] == 'WAIT'
    response = trustee1_client.contribute('stage_A', 2)
    assert response['status'] == 'DONE'
    pprint(response)
    response = trustee2_client.query_stage('stage_A', 2)
    assert response['status'] == 'DONE'

    response = trustee1_client.get_overview()
    report = response['reports'][-1]
    assert report['stage'] == 'stage_A'
    assert report['instance'] == 2
    assert report['completed'] == True
    assert response['next_stage'] == 'stage_B'
    assert response['next_instance'] == 1

    # STAGE B
    response = trustee1_client.query_stage('stage_B', 1)
    assert response['label'] == 'PROPOSE'
    assert 'last_consensus' in response['document']

    trustee1_client.update_document(
        'stage_B', 1,
        {
            'election_cryptosystem': 'ElGamalIntegers',
            'election_name': 'ELECTION1',
            'no_of_mixers': 2,
            'public_shares': {'election_cryptosystem': 'ElGamalIntegers'},
        }
    )
    response = trustee1_client.contribute('stage_B', 1)
    assert response['label'] == 'AUTOCLOSE'

    response = trustee2_client.query_stage('stage_B', 1)
    assert response['label'] == 'CONSENT'

    response = trustee2_client.update_document(
        'stage_B', 1,
        {
            'public_shares': {'election_cryptosystem': 'ElGamalIntegers'},
        })
    assert response['label'] == 'ENHANCE'
    response = trustee2_client.contribute('stage_B', 1)
    assert response['label'] == 'CONSENT'
    response = trustee2_client.contribute('stage_B', 1)
    assert response['label'] == 'WAIT'

    response = trustee2_client.update_document(
        'stage_B', 1, {'mixnet': 'Verificatum'})
    assert response['label'] == 'ENHANCE'
    response = trustee2_client.contribute('stage_B', 1)
    assert response['label'] == 'CONSENT'
    response = trustee2_client.contribute('stage_B', 1)
    assert response['label'] == 'WAIT'

    response = trustee1_client.query_stage('stage_B', 1)
    assert response['label'] == 'FINISH'
    response = trustee1_client.contribute('stage_B', 1)
    assert response['status'] == 'DONE'
    response = trustee2_client.contribute('stage_B', 1)
    assert response['status'] == 'DONE'
    pprint(response)

    response = trustee1_client.get_overview()
    assert response['next_stage'] == 'stage_B'
    assert response['next_instance'] == 2

    response = trustee1_client.query_stage('stage_B', 2)
    response = trustee1_client.update_document(
        'stage_B', 2, {'public_shares': 'lock'})
    response = trustee1_client.contribute('stage_B', 2)

    response = trustee2_client.query_stage('stage_B', 2)
    response = trustee2_client.contribute('stage_B', 2)

    response = trustee1_client.contribute('stage_B', 2)
    assert response['status'] == 'DONE'
    response = trustee2_client.query_stage('stage_B', 2)
    pprint(response)

    # STAGE C
    response = trustee1_client.query_stage('stage_C', 1)
    assert response['label'] == 'PROPOSE'
    response = trustee1_client.update_document(
        'stage_C', 1,
        {'mixers': {}})
    assert response['label'] == 'PROPOSE'
    response = trustee1_client.contribute('stage_C', 1)
    assert response['label'] == 'AUTOCLOSE'

    response = trustee2_client.query_stage('stage_C', 1)
    assert response['label'] == 'CONSENT'
    response = trustee2_client.update_document(
        'stage_C', 1,
        {'mixers': {}})
    assert response['label'] == 'ENHANCE'
    response = trustee2_client.contribute('stage_C', 1)
    assert response['label'] == 'CONSENT'

    response = trustee1_client.query_stage('stage_C', 1)
    assert response['label'] == 'CONSENT'
    response = trustee1_client.contribute('stage_C', 1)
    assert response['label'] == 'WAIT'

    response = trustee2_client.query_stage('stage_C', 1)
    assert response['label'] == 'FINISH'
    response = trustee2_client.contribute('stage_C', 1)
    assert response['status'] == 'DONE'

    response = trustee1_client.query_stage('stage_C', 1)
    assert response['status'] == 'DONE'
    pprint(response)

    affected = trustee1_client.reset('stage_B')
    print 'Affected:', affected
    assert trustee1_client.election_key is None
    assert trustee1_client.client.crypto_client is not None

    response = trustee1_client.query_stage('stage_C', 1)
    assert response['label'] == 'PROPOSE'

    response = trustee1_client.query_stage('stage_B', 1)
    assert response['label'] == 'PROPOSE'

    response = trustee1_client.query_stage('stage_A', 1)
    assert response['status'] == 'DONE'

    response = trustee1_client.query_stage('stage_D', 1)
    assert response['label'] == 'PROPOSE'

    affected = trustee1_client.reset('stage_A')
    print 'Affected:', affected
    assert trustee1_client.election_key is None
    assert trustee1_client.client.crypto_client is None

    # STAGE D
    tresponse = trustee1_client.query_stage('stage_D')
    mresponse = mixer_client.query_stage('stage_D')
    assert not mresponse['options']

    content = trustee1_client.update_document(
        'stage_D',
        {
            'opens_at': '2018-12-12T07:00:00',
            'closes_at': '2018-12-12T19:00:00',
        }
    )
    trustee1_client.contribute('stage_D')
    response = trustee1_client.query_stage('stage_D')
    pprint(response['consensus'])
    mixer_client.query_stage('stage_D')

    # STAGE E
    tresponse = trustee1_client.query_stage('stage_E')
    mresponse = mixer_client.query_stage('stage_E')
    assert not mresponse['options']
    assert 'votes' in tresponse['document']

    trustee1_client.contribute('stage_E')
    response = trustee1_client.query_stage('stage_E')
    pprint(response['consensus'])
    mixer_client.query_stage('stage_E')

    # STAGE F
    tresponse = trustee1_client.query_stage('stage_F')
    mresponse = mixer_client.query_stage('stage_F')
    # Bootstrap the negotiation
    trustee1_client.contribute('stage_F')

    assert 'mixed_data' in mresponse['document']
    mixer_client.contribute('stage_F')

    assert 'mixed_data' in tresponse['document']
    trustee1_client.contribute('stage_F')
    response = trustee1_client.query_stage('stage_F')
    pprint(response['consensus'])
    mixer_client.query_stage('stage_F')

    # STAGE G
    tresponse = trustee1_client.query_stage('stage_G')
    mresponse = mixer_client.query_stage('stage_G')
    assert not mresponse['options']

    assert 'decryption_factors' in tresponse['document']
    trustee1_client.contribute('stage_G')
    response = trustee1_client.query_stage('stage_G')
    pprint(response['consensus'])
    mixer_client.query_stage('stage_G')
    return trustee1, mixer


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else None
    if command == 'test':
        test(bool(os.environ.get('USE_FLASK')), bool(os.environ.get('SERVE')))
    elif command == 'run':
        no_of_trustees = int(os.environ.get('NRTRUSTEES', 2))
        if len(sys.argv) > 2:
            no_of_trustees = int(sys.argv[2])
        port = int(os.environ.get('PORT', 9000))
        if len(sys.argv) > 3:
            port = int(sys.argv[3])
        run(no_of_trustees, port)
