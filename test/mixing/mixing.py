import datetime
import time
from panoramix import client
from panoramix.canonical import from_unicode_canonical
from panoramix.agent import client as end_user
from panoramix.config import cfg

messages = sorted([('%02d' % i, 'user%s' % i) for i in range(100)])


print "Sending"
for message in messages:
    end_user.send_message(text=message[0], recipient=message[1])
print "Sent messages"

t_start = datetime.datetime.now()

mixnet_url = cfg.get('MIXNET_URL').rstrip('/')
endpoint_prefix, endpoint_id = mixnet_url.rsplit('/', 1)

def init_client():
    panoramix_client = client.PanoramixClient()
    catalog_url = cfg.get("CATALOG_URL")
    panoramix_client.register_catalog_url(catalog_url)
    backend = cfg.get("CRYPTO_BACKEND")
    panoramix_client.register_backend(backend)
    panoramix_client.register_crypto_client(cfg)
    mixnet_description = cfg.get("MIXNET_DESCRIPTION")
    panoramix_client.register_mixnet(mixnet_description)
    return panoramix_client

panoramix_client = init_client()

while True:
    outbox = panoramix_client.box_list(endpoint_id, client.OUTBOX)
    if outbox:
        print "Found outbox, checking..."
        outbox_messages = [
            (from_unicode_canonical(msg['text']), msg['recipient'])
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
print "Time elapsed", (t_end - t_start).total_seconds()
