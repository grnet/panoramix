# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-11-08 14:56
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Contribution',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField()),
                ('latest', models.BooleanField()),
                ('signer_key_id', models.CharField(max_length=255)),
                ('signature', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='Negotiation',
            fields=[
                ('id', models.CharField(max_length=255, primary_key=True, serialize=False)),
                ('text', models.TextField(null=True)),
                ('status', models.CharField(choices=[('OPEN', 'OPEN'), ('DONE', 'DONE')], default='OPEN', max_length=255)),
                ('timestamp', models.DateTimeField(null=True)),
                ('consensus_id', models.CharField(max_length=255, null=True, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='Signing',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('signer_key_id', models.CharField(max_length=255)),
                ('signature', models.TextField()),
                ('negotiation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='signings', to='consensus_service.Negotiation')),
            ],
        ),
        migrations.AddField(
            model_name='contribution',
            name='negotiation',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contributions', to='consensus_service.Negotiation'),
        ),
        migrations.AlterIndexTogether(
            name='contribution',
            index_together=set([('negotiation', 'signer_key_id')]),
        ),
    ]
