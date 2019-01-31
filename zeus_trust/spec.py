import specular


negotiation_specs = [
    ('.negotiation_stage',
     {
         '.negotiation_stage': {},
         'type': {},
         'negotiation': {},
         'signers': {},
         'content': {},
     },
    ),

    ('.negotiation',
     {
         '.negotiation': {},
         'stages': {
             '?': {'.negotiation_stage': {}}
         },
     },
    ),

    ('.peer',
     {'.peer': {}},
    ),

    ('.cryptosystem',
     {'.cryptosystem': {}},
    ),


    ('.sign_key',
     {'.sign_key': {}},
    ),

    ('.election_key',
     {'.election_key': {}},
    ),

    ('.shares',
     {'.shares': {}},
    ),

    ('.mixes',
     {'.mixes': {}},
    ),

    ('.decryptions',
     {'.decryptions': {}},
    ),
]


negotiation_zeus_spec = {
    '.negotiation.zeus': {},
    'stages': {
        'stage_A': {
            'type': 'authority',
            'title': 'Trustees',
            'description': "Record trustees' identity",
            'negotiation': {},
            'peers': 'trustees',
            'signers': ['stage_A/trustees'],
            'content': {
                'last_consensus': {},
                'signing_cryptosystem': {'.cryptosystem': {}},
                'trustees': {
                    '?': {'.sign_key': {}},
                },
            },
        },
        'stage_B': {
            'type': 'configuration',
            'title': 'Election',
            'description': 'Configure election parameters',
            'negotiation': {},
            'signers': ['stage_A/trustees'],
            'content': {
                'last_consensus': {},
                'election_cryptosystem': {'.cryptosystem': {}},
                'public_shares': {
                    '.shares': {},
                    '?': {'.election_key': {}},
                },
                'election_name': {},
                # 'election_admin': {},
                'no_of_mixers': {},
                'mixnet': {},
            },
        },
        'stage_C': {
            'type': 'mixnet_setup',
            'title': 'Mixers',
            'description': 'Record mixing peers',
            'negotiation': {},
            'signers': ['stage_A/trustees', 'stage_C/mixers'],
            'content': {
                'last_consensus': {},
                'mixers': {
                    '?': {'.peer': {}},
                },
            },
        },
        'stage_D': {
            'type': 'activation',
            'title': 'Booth',
            'description': 'Configure booth operation, record candidates',
            'negotiation': {},
            'signers': ['stage_A/trustees'],
            'content': {
                'last_consensus': {},
                'opens_at': {},
                'closes_at': {},
                'candidates': {},
                'voters': {},
#                'excluded_voters': {},
            },
        },
        'stage_E': {
            'type': 'voting',
            'title': 'Voting',
            'description': 'Give extension or close booth',
            'negotiation': {},
            'signers': ['stage_A/trustees'],
            'content': {
                'last_consensus': {},
                'extensions': {},
            },
        },
        'stage_F': {
            'type': 'votes',
            'title': 'Votes',
            'description': 'Record cast votes',
            'negotiation': {},
            'signers': ['stage_A/trustees'],
            'content': {
                'last_consensus': {},
                'votes': {},
            },
        },
        'stage_G': {
            'type': 'mixing',
            'title': 'Mixes',
            'description': 'Record results produced from the mixnet',
            'negotiation': {},
            'signers': ['stage_A/trustees', 'stage_C/mixers'],
            'content': {
                'last_consensus': {},
                'mixes': {
                    '.mixes': {},
                    '?': {}},
            },
            'actions': ['decrypt'],
        },
        'stage_H': {
            'type': 'decryption',
            'title': 'Decryption',
            'description': 'Record decryptions produced by the trustees',
            'negotiation': {},
            'signers': ['stage_A/trustees'],
            'content': {
                'last_consensus': {},
                'decryptions': {
                    '.decryptions': {},
                    '?': {}},
            },
        },
    },
}

domain = specular.Spec()
domain.compile_schemata(negotiation_specs)
domain.compile_schema('.negotiation.zeus', negotiation_zeus_spec)
