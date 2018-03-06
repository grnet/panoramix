# -*- coding: utf-8 -*-

from apimas_django.test import *
from panoramix_service import models

pytestmark = pytest.mark.django_db(transaction=False)


def test_workflow(client):
    api = client.copy(prefix='/panoramix/')

    data = {
        'peer_id': 'peer1_id',
        'name': 'name1',
        'key_type': 1,
        'key_data': 'key_data',
        'crypto_backend': 'sphinxmix',
        'crypto_params': '',
    }
    r = api.post('peers', data)
    assert r.status_code == 201

    end1_id = 'end1_id'
    data = {
        'endpoint_id': end1_id,
        'peer_id': 'peer1_id',
        'public': True,
        'description': 'ddd',
        'endpoint_type': 'type',
        'endpoint_params': 'params',
        'public': 1,
    }
    r = api.post('endpoints', data)
    assert r.status_code == 201
    assert r.json()['current_cycle'] == 0

    end1_path = 'endpoints/%s' % end1_id
    r = api.post('%s/cycles/' % end1_path, {})
    assert r.status_code == 201

    r = api.get(end1_path)
    assert r.status_code == 200
    assert r.json()['current_cycle'] == 1

    r = api.get('%s/cycles/1' % end1_path)
    assert r.status_code == 200

    end2_id = 'end2_id'
    data = {
        'endpoint_id': end2_id,
        'peer_id': 'peer1_id',
        'public': True,
        'description': 'ddd',
        'endpoint_type': 'type',
        'endpoint_params': 'params',
        'public': 1,
    }
    r = api.post('endpoints', data)
    assert r.status_code == 201

    end2_path = 'endpoints/%s' % end2_id
    r = api.post('%s/cycles/' % end2_path, {'state': 'new'})
    assert r.status_code == 201
    assert r.json()['cycle'] == 1

    r = api.get('%s/cycles/1/' % end2_path)
    assert r.status_code == 200

    data = {
        'sender': 'sender1',
        'recipient': 'recipient1',
        'text': 'text1',
    }

    r = api.post('%s/messages/' % end1_path, data)
    assert r.status_code == 201
    body = r.json()
    m1_id = body['id']
    assert body['state'] == 'INBOX'

    data = {
        'sender': 'sender2',
        'recipient': 'recipient2',
        'text': 'text2',
    }

    r = api.post('%s/messages/' % end1_path, data)
    assert r.status_code == 201
    body = r.json()
    m2_id = body['id']

    data = {
        'sender': 'sender3',
        'recipient': 'recipient3',
        'text': 'text3',
    }

    r = api.post('%s/messages/' % end1_path, data)
    assert r.status_code == 201
    body = r.json()
    m3_id = body['id']

    r = api.get('%s/messages/' % end1_path, {'flt__cycle': 1})
    assert r.status_code == 200
    assert len(r.json()) == 3

    r = api.get('%s/cycles/1/' % end1_path)
    assert r.status_code == 200
    assert r.json()['message_count'] == 3

    r = api.get('%s/messages/' % end1_path, {'flt__cycle': 2})
    assert r.status_code == 200
    assert len(r.json()) == 0

    r = api.post('%s/cycles/' % end1_path, {})
    assert r.status_code == 201
    assert r.json()['cycle'] == 2

    data = {
        'sender': 'sender3',
        'recipient': 'recipient3',
        'text': 'text3',
    }

    r = api.post('%s/messages/' % end1_path, data)
    assert r.status_code == 201
    assert r.json()['cycle'] == 2

    data = {
        'messages': [
            {'id': m1_id, 'state': 'accepted'},
            {'id': m2_id, 'state': 'accepted'},
        ],
    }
    r = api.post('%s/cycles/1/set-message-state/' % end1_path, data)
    assert r.status_code == 200

    r = api.get('%s/messages/' % end1_path,
                {'flt__cycle': 1, 'flt__state': 'accepted'})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2

    messages = []
    for msg in body:
        messages.append(
            {'sender': msg['sender'],
             'recipient': msg['recipient'],
             'text': msg['text'],
             'state': 'processed'})

    data = {'messages': messages}
    r = api.post('%s/cycles/1/bulk-upload/' % end2_path, data)
    assert r.status_code == 201

    r = api.get('%s/messages/' % end2_path, {'flt__cycle': 1})
    assert r.status_code == 200

    r = api.post('%s/cycles/2/purge/' % end1_path, {})
    assert r.status_code == 400

    r = api.get('%s/messages/' % end1_path, {'flt__cycle': 2})
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = api.post('%s/cycles/1/purge/' % end1_path, {})
    assert r.status_code == 200

    r = api.get('%s/messages/' % end1_path, {'flt__cycle': 1})
    assert r.status_code == 200
    assert len(r.json()) == 0
