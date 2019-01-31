from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

import requests
from threading import Thread
import os
import sys
import hashlib
from consensus_client.client import Client
from consensus_client import utils
from consensus_client import canonical
import specular

import logging


DATA_FILE_DIR = os.path.abspath(os.path.join('.', 'datafiles'))


DEBUG = os.environ.get('DEBUG', None)
if DEBUG and 'http' in DEBUG:
    try:
        import http.client as http_client
    except ImportError:
        # Python 2
        import httplib as http_client
    http_client.HTTPConnection.debuglevel = 1

    # You must initialize logging, otherwise you'll not see debug output.
    logging.basicConfig(stream=sys.stdout)
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


def hash_file(filepath):
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
        return hasher.hexdigest()


def hash_list(l):
    return utils.hash_string(','.join(l))


def spec_to_position(spec):
    return {
        specular.path_to_key(path): value
        for path, value in spec.iterall(what='=')
    }


def clean_proposal(doc):
    return {
        path: value for path, value in doc.iteritems()
        if value is not specular.ANY
    }


def clean_none_values(doc):
    return {
        path: value for path, value in doc.iteritems()
        if value is not None
    }


def convert_special(doc):
    return {
        path: (value if value is not specular.ANY else None)
        for path, value in doc.iteritems()
    }


def convert_positions(consensus):
    positions = {}
    for path, path_analysis in consensus.iteritems():
        position = []
        for value, (issuer, approvals) in path_analysis.iteritems():
            position.append(
                (value if value is not specular.ANY else None,
                 issuer,
                 list(approvals)))
        positions[path] = position
    return positions


def short(identifier):
    return identifier[:10]


def analyze_negotiation(
        stage_spec, negotiation, ignored, peer_id, proposal=None):
    spec = stage_spec.getpath('content').clone()
    positions = []
    for contrib in negotiation['contributions']:
        if contrib['id'] <= ignored:
            continue
        issuer = short(contrib['signer_key_id'])
        document, meta = get_body_and_meta(contrib)
        positions.append((issuer, document))

    if proposal is not None:
        proposal = clean_proposal(proposal)
        if not proposal:
            proposal = None

    analysis = specular.negotiate(spec, positions, peer_id, proposal)
    analysis['signers'] = list(analysis['signers'])
    return analysis


def produce_node_label(status, alone):
    before, after = status
    LABELS = {  # before_ack, final, after_ack, alone
        (None, False, 'NOACK', True): 'PROPOSE',
        (None, False, 'NOACK', False): 'PROPOSE',

        ('NOACK', True, 'ACK', True): 'AUTOCLOSE',
        ('NOACK', True, 'ACK', False): 'FINISH',

        ('NOACK', False, 'ACK', False): 'CONSENT',
        ('NOACK', False, 'NOACK', False): 'ENHANCE',
        ('NOACK', False, 'NOACK', True): 'ENHANCE',

        ('ACK', False, 'ACK', False): 'WAIT',
        ('ACK', False, 'NOACK', False): 'ENHANCE',
    }

    if after[1] == 'CONFLICT':
        return 'CONFLICT'
    if before == (0, 'ACK'):
        return 'DONE'

    before_ack = before[1] if before is not None else None
    final = after[0] == 0
    after_ack = after[1]
    return LABELS[(before_ack, final, after_ack, alone)]


def produce_labels(analysis):
    our_node_analysis = analysis['our_node_analysis']
    if our_node_analysis is None:
        return 'NO_TRANSITION', {}

    alone = len(analysis['signers']) == 1
    labels = {
        node: produce_node_label(status, alone)
        for node, status in our_node_analysis.iteritems()
    }
    return labels[''], labels


def get_body_and_meta(consensus):
    text = consensus['text']
    unpacked_text = canonical.from_unicode_canonical(text)
    return unpacked_text['body'], unpacked_text['meta']


def get_election_name(records):
    stage_B_consensus = records.get('stage_B')
    if not stage_B_consensus:
        return specular.ANY
    return stage_B_consensus['document']['election_name']


def signing_crypto(handler, spec, cryptosystem, path):
    if cryptosystem != 'ECDSA':
        raise Exception('Unsupported cryptosystem')

    if path is None:
        pem = utils.make_ecdsa_signing_key()
        crypto = utils.ECDSAClient(pem)
    else:
        raise Exception('Key loading unsupported')

    handler.register_crypto(crypto)
    return crypto.key_id


def stage_negotiation(name, stage_instance):
    stage, instance = stage_instance
    suffix = join_stage_instance(stage, instance)
    return '%s_%s' % (name, suffix)


def parse_stage_instance(s):
    stage, instance = s.rsplit('_', 1)
    return stage, int(instance)


def join_stage_instance(stage, instance):
    return '_'.join((stage, str(instance)))


def make_instance(stage, instance):
    return stage, instance


def get_last_consensus(handler):
    if not handler.records:
        return "initial"
    last_stage_instance = sorted(handler.records.keys())[-1]
    last_record = handler.records[last_stage_instance]
    return last_record['id']


class PeerOperation(object):
    FUNCTIONS = None
    spec = None
    options = None

    def __init__(self, consensus_endpoint, dataloc, negotiation_id, username):
        self.client = Client(consensus_endpoint)
        self.negotiation_id = negotiation_id
        self.curr_file_dir = os.path.join(DATA_FILE_DIR, short(negotiation_id))
        self.dataloc = dataloc
        self.files_location = os.path.join(dataloc, short(negotiation_id))
        self.user_input = {}
        self.our_proposals = {}
        self.records = {}
        self.ignored = {}
        self.username = username

    def register_crypto(self, crypto):
        self.client.register_crypto(crypto)

    def unregister_crypto(self):
        self.client.crypto_client = None

    def set_signing_crypto(self, signing_cryptosystem, path=None):
        if signing_cryptosystem != 'ECDSA':
            raise Exception('Unsupported cryptosystem' % signing_cryptosystem)

        if path is None:
            pem = utils.make_ecdsa_signing_key()
            crypto = utils.ECDSAClient(pem)
        else:
            raise Exception('Key loading unsupported')

        self.register_crypto(crypto)
        return self.username, short(crypto.key_id)

    def run_function(self, key, option, args=None):
        fn = self.FUNCTIONS[option['function']]
        if args is None:
            args = option.get('actuals', {})

        action = option['action']
        result = fn(self, **args)
        if action == 'compute':
            return key, result
        elif action == 'compute_element':
            return '/'.join((key, result[0])), result[1]

    def produce_auto_content(self, stage_options):
        content = {}
        for key, option in stage_options.iteritems():
            mode = option.get('mode')
            action = option.get('action')
            if mode == 'auto' and action in ['compute', 'compute_element']:
                res_key, res_value = self.run_function(key, option)
                content[res_key] = res_value
        return content

    def compute_updates(self, instructions, stage_options):
        content = {}
        for key, value in instructions.iteritems():
            prefix, sep, suffix = key.partition('/')
            canonical = prefix
            if suffix:
                canonical += '/*'
            option = stage_options[canonical]
            action = option.get('action')
            if action in ['compute', 'compute_element'] and \
               isinstance(value, dict):
                res_key, res_value = self.run_function(key, option, value)
                content[res_key] = res_value
            else:
                content[key] = value
        return content

    def record_consensus(self, stage_instance, analysis):
        print
        print "RECORD %s (user: %s)" % (stage_instance, self.username)
        document = spec_to_position(analysis['candidate_spec'])
        document = convert_special(document)
        consensus_id = utils.hash_string(canonical.to_canonical(document))
        doc = dict(document)
        doc.pop('')
        completed = None not in doc.values()

        value = {
            'id': short(consensus_id),
            'document': document,
            'signers': list(analysis['signers']),
            'completed': completed,
        }
        self.records[stage_instance] = value
        return value

    def report_consensus(self, stage, instance, consensus):
        stage_instance = make_instance(stage, instance)
        stage_negotiation_id = stage_negotiation(
                self.negotiation_id, stage_instance)

        return {
            'status': 'DONE',
            'stage': stage,
            'instance': instance,
            'stage_negotiation_id': stage_negotiation_id,
            'options': self.options.get(stage, {}),
            'document': convert_special(consensus['document']),
            'consensus_id': consensus['id'],
            'signers': consensus['signers'],
            'completed': consensus['completed'],
        }

    def get_sign_key(self):
        sign_key = self.client.crypto_client.key_id \
                   if self.client.crypto_client else self.username
        return short(sign_key)

    def reset_negotiation(self, stage_instance):
        stage, instance = stage_instance
        negotiation = self.get_negotiation(stage_instance)
        contributions = negotiation['contributions']
        if contributions:
            last_contribution = max(contributions, key=lambda c: c['id'])
            max_id = last_contribution['id']
            print 'Ignoring %s up to %s' % (stage_instance, max_id)
            self.ignored[stage_instance] = max_id

        options = self.options.get(stage, {})
        for key, option in options.iteritems():
            undo = option.get('undo')
            if undo:
                fn = self.FUNCTIONS[undo]
                fn(self)

        self.user_input.pop(stage_instance, None)
        self.our_proposals.pop(stage_instance, None)
        self.records.pop(stage_instance, None)

    def get_instances_from(self, from_stage_instance):
        stage_instances = sorted(self.records.keys())
        from_idx = stage_instances.index(from_stage_instance)
        return stage_instances[from_idx:]

    def reset(self, stage):
        from_stage_instance = make_instance(stage, 1)
        try:
            affected = self.get_instances_from(from_stage_instance)
        except ValueError:
            return []
        for stage_instance in affected:
            self.reset_negotiation(stage_instance)
        return affected

    def create_negotiation(self, neg_id):
        try:
            return self.client.negotiation_create(neg_id)
        except Exception as e:
            return self.client.negotiation_retrieve(neg_id)

    def get_negotiation(self, stage_instance):
        instance_negotiation_id = stage_negotiation(
            self.negotiation_id, stage_instance)
        try:
            return self.client.negotiation_retrieve(instance_negotiation_id)
        except Exception as e:
            return self.create_negotiation(instance_negotiation_id)

    def check_consensus(self, stage_instance, analysis):
        node_statuses = analysis['node_statuses']
        if node_statuses and node_statuses[''] == (0, 'ACK'):
            print 'Consensus Reached'
            return self.record_consensus(stage_instance, analysis)
        return None

    def apply_previous_consensus(self, stage, instance, candidate_spec):
        if instance == 1:
            return candidate_spec

        prev_stage_instance = make_instance(stage, instance - 1)
        previous_doc = dict(self.records[prev_stage_instance]['document'])
        previous_doc.pop('last_consensus')
        candidate_spec = candidate_spec.clone()
        candidate_spec.config(clean_none_values(previous_doc))
        return candidate_spec

    def new_proposal(self, stage, instance, apriori_analysis):
        stage_instance = make_instance(stage, instance)
        candidate_spec = apriori_analysis['candidate_spec']
        candidate_spec = self.apply_previous_consensus(
            stage, instance, candidate_spec)
        proposal = spec_to_position(candidate_spec)
        stage_options = self.options.get(stage, {})
        auto_content = self.produce_auto_content(stage_options)
        proposal.update(auto_content)
        user_input = self.user_input.get(stage_instance, {})
        proposal.update(user_input)
        self.our_proposals[stage_instance] = proposal
        return proposal

    def validate_proposal(self, stage_spec, proposal):
        spec = stage_spec.getpath('content').clone()
        spec.config(proposal)
        artifacts = {'records': self.records}
        artifacts = spec.construct(
            constructions={'validations': self.validators},
            artifacts=artifacts)
        validations = artifacts.get('validations', {})
        return {specular.path_to_key(path): value
                for path, value in validations.iteritems()}

    def query_stage(self, stage, instance):
        stage_instance = make_instance(stage, instance)
        consensus = self.records.get(stage_instance)
        if consensus:
            return self.report_consensus(stage, instance, consensus)

        negotiation = self.get_negotiation(stage_instance)
        stage_spec = self.spec.getpath(('stages', stage))
        sign_key = self.get_sign_key()

        ignored = self.ignored.get(stage_instance, 0)
        apriori = analyze_negotiation(
            stage_spec, negotiation, ignored, sign_key)
        consensus = self.check_consensus(stage_instance, apriori)
        if consensus:
            return self.report_consensus(stage, instance, consensus)

        proposal = self.new_proposal(stage, instance, apriori)
        aposteriori = analyze_negotiation(
            stage_spec, negotiation, ignored, sign_key, proposal)

        validations = self.validate_proposal(stage_spec, proposal)

        label, labels = produce_labels(aposteriori)

        stage_negotiation_id = stage_negotiation(
                self.negotiation_id, stage_instance)

        return {
            'stage': stage,
            'instance': instance,
            'stage_negotiation_id': stage_negotiation_id,
            'status': 'OPEN',
            'document': convert_special(proposal),
            'apriori_positions': convert_positions(apriori['consensus']),
            'positions': convert_positions(aposteriori['consensus']),
            'our_path_analysis': aposteriori['our_path_analysis'],
            'our_node_analysis': aposteriori['our_node_analysis'],
            'signers': list(aposteriori['signers']),
            'options': self.options.get(stage, {}),
            'peer_id': sign_key,
            'label': label,
            'labels': labels,
            'validations': validations,
        }

    def update_document(self, stage, instance, instructions):
        stage_instance = make_instance(stage, instance)
        stage_options = self.options.get(stage, {})
        result = self.compute_updates(instructions, stage_options)
        user_input = self.user_input.get(stage_instance, {})
        user_input.update(result)
        self.user_input[stage_instance] = user_input
        return self.query_stage(stage, instance)

    def contribute(self, stage, instance):
        stage_instance = make_instance(stage, instance)
        stage_negotiation_id = stage_negotiation(
            self.negotiation_id, stage_instance)
        proposal = self.our_proposals[stage_instance]
        proposal = clean_proposal(proposal)
        r = self.client.contribution_create(
            stage_negotiation_id, proposal, False)
        return self.query_stage(stage, instance)

    def get_overview(self):
        stages_spec = self.spec.getpath(('stages',))

        meta = {}
        for stage in sorted(stages_spec.nodes):
            if stage in (b'?', b'.', b'#', b'$'):
                continue
            meta[stage] = {
                'title': stages_spec[(stage, 'title')],
                'description': stages_spec[(stage, 'description')],
                'options': self.options.get(stage, {}),
            }

        reports = []
        for stage_instance in sorted(self.records.keys()):
            consensus = self.records[stage_instance]
            stage, instance = stage_instance
            reports.append(self.report_consensus(stage, instance, consensus))

        stages = sorted(meta.keys())
        num_stages = len(stages)
        if not reports:
            next_stage = stages[0]
            next_instance = 1
        else:
            last_report = reports[-1]
            last_stage = last_report['stage']
            if not last_report['completed']:
                next_stage = last_stage
                next_instance = last_report['instance'] + 1
            else:
                last_stage_idx = stages.index(last_stage)
                next_stage_idx = last_stage_idx + 1
                if next_stage_idx != num_stages:
                    next_stage = stages[next_stage_idx]
                    next_instance = 1
                else:
                    next_stage = None
                    next_instance = None

        overview = {
            'global_negotiation_id': self.negotiation_id,
            'meta': meta,
            'reports': reports,
            'next_stage': next_stage,
            'next_instance': next_instance,
        }
        return overview


def flask_service(handlers):
    app = Flask(__name__)
    CORS(app)

    ui_default_dir = os.path.abspath(os.path.join('.', 'ui'))
    ui_dir = os.environ.get('UI_DIR', ui_default_dir)
    static_file_dir = os.path.join(ui_dir, 'dist')

    @app.route('/ui/')
    def index():
        return send_from_directory(static_file_dir, 'index.html')

    @app.route('/ui/<path:path>', methods=['GET'])
    def serve_file_in_dir(path):
        if not os.path.isfile(os.path.join(static_file_dir, path)):
            path = 'index.html'
        return send_from_directory(static_file_dir, path)

    @app.route('/reset/<stage>/')
    def reset(stage):
        for _, handler in handlers.items():
            affected = handler.reset(stage)

        return jsonify(affected)

    @app.route('/<user>/stages/<stage_instance>/')
    def query_stage(user, stage_instance):
        stage, instance = parse_stage_instance(stage_instance)
        handler = handlers[user]
        response = handler.query_stage(stage, instance)
        return jsonify(response)

    @app.route('/<user>/stages/<stage_instance>/update/', methods=['POST'])
    def update_document(user, stage_instance):
        stage, instance = parse_stage_instance(stage_instance)
        handler = handlers[user]
        body = request.json
        instructions = body['instructions']
        response = handler.update_document(stage, instance, instructions)
        return jsonify(response)

    @app.route('/<user>/stages/<stage_instance>/contribute/', methods=['POST'])
    def contribute(user, stage_instance):
        stage, instance = parse_stage_instance(stage_instance)
        handler = handlers[user]
        response = handler.contribute(stage, instance)
        return jsonify(response)

    @app.route('/<user>/stages/')
    def get_overview(user):
        handler = handlers[user]
        response = handler.get_overview()
        return jsonify(response)

    @app.route('/data/<path:filename>')
    def download_file(filename):
        return send_from_directory(DATA_FILE_DIR,
                                   filename, as_attachment=True)
    return app


def launch(handlers, host, port, serve=False):
    kwargs={
        'host': host,
        'port': port,
        'use_reloader': serve and bool(DEBUG)
    }
    app = flask_service(handlers)
    if serve:
        return app.run(**kwargs)
    else:
        thd = Thread(target=app.run)
        thd.daemon = True
        thd.start()
        return thd


class SimpleHttpClient(object):
    def __init__(self, username, endpoint):
        self.bare_endpoint = endpoint.rstrip('/')
        self.endpoint = self.bare_endpoint + '/' + username

    def query_stage(self, stage, instance):
        stage_instance = join_stage_instance(stage, instance)
        ep = '%s/stages/%s/' % (self.endpoint, stage_instance)
        response = requests.get(ep)
        return response.json()

    def update_document(self, stage, instance, instructions):
        stage_instance = join_stage_instance(stage, instance)
        ep = '%s/stages/%s/update/' % (self.endpoint, stage_instance)
        data = {'instructions': instructions}
        response = requests.post(ep, json=data)
        return response.json()

    def contribute(self, stage, instance):
        stage_instance = join_stage_instance(stage, instance)
        ep = '%s/stages/%s/contribute/' % (self.endpoint, stage_instance)
        response = requests.post(ep, json={})
        return response.json()

    def get_overview(self):
        ep = '%s/stages/' % self.endpoint
        response = requests.get(ep)
        return response.json()

    def reset(self, stage):
        ep = '%s/reset/%s/' % (self.bare_endpoint, stage)
        response = requests.get(ep)
        return response.json()
