import os
import time
from consensus_client import zeus_events
from consensus_client.config import Config
import sys
WORKSPACE = os.environ['WORKSPACE']

role = sys.argv[1]  # 'admin' or 'trustee' or 'check_done'

if role == 'check_done':
    admin_cfg_file = os.path.join(WORKSPACE, 'admin')
    admin_cfg = Config(admin_cfg_file)
    while True:
        decryption = admin_cfg.get_value('decryption')
        if decryption is not None:
            break
        admin_cfg.reload()
        time.sleep(2)

else:
    cfg_file = os.path.join(WORKSPACE, role)
    pad_file = os.path.join(WORKSPACE, 'pad')
    doc_file = os.path.join(WORKSPACE, 'election.zeus')

    zeus_events.main(cfg_file, pad_file, doc_file)
