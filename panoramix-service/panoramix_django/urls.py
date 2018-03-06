"""panoramix_django URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url
from django.contrib import admin

from apimas_django import provider
from panoramix_django.spec import APP_CONFIG, DEPLOY_CONFIG

try:
    app_spec = provider.configure_apimas_app(APP_CONFIG)
    deployment_spec = provider.configure_spec(app_spec, DEPLOY_CONFIG)

    api_urls = provider.construct_views(deployment_spec)
except:
    import pdb; pdb.post_mortem()

urlpatterns = [
    url(r'^admin/', admin.site.urls),
]
urlpatterns.extend(api_urls)
