from django.db import models
from djchoices import DjangoChoices, ChoiceItem

import datetime

get_now = datetime.datetime.utcnow


class NegotiationStatus(DjangoChoices):
    OPEN = ChoiceItem("OPEN")
    DONE = ChoiceItem("DONE")


class Negotiation(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    text = models.TextField(null=True)
    status = models.CharField(
        max_length=255, choices=NegotiationStatus.choices,
        default=NegotiationStatus.OPEN)
    timestamp = models.DateTimeField(null=True)
    consensus = models.CharField(max_length=255, null=True, unique=True)

    def get_latest_contributions(self):
        return Contribution.objects.filter(latest=True, negotiation=self)

    def get_text_and_signatures(self, contributions):
        texts = set(c.text for c in contributions)
        assert len(texts) == 1
        text = texts.pop()
        signings = dict((c.signer_key_id, c.signature)
                        for c in contributions)
        return {
            "text": text,
            "signings": signings,
        }

    def to_consensus_dict(self):
        contributions = self.get_latest_contributions()
        d = {}
        d.update(self.get_text_and_signatures(contributions))
        d["id"] = self.consensus
        d["negotiation_id"] = self.id
        d["timestamp"] = self.timestamp
        return d


class Signing(models.Model):
    negotiation = models.ForeignKey(Negotiation, related_name="signings")
    signer_key_id = models.CharField(max_length=255)
    signature = models.TextField()


class Contribution(models.Model):
    negotiation = models.ForeignKey(Negotiation, related_name="contributions")
    text = models.TextField()
    latest = models.BooleanField()
    signer_key_id = models.CharField(max_length=255)
    signature = models.TextField()

    class Meta:
        index_together = ["negotiation", "signer_key_id"]


class KeyType(DjangoChoices):
    RSA_ENC_SIG = ChoiceItem(1)
    RSA_ENC = ChoiceItem(2)
    RSA_SIG = ChoiceItem(3)
    ELGAMAL = ChoiceItem(16)
    DSA = ChoiceItem(17)
    ELLIPTIC_CURVE = ChoiceItem(18)
    ECDSA = ChoiceItem(19)


class PeerStatus(DjangoChoices):
    READY = ChoiceItem("READY")
    DELETED = ChoiceItem("DELETED")


class Peer(models.Model):
    name = models.CharField(max_length=255)
    peer_id = models.CharField(max_length=255, primary_key=True)
    key_type = models.IntegerField(choices=KeyType.choices)
    crypto_backend = models.CharField(max_length=255)
    crypto_params = models.TextField()
    key_data = models.TextField(unique=True)
    status = models.CharField(max_length=255, choices=PeerStatus.choices)

    def log_consensus(self, consensus_id):
        self.consensus_logs.create(
            consensus_id=consensus_id,
            status=self.status,
            timestamp=get_now())

    def list_owners(self):
        owners = self.owners.all()
        return [owner.show() for owner in owners]


class PeerConsensusLog(models.Model):
    peer = models.ForeignKey(Peer, related_name="consensus_logs")
    consensus_id = models.CharField(max_length=255)
    timestamp = models.DateTimeField()
    status = models.CharField(max_length=255, choices=PeerStatus.choices)

    class Meta:
        index_together = ["peer", "id"]


class Owner(models.Model):
    peer = models.ForeignKey(Peer, related_name='owners')
    owner_key_id = models.CharField(max_length=255)

    class Meta:
        unique_together = ["peer", "owner_key_id"]

    def show(self):
        return self.owner_key_id


class EndpointType(DjangoChoices):
    GATEWAY = ChoiceItem("GATEWAY")
    PATH = ChoiceItem("PATH")
    ONION = ChoiceItem("ONION")
    ZEUS_BOOTH = ChoiceItem("ZEUS_BOOTH")
    ZEUS_SK_MIX = ChoiceItem("ZEUS_SK_MIX")
    ZEUS_SK_PARTIAL_DECRYPT = ChoiceItem("ZEUS_SK_PARTIAL_DECRYPT")
    ZEUS_SK_DECRYPT = ChoiceItem("ZEUS_SK_DECRYPT")
    ZEUS_SK_COMBINE = ChoiceItem("ZEUS_SK_COMBINE")
    SPHINXMIX = ChoiceItem("SPHINXMIX")
    USER = ChoiceItem("USER")


class CycleStatus(DjangoChoices):
    OPEN = ChoiceItem("OPEN")
    FULL = ChoiceItem("FULL")
    CLOSED = ChoiceItem("CLOSED")
    PROCESSED = ChoiceItem("PROCESSED")


class Endpoint(models.Model):
    endpoint_id = models.CharField(max_length=255, primary_key=True)
    peer_id = models.CharField(max_length=255, db_index=True)
    description = models.CharField(max_length=255)
    size_min = models.IntegerField()
    size_max = models.IntegerField()
    endpoint_type = models.CharField(
        max_length=255, choices=EndpointType.choices)
    endpoint_params = models.TextField()

    # size_current = models.IntegerField(default=0)
    # messages_total = models.IntegerField(default=0)  # what is total?
    # messages_sent = models.IntegerField(default=0)
    # messages_processed = models.IntegerField(default=0)
    # dispatch_started_at = models.DateTimeField(null=True)
    # dispatch_ended_at = models.DateTimeField(null=True)

    inbox_hash = models.CharField(max_length=255, null=True)
    outbox_hash = models.CharField(max_length=255, null=True)
    process_proof = models.TextField(null=True)
    status = models.CharField(max_length=255, choices=CycleStatus.choices)

    def log_consensus(self, consensus_id):
        self.consensus_logs.create(
            consensus_id=consensus_id,
            status=self.status,
            timestamp=get_now())

    def get_last_consensus_id(self):
        try:
            return self.consensus_logs.all().order_by("-id")[0].consensus_id
        except IndexError:
            return None


class EndpointConsensusLog(models.Model):
    endpoint = models.ForeignKey(Endpoint, related_name="consensus_logs")
    consensus_id = models.CharField(max_length=255)
    timestamp = models.DateTimeField()
    status = models.CharField(max_length=255, choices=CycleStatus.choices)

    class Meta:
        index_together = ["endpoint", "id"]


class Box(DjangoChoices):
    INBOX = ChoiceItem("INBOX")
    ACCEPTED = ChoiceItem("ACCEPTED")
    PROCESSBOX = ChoiceItem("PROCESSBOX")
    OUTBOX = ChoiceItem("OUTBOX")


class Message(models.Model):
    sender = models.CharField(max_length=255)  # some peer
    recipient = models.CharField(max_length=255)  # some peer
    text = models.TextField()
    message_hash = models.CharField(max_length=255)
    endpoint_id = models.CharField(max_length=255)
    box = models.CharField(max_length=255, choices=Box.choices, db_index=True)

    class Meta:
        unique_together = ["endpoint_id", "box", "message_hash"]
        index_together = ["endpoint_id", "box", "id"]
