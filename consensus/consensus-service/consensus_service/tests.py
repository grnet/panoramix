# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from apimas_django.test import *
from consensus_service import models
from consensus_client import utils

pytestmark = pytest.mark.django_db(transaction=False)


def init_crypto():
    pem = utils.make_ecdsa_signing_key()
    return utils.ECDSAClient(secret=pem)


def test_disallowed(client):
    api = client.copy(prefix='/consensus/')

    r = api.get('negotiations')
    assert r.status_code == 405

    data = {
        'contributions': [
            {
                'text': utils.prepare_text('a text', accept=True),
                'signature': 'a long signature'
            }
        ]
    }

    r = api.post('negotiations', data)
    assert r.status_code == 400
    assert 'not writable' in r.content
    assert 'contributions' in r.content


def test_negotiation_id(client):
    api = client.copy(prefix='/consensus/')
    r = api.post('negotiations', {'id': 'neg_id'})
    assert r.status_code == 201
    body = r.json()
    assert body['status'] == 'OPEN'
    assert body['id'] == 'neg_id'

    r = api.post('negotiations', {'id': 'neg_id'})
    assert r.status_code == 409


def test_auto_close(client):
    api = client.copy(prefix='/consensus/')
    crypto = init_crypto()

    r = api.post('negotiations')
    assert r.status_code == 201
    body = r.json()
    assert body['status'] == 'OPEN'
    assert body['consensus_id'] is None
    neg_id = body['id']

    neg_path = 'negotiations/%s' % neg_id
    text = utils.prepare_text('a text', accept=True)
    data = {
        'text': text,
        'signature': crypto.sign(text),
    }
    r = api.post('%s/contributions' % neg_path, data)
    assert r.status_code == 201
    body = r.json()
    assert body['latest'] is True

    r = api.get(neg_path)
    assert r.status_code == 200
    body = r.json()
    assert body['status'] == 'DONE'

    r = api.post('%s/contributions' % neg_path, data)
    assert r.status_code == 400
    assert 'Negotiation is not open' in r.content


def test_two_users(client):
    api = client.copy(prefix='/consensus/')
    crypto1 = init_crypto()
    crypto2 = init_crypto()

    assert crypto1.key_id != crypto2.key_id

    # new negotiation
    r = api.post('negotiations')
    neg_id = r.json()['id']
    neg_path = 'negotiations/%s' % neg_id

    text = utils.prepare_text('a text', accept=False)
    data = {
        'text': text,
        'signature': crypto1.sign(text),
    }
    r = api.post('%s/contributions' % neg_path, data)
    assert r.status_code == 201
    body = r.json()
    assert body['signer_key_id'] == crypto1.key_id
    signature11 = body['signature']

    text = utils.prepare_text('a text', accept=True)
    data = {
        'text': text,
        'signature': crypto2.sign(text),
    }
    r = api.post('%s/contributions' % neg_path, data)
    assert r.status_code == 201
    body = r.json()
    assert body['signer_key_id'] == crypto2.key_id
    signature21 = body['signature']

    r = api.get(neg_path)
    assert r.status_code == 200
    body = r.json()
    assert body['status'] == 'OPEN'
    assert body['consensus_id'] is None

    # Both users accept
    text = utils.prepare_text('a text', accept=True)
    data = {
        'text': text,
        'signature': crypto1.sign(text),
    }
    r = api.post('%s/contributions' % neg_path, data)
    assert r.status_code == 201
    body = r.json()
    contrib12 = body['id']
    assert body['signer_key_id'] == crypto1.key_id
    signature12 = body['signature']

    r = api.get(neg_path)
    assert r.status_code == 200
    body = r.json()
    assert body['status'] == 'DONE'
    assert len(body['contributions']) == 3
    consensus_id = body['consensus_id']
    assert consensus_id is not None

    r = api.get('consensus/%s' % consensus_id)
    assert r.status_code == 200
    body = r.json()
    assert body['negotiation_id'] == neg_id
    assert body['text'] == utils.prepare_text('a text', accept=True)
    signings = body['signings']
    assert len(signings) == 2
    assert any(sign['signature'] == signature21 for sign in signings)
    assert any(sign['signature'] == signature12 for sign in signings)
