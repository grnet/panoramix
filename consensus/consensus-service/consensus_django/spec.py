DEPLOY_CONFIG = {
    ":root_url": "http://127.0.0.1:8000/",
}

NEGOTIATIONS = {
    '.collection.django': {},
    'model': 'consensus_service.models.Negotiation',
    'actions': {
        '.action-template.django.create': {},
        '.action-template.django.retrieve': {},
    },
    'fields': {
        'id': {
            '.field.string': {},
            'default_fn': 'consensus_service.logic.generate_random_key',
        },
        'status': {
            '.field.string': {},
            '.flag.nowrite': {}},
        'consensus_id': {
            '.field.string': {},
            '.flag.nullable': {},
            '.flag.nowrite': {}},
        'contributions': {
            '.field.collection.django': {},
            '.flag.nowrite': {},
            'model': 'consensus_service.models.Contribution',
            'bound': 'negotiation',
            'actions': {
                '.action-template.django.create': {},
                'create': {
                    ':custom_create_handler': 'consensus_service.logic.contribute',
                },
            },
            'fields': {
                'id': {
                    '.field.serial': {}},
                'text': {
                    '.field.text': {}},
                'latest': {
                    '.field.boolean': {},
                    '.flag.nowrite': {}},
                'signer_key_id': {
                    '.field.string': {},
                    '.flag.nowrite': {}},
                'signature': {
                    '.field.text': {}},
            },
        },
    },
}

CONSENSUS = {
    '.collection.django': {},
    'model': 'consensus_service.models.Negotiation',
    'subset': 'consensus_service.models.finished_negotiations',
    'fields': {
        'id': {
            'source': 'consensus_id',
            '.field.string': {},
            '.flag.nowrite': {}},
        'negotiation_id': {
            'source': 'id',
            '.field.string': {},
            '.flag.nowrite': {}},
        'text': {
            '.field.text': {},
            '.flag.nowrite': {}},
        'timestamp': {
            '.field.datetime': {},
            '.flag.nowrite': {}},
        'signings': {
            '.field.collection.django': {},
            'model': 'consensus_service.models.Signing',
            'bound': 'negotiation',
            'fields': {
                'id': {
                    '.field.serial': {}},
                'signer_key_id': {
                    '.field.string': {},
                    '.flag.nowrite': {}},
                'signature': {
                    '.field.text': {},
                    '.flag.nowrite': {}},
            },
        },
    },
    'actions': {
        '.action-template.django.list': {},
        '.action-template.django.retrieve': {},
    },
}

APP_CONFIG = {
    '.apimas_app': {},
    ':permission_rules': 'consensus_service.rules.get_rules',
    'endpoints': {
        'consensus': {
            'collections': {
                'negotiations': NEGOTIATIONS,
                'consensus': CONSENSUS,
            },
        },
    },
}
