# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from collections import namedtuple
from django.db import models


def to_choices(named):
    values = list(named)
    return [(value, value) for value in values]


def mk_tuple(name, fields):
    tpl = namedtuple(name, fields)
    return tpl(*fields)


NegotiationStatus = mk_tuple("NegotiationStatus", ["OPEN", "DONE"])


class Negotiation(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    text = models.TextField(null=True)
    status = models.CharField(
        max_length=255, choices=to_choices(NegotiationStatus),
        default=NegotiationStatus.OPEN)
    timestamp = models.DateTimeField(null=True)
    consensus_id = models.CharField(max_length=255, null=True, unique=True)


finished_negotiations = models.Q(status=NegotiationStatus.DONE)


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
