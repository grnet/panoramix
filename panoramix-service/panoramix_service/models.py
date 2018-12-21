# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models


class Peer(models.Model):
    name = models.CharField(max_length=255)
    peer_id = models.CharField(max_length=255, primary_key=True)
    key_type = models.IntegerField()
    crypto_backend = models.CharField(max_length=255)
    crypto_params = models.TextField()
    key_data = models.TextField(unique=True)
    status = models.CharField(max_length=255)


class Owner(models.Model):
    peer = models.ForeignKey(Peer, related_name='owners')
    position = models.IntegerField()
    owner_key_id = models.CharField(max_length=255)

    class Meta:
        unique_together = ["peer", "owner_key_id"]


class Endpoint(models.Model):
    endpoint_id = models.CharField(max_length=255, primary_key=True)
    peer_id = models.CharField(max_length=255, db_index=True)
    owner = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    public = models.BooleanField()
    endpoint_type = models.CharField(max_length=255)
    endpoint_params = models.TextField()
    current_cycle = models.ForeignKey(
        'Cycle', null=True, related_name='current_of')

    @property
    def current_cycle_property(self):
        if self.current_cycle is None:
            return 0
        return self.current_cycle.cycle


class Cycle(models.Model):
    endpoint = models.ForeignKey(Endpoint, related_name='cycles')
    cycle = models.IntegerField()
    state = models.CharField(max_length=255, db_index=True)

    @property
    def message_count(self):
        return self.cycle_messages.all().count()

    class Meta:
        unique_together = ["endpoint", "cycle"]


class Message(models.Model):
    endpoint = models.ForeignKey(Endpoint, related_name='endpoint_messages')
    cycle = models.ForeignKey(Cycle, related_name='cycle_messages')
    serial = models.IntegerField(null=True)
    sender = models.CharField(max_length=255)  # some peer
    recipient = models.CharField(max_length=255)  # some peer
    text = models.TextField()
#    message_hash = models.CharField(max_length=255)
    state = models.CharField(max_length=255, db_index=True)

    class Meta:
        pass
        # unique_together = ["endpoint_id", "box", "message_hash"]
        # index_together = ["endpoint_id", "box", "id"]
