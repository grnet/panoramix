from django.conf.urls import patterns, url
from django.contrib import admin
admin.autodiscover()

from apimas.modeling.adapters.drf import django_rest
from panoramix.permissions import PERMISSION_RULES
from panoramix.spec import SPEC

SPEC['.endpoint']['permissions'] = PERMISSION_RULES

adapter = django_rest.DjangoRestAdapter()
adapter.construct(SPEC)
adapter.apply()

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    adapter.urls
]


