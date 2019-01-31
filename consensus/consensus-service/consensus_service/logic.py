import os
import base64
import datetime
from apimas import errors
from consensus_service import models
from consensus_client import utils
from apimas.utils import import_object

get_now = datetime.datetime.utcnow

client_path = os.environ.get('CONSENSUS_CRYPTO_CLIENT')
crypto_client_class = import_object(client_path) if client_path \
                      else utils.ECDSAClient
crypto_client = crypto_client_class()


def generate_random_key():
    s = os.urandom(32)
    return base64.urlsafe_b64encode(s).rstrip('=')


def get_negotiation_for_update(negotiation_id):
    try:
        objects = models.Negotiation.objects.select_for_update()
        return objects.get(id=negotiation_id)
    except models.Negotiation.DoesNotExist:
        raise errors.NotFound("Negotiation '%s' not found." % negotiation_id)


def mk_signings(negotiation, contributions):
    signings_dict = {}
    signings = []
    for contribution in contributions:
        signings.append(models.Signing(
            negotiation=negotiation,
            signer_key_id=contribution.signer_key_id,
            signature=contribution.signature))
        signings_dict[contribution.signer_key_id] = contribution.signature
    models.Signing.objects.bulk_create(signings)
    return signings_dict


def get_latest_contributions(negotiation):
    return models.Contribution.objects.filter(
        negotiation=negotiation, latest=True)


def check_close_negotiation(negotiation):
    latests = get_latest_contributions(negotiation)
    text_set = set(c.text for c in latests)
    if len(text_set) == 1:
        text = text_set.pop()
        if not utils.has_accept_meta(text):
            return

        now = get_now()
        signings_dict = mk_signings(negotiation, latests)
        hashable = {
            "timestamp": now.isoformat(),
            "negotiation_id": negotiation.id,
            "text": text,
            "signings": signings_dict,
        }
        consensus_id = utils.hash_with_canonical(hashable)
        negotiation.text = text
        negotiation.timestamp = now
        negotiation.consensus_id = consensus_id
        negotiation.status = models.NegotiationStatus.DONE
        negotiation.save()


def contribute(request_data, negotiation_id, context):
    negotiation = get_negotiation_for_update(negotiation_id)
    if negotiation.status != models.NegotiationStatus.OPEN:
        raise errors.ValidationError("Negotiation is not open")
    text = request_data["text"]
    signature = request_data["signature"]
    signer_key_id = crypto_client.verify(signature, text)
    if signer_key_id is None:
        raise errors.ValidationError("Contribution's signature is not valid")

    negotiation.contributions.filter(
        signer_key_id=signer_key_id).update(latest=False)

    contrib = models.Contribution.objects.create(
        latest=True,
        negotiation=negotiation, text=text,
        signer_key_id=signer_key_id, signature=signature)

    check_close_negotiation(negotiation)
    return contrib
