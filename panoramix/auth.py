from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from panoramix import functions
from panoramix import canonical


class AuthUser(object):
    apimas_roles = ['peer']

    def __init__(self, peer_id):
        self.peer_id = peer_id


class Auth(BaseAuthentication):
    def verify(self, mixnet_data, signature, public=None):
        canonical_data = canonical.to_canonical(
            canonical.from_unicode(mixnet_data))
        valid, key_id = functions.verify(
            canonical_data, signature, public=public)
        if not valid:
            raise AuthenticationFailed("signature is not valid")
        return key_id

    def _authenticate(self, request):
        data = request.data.copy()
        if request.method == "GET" and not data:
            return None
        metadata = data.pop("meta", None)
        if metadata is None:
            raise AuthenticationFailed("no metadata")
        signature = metadata["signature"]

        if not data or signature is None:
            raise AuthenticationFailed("empty data or sig")
        key_data = metadata.get("key_data")
        request_peer_id = self.verify(data, signature, public=key_data)
        auth_user = AuthUser(request_peer_id)
        return auth_user, key_data

    def authenticate(self, request):
        try:
            return self._authenticate(request)
        except AttributeError as e:
            # Because request.user in a property of Request, an AttributeError
            # is wrongly perceived to mean that the user is missing.
            # To avoid this, wrap it as a ValueError.
            raise ValueError(e)
