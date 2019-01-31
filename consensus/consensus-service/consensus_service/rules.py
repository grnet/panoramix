# COLUMNS = ('collection', 'action', 'role', 'filter', 'check', 'fields', 'comment')

RULES = [
    ('consensus/negotiations', 'create', '*', '*', '*', '*', ''),
    ('consensus/negotiations', 'retrieve', '*', '*', '*', '*', ''),
    ('consensus/negotiations/contributions', 'create', '*', '*', '*', '*', ''),
    ('consensus/negotiations/contributions', 'retrieve', '*', '*', '*', '*', ''),
    ('consensus/consensus', 'list', '*', '*', '*', '*', ''),
    ('consensus/consensus', 'retrieve', '*', '*', '*', '*', ''),
]


def get_rules():
    return RULES
