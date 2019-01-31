from consensus_client.client import Client
from consensus_client import utils

pem = utils.make_ecdsa_signing_key()
crypto = utils.ECDSAClient(pem)
client = Client('http://127.0.0.1:8000/consensus/', crypto)

body = client.negotiation_create()
neg_id = body['id']
assert body['status'] == 'OPEN'
print "Negotiation:"
print body

neg = client.negotiation_retrieve(neg_id)
assert neg == body

body = client.contribution_create(neg_id, 'TEXTTEXT', True)
print "Contribution:"
print body
assert body['signer_key_id'] == crypto.key_id

print "Verify:"
assert client.contribution_verify(body)

body = client.negotiation_retrieve(neg_id)
print "Negotiation:"
print body
assert body['status'] == 'DONE'
consensus_id = body['consensus_id']

body = client.consensus_retrieve(consensus_id)
print "Consensus:"
print body
