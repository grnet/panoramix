from flask import Flask, request, abort

from panoramix.config import cfg
from panoramix.common import SphinxmixClient

app = Flask(__name__)

client = SphinxmixClient()


@app.route("/send", methods=["POST"])
def send_message():
    recipient = request.form["recipient"]
    text = request.form["message"]
    message = client.message_send(cfg.get('ENDPOINT_ID'),
                                  cfg.get('MIXNET_ID'),
                                  cfg.get('MIXERS'),
                                  text,
                                  recipient)
    return str(message['id'])


def main():
    client.register_catalog_url(cfg.get('CATALOG_URL'))
    client.register_crypto_client(cfg)
    app.run()

if __name__ == "__main__":
    main()
