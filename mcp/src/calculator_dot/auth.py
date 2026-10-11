import logging
import time

import httpx
from fastmcp.server.auth import AccessToken, TokenVerifier

from calculator_dot.config import Settings

log = logging.getLogger("calculator.auth")


class IdentityUnavailable(Exception):
    """Transient identity service failure; never contains upstream response data."""


class DjangoTokenVerifier(TokenVerifier):
    def __init__(self, config: Settings, client: httpx.AsyncClient | None = None):
        super().__init__(required_scopes=[config.mcp_required_scope])
        self.config = config
        self.client = client

    @staticmethod
    def reject(reason):
        log.warning("token_rejected reason=%s", reason)
        return None

    async def verify_token(self, token: str) -> AccessToken | None:
        async def fetch(client):
            try:
                response = await client.post(
                    self.config.django_introspection_url,
                    data={"token": token, "token_type_hint": "access_token"},
                    auth=httpx.BasicAuth(
                        self.config.introspection_client_id,
                        self.config.introspection_client_secret.get_secret_value(),
                    ),
                    timeout=self.config.introspection_timeout,
                    follow_redirects=False,
                )
            except httpx.RequestError:
                log.warning("introspection_unavailable reason=transport_error")
                raise IdentityUnavailable() from None
            if response.status_code != 200:
                log.warning("introspection_unavailable status=%s", response.status_code)
                raise IdentityUnavailable()
            try:
                data = response.json()
            except ValueError:
                raise IdentityUnavailable() from None
            if not isinstance(data, dict):
                raise IdentityUnavailable()
            if data.get("active") is False:
                reason = response.headers.get("X-PoC-Introspection-Reason")
                if reason in {
                    "unknown_token",
                    "expired_or_invalid",
                    "missing_user",
                    "inactive_user",
                    "missing_application",
                    "wrong_resource",
                    "missing_scope",
                }:
                    log.warning("introspection_inactive reason=%s", reason)
            return data

        if self.client is None:
            async with httpx.AsyncClient(trust_env=False) as client:
                data = await fetch(client)
        else:
            data = await fetch(self.client)

        if data.get("active") is not True:
            return self.reject("inactive")
        audience = data.get("aud")
        audiences = [audience] if isinstance(audience, str) else audience
        if (
            not isinstance(audiences, list)
            or not all(isinstance(a, str) for a in audiences)
            or self.config.mcp_public_url not in audiences
        ):
            return self.reject("audience_mismatch")
        subject, client_id = data.get("sub"), data.get("client_id")
        if not isinstance(subject, str) or not subject.strip():
            return self.reject("missing_subject")
        if not isinstance(client_id, str) or not client_id.strip():
            return self.reject("missing_client_id")
        if data.get("iss") != self.config.django_issuer_url:
            return self.reject("issuer_mismatch")
        expiry = data.get("exp")
        if type(expiry) is not int or expiry <= time.time():
            return self.reject("expired_or_missing_expiry")
        if not isinstance(data.get("scope"), str):
            return self.reject("invalid_scope_claim")
        scopes = data["scope"].split()
        if self.config.mcp_required_scope not in scopes:
            return self.reject("missing_scope")
        return AccessToken(
            token=token,
            client_id=client_id,
            subject=subject,
            scopes=scopes,
            expires_at=expiry,
            resource=self.config.mcp_public_url,
            claims=data,
        )
