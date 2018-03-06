DEPLOY_CONFIG = {}

PEERS = {
    '.field.collection.django': {},
    'model': 'panoramix_service.models.Peer',
    'id_field': 'peer_id',
    'fields': {
        'peer_id': {
            '.field.string': {},
            '.flag.noupdate': {}},
        'name': {
            '.field.string': {},
            '.flag.noupdate': {}},
        'key_type': {
            '.field.integer': {},
            '.flag.noupdate': {}},
        'key_data': {
            '.field.string': {},
            '.flag.noupdate': {}},
        'crypto_backend': {
            '.field.string': {},
            '.flag.noupdate': {}},
        'crypto_params': {
            '.field.text': {},
            '.flag.noupdate': {}},
        'owners': {
            '.field.collection.django': {},
            'model': 'panoramix_service.models.Owner',
            'bound': 'peer',
            'flat': True,
            'id_field': 'owner_key_id',
            '.flag.noupdate': {},
            'fields': {
                'owner_key_id': {
                    '.field.string': {},
                    '.flag.noupdate': {}},
            },
        },
    },
    'actions': {
        '.action-template.django.list': {},
        '.action-template.django.create': {},
        '.action-template.django.retrieve': {},
    },
}

def MESSAGE_FIELDS(writable=False):
    idspec = {'.field.integer': {}}
    if not writable:
        idspec['.flag.nowrite'] = {}

    return {
        'id': idspec,
        'serial': {
            '.field.integer': {},
            '.flag.nullable.default': {},
            '.flag.noupdate': {}},
        'endpoint_id': {
            '.field.string': {},
            '.flag.nowrite': {}},
        'cycle': {
            '.field.integer': {},
            '.flag.nowrite': {},
            'source': 'cycle.cycle',
            '.flag.filterable': {}},
        'cycle_id': {
            '.field.integer': {},
            '.flag.noread': {},
            '.flag.nowrite': {}},
        'sender': {
            '.field.string': {},
            '.flag.noupdate': {}},
        'recipient': {
            '.field.string': {},
            '.flag.noupdate': {}},
        'text': {
            '.field.text': {},
            '.flag.noupdate': {}},
        'state': {
            '.field.string': {},
            'default': 'INBOX',
            '.flag.filterable': {}},
        # 'message_hash': {
        #     '.field.string': {}},
    }

ENDPOINTS = {
    '.field.collection.django': {},
    'model': 'panoramix_service.models.Endpoint',
    'id_field': 'endpoint_id',
    'actions': {
        '.action-template.django.list': {},
        '.action-template.django.create': {},
        '.action-template.django.retrieve': {},
    },
    'fields': {
        'endpoint_id': {
            '.field.string': {},
            '.flag.noupdate': {}},
        'peer_id': {
            '.field.string': {},
            '.flag.noupdate': {},
            '.flag.filterable': {}},
        'description': {
            '.field.string': {},
            '.flag.noupdate': {}},
        'endpoint_type': {
            '.field.string': {},
            '.flag.noupdate': {}},
        'endpoint_params': {
            '.field.text': {},
            '.flag.noupdate': {}},
        'public': {
            '.field.boolean': {},
            '.flag.noupdate': {}},
        'current_cycle': {
            '.field.integer': {},
            '.flag.nowrite': {},
            'source': 'current_cycle_property'},
        'cycles': {
            '.field.collection.django': {},
            '.flag.noread': {},
            '.flag.nowrite': {},
            'model': 'panoramix_service.models.Cycle',
            'bound': 'endpoint',
            'id_field': 'cycle',
            'actions': {
                '.action-template.django.partial_update': {},
                '.action-template.django.retrieve': {},
                '.action-template.django.list': {},
                '.action-template.django.create': {},
                'create': {
                    ':custom_create_handler': 'panoramix_service.logic.new_cycle',
                },
                'bulk-upload': {
                    '.action.django.recipe.partial_update': {},
                    'method': 'POST',
                    'status_code': 201,
                    'url': '/*/bulk-upload/',
                    ':custom_update_handler': 'panoramix_service.logic.bulk_upload',
                },
                'set-message-state': {
                    '.action.django.recipe.partial_update': {},
                    'method': 'POST',
                    'status_code': 200,
                    'url': '/*/set-message-state/',
                    ':custom_update_handler': 'panoramix_service.logic.set_message_state',
                },
                'purge': {
                    '.action.django.recipe.partial_update': {},
                    'method': 'POST',
                    'status_code': 200,
                    'url': '/*/purge/',
                    ':custom_update_handler': 'panoramix_service.logic.purge',
                },
            },
            'fields': {
                'cycle': {
                    '.field.integer': {},
                    '.flag.nowrite': {},
                    '.flag.filterable': {}},
                'state': {
                    '.field.string': {},
                    '.flag.filterable': {},
                    'default': 'OPEN'},
                'message_count': {
                    '.field.integer': {},
                    '.flag.nowrite': {}},
                'messages': {
                    '.field.collection.django': {},
                    '.flag.noread': {},
                    'model': 'panoramix_service.models.Message',
                    'source': 'cycle_messages',
                    'bound': 'cycle',
                    'fields': MESSAGE_FIELDS(writable=True),
                },
            },
        },
        'messages': {
            '.field.collection.django': {},
            '.flag.noread': {},
            'model': 'panoramix_service.models.Message',
            'source': 'endpoint_messages',
            'bound': 'endpoint',
            'actions': {
                '.action-template.django.create': {},
                '.action-template.django.list': {},
            },
            'fields': MESSAGE_FIELDS(),
        },
    },
}

APP_CONFIG = {
    '.apimas_app': {},
    ':permission_rules': 'panoramix_service.rules.get_rules',
    ':permissions_namespace': 'panoramix_service.logic',
    'endpoints': {
        'panoramix': {
            'collections': {
                'peers': PEERS,
                'endpoints': ENDPOINTS,
            },
        },
    },
}
