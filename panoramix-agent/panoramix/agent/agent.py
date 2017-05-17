from flask import Flask, request, abort

from panoramix.config import cfg
from panoramix import wizard_common as common
from panoramix.client import PanoramixClient, ApimasClientException

app = Flask(__name__)

client = PanoramixClient()


def init():
    catalog_url = cfg.get("CATALOG_URL")
    client.register_catalog_url(catalog_url)
    backend = cfg.get("CRYPTO_BACKEND")
    client.register_backend(backend)
    client.register_crypto_client(cfg)
    mixnet_description = cfg.get("MIXNET_DESCRIPTION")
    client.register_mixnet(mixnet_description)


@app.route("/send", methods=["POST"])
def send_message():
    recipient = request.form["recipient"]
    message = request.form["message"]
    prepared_message = client.construct_message(recipient, message)
    try:
        r = client.send_message_to_mixnet(prepared_message)
    except ApimasClientException as e:
        abort(e.response.status_code)
    return str(r["data"]["id"])


def main():
    init()
    app.run()

if __name__ == "__main__":
    main()
