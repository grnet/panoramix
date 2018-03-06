from panoramix.config import cfg
from panoramix.common import ui, config_file, SphinxmixClient
import requests
import argparse


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


def output_cycle(cycle):
    client = SphinxmixClient()
    client.register_catalog_url(cfg.get('CATALOG_URL'))
    output_endpoint_id = '%s_output' % cfg.get('ENDPOINT_ID')
    messages = client.messages_list(output_endpoint_id, cycle=cycle)
    ui.inform(messages)


def ack_cycle(cycle):
    client = SphinxmixClient()
    client.register_catalog_url(cfg.get('CATALOG_URL'))
    output_endpoint_id = '%s_output' % cfg.get('ENDPOINT_ID')
    r = client.cycle_set_state(output_endpoint_id, cycle, 'ACK')
    ui.inform(r)


parser = argparse.ArgumentParser(description='Panoramix client')
parser.add_argument('--output', metavar='CYCLE', type=int,
                    help='Print output of CYCLE')
parser.add_argument('--ack', metavar='CYCLE', type=int,
                    help='Acknowledge output of CYCLE')


def main():
    ui.inform("Welcome to Panoramix client!")
    ui.inform("Configuration file is: %s" % config_file)
    ui.inform("Set PANORAMIX_CONFIG environment variable to override")
    args = parser.parse_args()
    if args.output is None and args.ack is None:
        send_message(text=text, recipient=recipient)
        return
    if args.output is not None:
        output_cycle(args.output)
    if args.ack is not None:
        ack_cycle(args.ack)


if __name__ == "__main__":
    main()
