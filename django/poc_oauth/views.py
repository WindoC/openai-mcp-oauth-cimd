import base64
import binascii
import hashlib
import logging
from urllib.parse import unquote_plus

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider.models import get_access_token_model, get_application_model

log = logging.getLogger("poc_oauth.introspection")


@method_decorator(csrf_exempt, name="dispatch")
class MCPIntrospectionView(View):
    """Dedicated POST-only, service-authenticated identity contract."""

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    def post(self, request):
        try:
            scheme, encoded = request.headers.get("Authorization", "").split(" ", 1)
            if scheme.lower() != "basic":
                raise ValueError
            client_id, secret = base64.b64decode(encoded, validate=True).decode().split(":", 1)
            client_id, secret = unquote_plus(client_id), unquote_plus(secret)
        except (ValueError, binascii.Error, UnicodeError):
            return self.unauthorized()
        if client_id != settings.MCP_INTROSPECTION_CLIENT_ID:
            return self.unauthorized()
        application = get_application_model().objects.filter(client_id=client_id).first()
        if (
            application is None
            or application.client_type != application.CLIENT_CONFIDENTIAL
            or not check_password(secret, application.client_secret)
        ):
            return self.unauthorized()
        value = request.POST.get("token")
        if not value:
            return JsonResponse({"error": "invalid_request"}, status=400)
        checksum = hashlib.sha256(value.encode()).hexdigest()
        token = (
            get_access_token_model()
            .objects.select_related("user", "application")
            .filter(
                token_checksum=checksum,
            )
            .first()
        )
        reason = None
        if token is None:
            reason = "unknown_token"
        elif not token.is_valid():
            reason = "expired_or_invalid"
        elif token.user is None:
            reason = "missing_user"
        elif not token.user.is_active or getattr(token.user, "is_blocked", False):
            reason = "inactive_user"
        elif token.application is None:
            reason = "missing_application"
        elif settings.MCP_RESOURCE_URI not in (token.resource or []):
            reason = "wrong_resource"
        elif "calculator:execute" not in token.scope.split():
            reason = "missing_scope"
        if reason:
            log.info(
                "introspection inactive: reason=%s expected_resource=%s",
                reason,
                settings.MCP_RESOURCE_URI,
            )
            # Diagnostic headers are only returned after service authentication.
            # Keep the inactive-token JSON contract unchanged.
            return JsonResponse(
                {"active": False},
                headers={
                    "X-PoC-Introspection-Reason": reason,
                    "X-PoC-Expected-Resource": settings.MCP_RESOURCE_URI,
                },
            )
        return JsonResponse(
            {
                "active": True,
                "sub": str(token.user.pk),
                "iss": settings.MCP_ISSUER,
                "client_id": token.application.client_id,
                "scope": token.scope,
                "exp": int(token.expires.timestamp()),
                "aud": token.resource,
            },
            headers={"Cache-Control": "no-store"},
        )

    @staticmethod
    def unauthorized():
        return JsonResponse(
            {"error": "invalid_client"},
            status=401,
            headers={"WWW-Authenticate": 'Basic realm="mcp-introspection"'},
        )
