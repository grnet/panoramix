# Contribute
{
    "data": {
        "negotiation_id": negid,
        # text is a canonical string constructed from a dict
        # with keys: "body" and "meta"
        "text": text,
        "signature": signature,
    },
    "info": {
        "operation": "contribute",
        "resource": "negotiation",
    },
    "meta": {
        # provides a signature for "data" and "info"
        "signature": sig,
        "key_data": key_data,
    },
}


# Contribution text should have the following structure:
{
    "meta": {  # this is metadata for the negotiation itself
        "accept": bool,
        "signers": list string,
    },
    "body": {
        "info": {
            "operation": "partial_update",
            "resource": "endpoint",
            "on_last_consensus_id": last_cons_id,
        },
        "data": {
            "endpoint_id": endpoint_id,
            "status": "CLOSED",
        }
    }
}


# Create negotiation
{
    "data": {},
    "info": {
        "operation": "create",
        "resource": "negotiation",
    },
    "meta": {
        "signature": sig,
        "key_data": key_data,
},
}


# Retrieve consensus
{
    "data": {
        "consensus_id": id,
    },
    "info": {
        "operation": "retrieve",
        "resource": "consensus",
    },
    "meta": {
        "signature": sig,
        "key_data": key_data,
    },
}


# Create peer
{
    "data": {
        "peer_id": the_key_id,
        "key_type": "gpg",
        "name": unique_name,
        "owners": list peer_id,
    },
    "info": {
        "operation": "create",
        "resource": "peer",
    },
    "by_consensus": {
        "consensus_id": cons_id,
        "text": {
            "data": ["ref", "data"],
            # or:
            "data": ["val", {"peer_id": the_key_id,
                             "key_type": "gpg",
                             "name": unique_name,
                             "owners": list peer_id}],
            "info": ["ref", "info"],
            # We have to choose if we allow referencing the whole dict or
            # its entries, in which case we have:
            "data": {
                "peer_id": ["ref", ["data", "peer_id"]],
                "key_type": ["val", "gpg"],
                "name": ...,
                "owners": ...,
            },
            "info": {
                "operation": ["ref", ["info", "operation"]],
                "resource": ["val", "peer"],
            },
            # Since we don't really need this fine tuning right now,
            # I'm in favor of the simpler top-level referencing (if any)
        },
    },
    "meta": {
        # provides a signature for "data", "info", and "by_consensus"
        "signature": sig,
        "key_data": key_data,
    },
}


# Create endpoint
{
    "data": {
        # notice: 
        "peer_id": peer_id,
        "name": name,
        "cycle_id": cycle_id,
        "status": "OPEN",
        "size_min": 5,
    },
    "info": {
        "operation": "create",
        "resource": "endpoint",
    },
    "by_consensus": ...,
    "meta": {
        ...
    }
}

# Update endpoint
{
    "data": {
        "endpoint_id": endpoint_id,
        "inbox_hash": inbox_hash,
        "status": "CLOSED",
    },
    "info": {
        "operation": "partial_update",
        "resource": "endpoint",
        "on_last_consensus_id": last_cons_id,
    },
    "by_consensus": {
        "consensus_id": cons_id,
        "text": {
            "data": ["ref", "data"],
            "info": ["ref", "info"],
        },
    },
    "meta": {
        # provides a signature for "data", "info", and "by_consensus"
        "signature": sig,
        "key_data": key_data,
    },
}


# Send message to inbox
{
    "data": {
        "endpoint_id": endpoint_id,
        "box": "inbox",
        "text": "the message text",
        "sender": sender_id,
        "recipient": recipient_id,
    },
    "info": {
        "operation": "create",
        # assuming it's semantically a collection under endpoint
        "resource": "message",
    },
    "meta": {
        # provides a signature for "data" and "info"
        "signature": sig,
        "key_data": key_data,
    },
}


# Uploading processed messages to outbox is done similarly,
# i.e. without consensus


# Acknowledge outbox
# Outbox messages become visible to non-owners after this action
{
    "data": {
        "endpoint_id": endpoint_id,
        "status": "PROCESSED",
        "process_proof": "proof",
        "outbox_hash": "a hash on all outbox messages",
    },
    "info": {
        "operation": "partial_update",
        "resource": "endpoint",
        "on_last_consensus_id": "last_cons_id",
    },
    "by_consensus": {
        "consensus_id": cons_id,
        "text": {
            "data": ["ref", "data"],
            "info": ["ref", "info"],
        },
    },
    "meta": {
        # provides a signature for "data", "info", and "by_consensus"
        "signature": sig,
        "key_data": key_data,
    },
}
