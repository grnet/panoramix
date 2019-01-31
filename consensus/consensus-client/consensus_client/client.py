import requests
from consensus_client import utils


def normalize(s):
    return s.rstrip('/') + '/'


class Client(object):
    def __init__(self, endpoint, crypto_client=None):
        self.endpoint = normalize(endpoint)
        self.negotiations = self.endpoint + 'negotiations/'
        self.consensus = self.endpoint + 'consensus/'
        self.crypto_client = crypto_client

    def register_crypto(self, crypto_client):
        self.crypto_client = crypto_client

    def negotiation_create(self, negotiation_id=None):
        data = None if negotiation_id is None else {'id': negotiation_id}
        response = requests.post(self.negotiations, json=data)
        assert response.status_code == 201
        return response.json()

    def negotiation_retrieve(self, negotiation_id):
        path = '%s%s/' % (self.negotiations, negotiation_id)
        response = requests.get(path)
        assert response.status_code == 200
        return response.json()

    def contribution_create(self, negotiation_id, body, accept):
        text = utils.prepare_text(body, accept)
        signature = self.crypto_client.sign(text)
        data = {
            'text': text,
            'signature': signature,
        }
        path = '%s%s/contributions/' % (self.negotiations, negotiation_id)
        response = requests.post(path, json=data)
        assert response.status_code == 201
        return response.json()

    def contribution_verify(self, contribution):
        text = contribution['text']
        signature = contribution['signature']
        signer_key_id = contribution['signer_key_id']
        verified_key_id = self.crypto_client.verify(signature, text)
        return verified_key_id and signer_key_id == verified_key_id

    def consensus_list(self):
        response = requests.get(self.consensus)
        assert response.status_code == 200
        return response.json()

    def consensus_retrieve(self, consensus_id):
        path = '%s%s/' % (self.consensus, consensus_id)
        response = requests.get(path)
        assert response.status_code == 200
        return response.json()
