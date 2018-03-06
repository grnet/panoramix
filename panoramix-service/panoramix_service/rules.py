# COLUMNS = ('collection', 'action', 'role', 'filter', 'check', 'fields', 'comment')

RULES = [
    ('panoramix/peers', 'create', '*', '*', '*', '*', ''),
    ('panoramix/peers', 'list', '*', '*', '*', '*', ''),
    ('panoramix/peers', 'retrieve', '*', '*', '*', '*', ''),

    ('panoramix/endpoints', 'create', '*', '*', '*', '*', ''),
    ('panoramix/endpoints', 'list', '*', '*', '*', '*', ''),
    ('panoramix/endpoints', 'retrieve', '*', '*', '*', '*', ''),

    ('panoramix/endpoints/messages', 'create', '*',
     '*', 'set_cycle', 'sender,recipient,text', ''),

    ('panoramix/endpoints/messages', 'retrieve', '*', '*', '*', '*', ''),
    ('panoramix/endpoints/messages', 'list', '*', '*', '*', '*', ''),

    ('panoramix/endpoints/cycles', 'create', '*',
     '*', '*', 'state', ''),

    ('panoramix/endpoints/cycles', 'retrieve', '*',
     '*', '*', 'cycle,state,message_count', ''),

    # ('panoramix/endpoints/cycles', 'list', '*',
    #  '*', '*', 'cycle,state,message_count', ''),

    ('panoramix/endpoints/cycles', 'list', '*',
     '*', '*', '*', ''),

    ('panoramix/endpoints/cycles', 'partial_update', '*',
     'update_non_current', '*', 'state', ''),

    ('panoramix/endpoints/cycles', 'bulk-upload', '*',
     '*', '*', 'messages/sender,messages/recipient,messages/text,messages/state', ''),

    ('panoramix/endpoints/cycles', 'set-message-state', '*',
     '*', '*', 'messages/id,messages/state', ''),

    ('panoramix/endpoints/cycles', 'purge', '*',
     '*', '*', 'cycle', ''),

]

def get_rules():
    return RULES
