from panoramix.wizard_common import abort, ui, cfg, on
from panoramix import wizard_common as common
import requests

AGENT_ADDRESS = "http://127.0.0.1:5000"
SEND_ADDRESS = requests.compat.urljoin(AGENT_ADDRESS, "send")


def send_message(text=None, recipient=None):
    if recipient is None:
        recipient = ui.ask_value("recipient", "Message recipient")
    if text is None:
        text = ui.ask_value("text", "Message text")

    payload = {"recipient": recipient,
               "message": text}
    r = requests.post(SEND_ADDRESS, data=payload)
    if r.status_code != requests.codes.ok:
        ui.inform("Failed with code: %s" % r.status_code)
        exit()
    ui.inform("Sent message with id %s" % r.content)


def main(text=None, recipient=None):
    import os
    ui.inform("Welcome to Panoramix client!")
    ui.inform("Configuration file is: %s" % common.config_file)
    ui.inform("Set PANORAMIX_CONFIG environment variable to override")
    send_message(text=text, recipient=recipient)


if __name__ == "__main__":
    main()
