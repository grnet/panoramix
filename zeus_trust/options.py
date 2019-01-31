TYPES = ['string', 'int', 'datetime', 'dict', 'file']
ACTIONS = ['choices', 'compute_element', 'compute']
MODES = ['interactive', 'auto']


TRUSTEE_OPTIONS = {
    'stage_A': {
        'last_consensus': {
            'type': 'string',
            'action': 'compute',
            'mode': 'auto',
            'function': 'get_last_consensus',
            'key_label': 'Last consensus ID',
        },
        'signing_cryptosystem': {
            'type': 'string',
            'action': 'choices',
            'choices': ['ECDSA', 'RSA'],
        },
        'trustees': {
            'type': 'dict',
            'action': 'compute_element',
            'label': 'Join',
            'function': 'set_signing_crypto',
            'undo': 'unregister_crypto',
            'params': ['signing_cryptosystem'],
            'icon': 'playlist_add',
        },
        'trustees/*': {
            'type': 'string',
            'mode': 'auto'
        },
    },

    'stage_B': {
        'last_consensus': {
            'type': 'string',
            'action': 'compute',
            'mode': 'auto',
            'function': 'get_last_consensus',
            'key_label': 'Last consensus ID',
        },
        'election_cryptosystem': {
            'type': 'string',
            'action': 'choices',
            'choices': ['ElGamalIntegers', 'ElGamalCurves'],
        },
        'public_shares': {
            'type': 'dict',
            'action': 'compute_element',
            'label': 'Add Share',
            'function': 'set_election_public',
            'undo': 'unset_election_public',
            'params': ['election_cryptosystem'],
        },
        'public_shares/*': {
            'type': 'string',
        },
        'election_name': {'type': 'string'},
        'no_of_mixers': {'type': 'int'},
        'mixnet': {
            'type': 'string',
            'action': 'choices',
            'choices': ['SakoKilian', 'HatShuffle', 'Verificatum'],
        },
    },

    'stage_C': {
        'last_consensus': {
            'type': 'string',
            'action': 'compute',
            'mode': 'auto',
            'function': 'get_last_consensus',
            'key_label': 'Last consensus ID',
        },
        'mixers': {
            'type': 'dict',
            'action': 'compute_element',
            'label': 'Join',
            'function': 'get_signing_key',
            'params': [],
        },
        'mixers/*': {
            'type': 'string',
        },
    },

    'stage_D': {
        'last_consensus': {
            'type': 'string',
            'action': 'compute',
            'mode': 'auto',
            'function': 'get_last_consensus',
            'key_label': 'Last consensus ID',
        },
        'opens_at': {'type': 'datetime'},
        'closes_at': {'type': 'datetime'},
        'candidates': {
            'type': 'file',
            'action': 'compute',
            'mode': 'auto',
            'function': 'hash_candidates',
        },
        'voters': {
            'type': 'file',
            'action': 'compute',
            'mode': 'auto',
            'function': 'hash_voters',
        },
    },

    'stage_E': {
        'last_consensus': {
            'type': 'string',
            'action': 'compute',
            'mode': 'auto',
            'function': 'get_last_consensus',
            'key_label': 'Last consensus ID',
        },
        'extensions': {
            'type': 'dict',
            'action': 'compute_element',
            'label': 'Extend',
            'function': 'new_extension',
        },
        'extensions/*': {
            'type': 'datetime',
        },
    },

    'stage_F': {
        'last_consensus': {
            'type': 'string',
            'action': 'compute',
            'mode': 'auto',
            'function': 'get_last_consensus',
            'key_label': 'Last consensus ID',
        },
        'votes': {
            'type': 'file',
            'action': 'compute',
            'mode': 'auto',
            'function': 'hash_votes',
            'label': 'Report',
        },
    },

    'stage_G': {
        'last_consensus': {
            'type': 'string',
            'action': 'compute',
            'mode': 'auto',
            'function': 'get_last_consensus',
            'key_label': 'Last consensus ID',
        },
        'mixes': {
            'type': 'dict',
            'action': 'compute_element',
            'label': 'Mix',
            'function': 'mix_and_verify',
        },
        'mixes/*': {
            'type': 'file',
        },
    },

    'stage_H': {
        'last_consensus': {
            'type': 'string',
            'action': 'compute',
            'mode': 'auto',
            'function': 'get_last_consensus',
            'key_label': 'Last consensus ID',
        },
        'decryptions': {
            'type': 'dict',
            'action': 'compute_element',
            'label': 'Decrypt',
            'function': 'make_decryption_factors',
        },
        'decryptions/*': {
            'type': 'file',
        },
    },
}

MIXER_OPTIONS = {
    'stage_C': {
        'stage_B_result': {
            'type': 'string',
            'action': 'compute',
            'mode': 'auto',
            'function': 'get_stage_result',
            'params': ['stage'],
            'actuals': {'stage': 'stage_B'},
        },
        'mixers': {
            'type': 'dict',
            'action': 'compute_element',
            'function': 'set_signing_crypto',
            'undo': 'unregister_crypto',
            'params': ['cryptosystem', 'path'],
        },
    },

    'stage_F': {
        'stage_E_result': {
            'type': 'string',
            'action': 'compute',
            'mode': 'auto',
            'function': 'get_stage_result',
            'params': ['stage'],
            'actuals': {'stage': 'stage_E'},
        },
        'mixed_data': {
            'type': 'string',
            'action': 'compute',
            'mode': 'auto',
            'function': 'verify_all_mixes',
        },
    },

}
