Setting up a mixnet
===================

Peer creation
-------------

We first need to create a joint peer. This fixes the crypto settings across
the mixnet, but does not involve any application settings. A simple
negotiation is enough.

Endpoint creation
-----------------

In the zeus case we start off a negotiation with the following definition::

  [
    {
        "peer_id": joint_peer,
        "endpoint_id": "ballotbox_election_foo",
        "endpoint_type": "ZEUS_BALLOT_BOX",
        "links": [{"from_endpoint_id": "combine_foo",
                   "from_box": "OUTBOX",
                   "to_box": "PROCESSBOX"}]
    },
    {
        "peer_id": peer1,
        "endpoint_id": "mix_peer1_foo",
        "endpoint_type": "ZEUS_SK_MIX",
        "links": [{"from_endpoint_id": "ballotbox_election_foo",
                   "from_box": "ACCEPTED",
                   "to_box": "INBOX"}]
    },
    {
        "peer_id": peer2,
        "endpoint_id": "mix_peer2_foo",
        "endpoint_type": "ZEUS_SK_MIX",
        "links": [{"from_endpoint_id": "mix_peer1_foo",
                   "from_box": "OUTBOX",
                   "to_box": "INBOX"}]
    },
    {
        "peer_id": peer1,
        "endpoint_id": "decr_peer1_foo",
        "endpoint_type": "ZEUS_SK_PARTIAL_DECRYPT",
        "links": [{"from_endpoint_id": "mix_peer2_foo",
                   "from_box": "OUTBOX",
                   "to_box": "INBOX"}]
    },
    {
        "peer_id": peer2,
        "endpoint_id": "decr_peer2_foo",
        "endpoint_type": "ZEUS_SK_PARTIAL_DECRYPT",
        "links": [{"from_endpoint_id": "mix_peer2_foo",
                   "from_box": "OUTBOX",
                   "to_box": "INBOX"}]
    },
    {
        "peer_id": joint_peer,
        "endpoint_id": "combine_foo",
        "endpoint_type": "ZEUS_SK_COMBINE",
        "links": [{"from_endpoint_id": "decr_peer1_foo",
                   "from_box": "OUTBOX",
                   "to_box": "INBOX"},
                  {"from_endpoint_id": "decr_peer2_foo",
                   "from_box": "OUTBOX",
                   "to_box": "INBOX"}]
    }
  ]

This describes a graph of endpoints: each list element is a prescription to
create an endpoint. The attribute "links" describes where each endpoint
takes its input from (be it the input of the INBOX or the PROCESSBOX).

The mixnet contributors (peers) inspect the definition, probably negotiate
it in order to change eg the endpoint_ids (or any other attributes not shown
in the above definition), and finally create the endpoints according to the
definition.


In the sphinxmix case (static routing) we start off with::

  [
    {
        "peer_id": joint_peer,
        "endpoint_id": "our_sphinx_mixnet",
        "endpoint_type": "SPHINXMIX_STATIC_GW",
        "size_min": 3,
        "links": [{"from_endpoint_id": "peer2_mix",
                   "from_box": "OUTBOX",
                   "to_box": "PROCESSBOX"}]
    },
    {
        "peer_id": peer1,
        "endpoint_id": "peer1_mix",
        "endpoint_type": "SPHINXMIX_STATIC",
        "size_min": 3,
        "links": [{"from_endpoint_id": "our_sphinx_mixnet",
                   "from_box": "ACCEPTED",
                   "to_box": "INBOX"}]
    },
    {
        "peer_id": peer2,
        "endpoint_id": "peer2_mix",
        "endpoint_type": "SPHINXMIX_STATIC",
        "size_min": 3,
        "links": [{"from_endpoint_id": "peer1_mix",
                   "from_box": "OUTBOX",
                   "to_box": "INBOX"}]
    }
  ]

Working with the endpoints
--------------------------

1. End-users post messages to 'inbox' of main endpoint.

2. Owners close the endpoint. Messages move to 'accepted'.

3. Transmission: The endpoint that expects to get its input from the main
   endpoint, polls its status until it becomes CLOSED and then retrieves the
   accepted messages.

4. The running endpoint is closed, messages are processed and uploaded, and
   the endpoint moves to state PROCESSED.

5. Similarly, steps 3 and 4 are executed by remaining peers according to
   their specified links.

6. The main endpoint waits for the last endpoint to finish processing (as
   specified in links), then pushes the processed messages to its own
   processbox. After acknowledging the processed messages though a
   negotiation, the output of the mixnet is available at the main endpoint's
   outbox.
