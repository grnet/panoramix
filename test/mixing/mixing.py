import datetime
import time
from panoramix.common import SphinxmixClient
from panoramix.agent import client as end_user
from panoramix.config import cfg

messages = sorted([('%02d' % i, 'user%s' % i) for i in range(100)])


t_start = datetime.datetime.now()
print "Sending"
for message in messages:
    end_user.send_message(text=message[0], recipient=message[1])
print "Sent messages"

t_sent = datetime.datetime.now()

mixnet_url = cfg.get('MIXNET_URL').rstrip('/')
endpoint_prefix, endpoint_id = mixnet_url.rsplit('/', 1)
out_endpoint_id = '%s_output' % endpoint_id


def init_client():
    panoramix_client = SphinxmixClient()
    catalog_url = cfg.get("CATALOG_URL")
    panoramix_client.register_catalog_url(catalog_url)
    panoramix_client.register_crypto_client(cfg)
    return panoramix_client

panoramix_client = init_client()

while True:
    outbox = panoramix_client.messages_list(out_endpoint_id)
    if outbox:
        print "Found outbox, checking..."
        outbox_messages = [
            (msg['text'], msg['recipient'])
            for msg in outbox
        ]
        if messages == outbox_messages:
            raise AssertionError("messages not shuffled")
        if messages != sorted(outbox_messages):
            raise AssertionError("messages do not match")
        print "Outbox verified!"
        break
    else:
        print "Outbox not ready yet..."
        time.sleep(1)

t_end = datetime.datetime.now()
print "Time sending", (t_sent - t_start).total_seconds()
print "Time mixing", (t_end - t_sent).total_seconds()
print "Time total", (t_end - t_start).total_seconds()
