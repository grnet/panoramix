from django.conf.urls import patterns, url
from django.contrib import admin
admin.autodiscover()

from apimas.drf import django_rest
from panoramix.server.permissions import PERMISSION_RULES
from panoramix.spec import SPEC

SPEC['panoramix']['.endpoint']['permissions'] = PERMISSION_RULES

adapter = django_rest.DjangoRestAdapter()
adapter.construct(SPEC)

urlpatterns = adapter.urls.values()
